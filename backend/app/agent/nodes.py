"""Graph nodes. Each node receives the state and returns the keys it updates.

External dependencies (vector search, history store) are injected through
`config["configurable"]` so the graph can be tested with fakes.
"""

import json
import logging
import re
import uuid

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage
from langchain_core.runnables import RunnableConfig

from app.agent import prompts
from app.agent.llm import get_json_llm, get_llm
from app.agent.state import AgentState
from app.core.config import get_settings

log = logging.getLogger(__name__)

_GREETING_RE = re.compile(
    r"^\s*(hi|hello|hey|hola|buenas|good (morning|afternoon|evening)|thanks?( you)?|thank you|"
    r"gracias|bye|goodbye|adi[oó]s|ok(ay)?)\W*$",
    re.IGNORECASE,
)


def _deps(config: RunnableConfig) -> dict:
    return config.get("configurable", {})


def _parse_json(raw: str) -> dict:
    """Small local models sometimes wrap JSON in text or code fences; be forgiving."""
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        match = re.search(r"\{.*\}", raw or "", re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except json.JSONDecodeError:
                pass
    return {}


def _history_messages(history: list[dict]) -> list:
    return [
        HumanMessage(m["content"]) if m["role"] == "user" else AIMessage(m["content"])
        for m in history
    ]


# 1) Validate the intent of the question ---------------------------------------------------
def validate_intent(state: AgentState) -> AgentState:
    question = state["question"].strip()
    if _GREETING_RE.match(question):
        return {"intent": "greeting", "search_query": ""}
    if len(re.sub(r"\W", "", question)) < 2:
        return {"intent": "unclear", "search_query": ""}

    messages = [
        SystemMessage(prompts.INTENT_SYSTEM),
        *_history_messages(state.get("history", [])),
        HumanMessage(question),
    ]
    data = _parse_json(get_json_llm().invoke(messages).content)
    intent = data.get("intent") if data.get("intent") in {"question", "greeting", "unclear"} else "question"
    search_query = str(data.get("search_query") or "").strip() or question
    log.info("intent=%s search_query=%r", intent, search_query)
    return {"intent": intent, "search_query": search_query}


def route_intent(state: AgentState) -> str:
    return {"greeting": "greet", "unclear": "ask_clarification"}.get(state["intent"], "retrieve")


# 2) Search the vector database ------------------------------------------------------------
def retrieve(state: AgentState, config: RunnableConfig) -> AgentState:
    settings = get_settings()
    search = _deps(config)["retriever"]
    # Search with the rewritten query and with the original question, keep the best score.
    found: dict[int, dict] = {}
    for query in {state["search_query"], state["question"]}:
        for chunk in search(query, settings.retrieval_top_k):
            if chunk.chunk_id not in found or chunk.similarity > found[chunk.chunk_id]["similarity"]:
                found[chunk.chunk_id] = {
                    "chunk_id": chunk.chunk_id,
                    "document_id": chunk.document_id,
                    "title": chunk.document_title,
                    "source_url": chunk.source_url,
                    "page": chunk.meta.get("page"),
                    "section": chunk.meta.get("section"),
                    "content": chunk.content,
                    "similarity": chunk.similarity,
                }
    ranked = sorted(found.values(), key=lambda c: c["similarity"], reverse=True)
    # Hallucination control #1: minimum similarity threshold.
    context = [c for c in ranked if c["similarity"] >= settings.similarity_threshold]
    context = context[: settings.retrieval_top_k]
    log.info(
        "retrieved=%d above_threshold=%d best=%.3f",
        len(ranked), len(context), ranked[0]["similarity"] if ranked else 0.0,
    )
    return {"retrieved": ranked, "context": context}


def route_after_retrieve(state: AgentState) -> str:
    return "grade_context" if state.get("context") else "reject"


# 3) Check whether the context is enough (dedicated validation node) -----------------------
def grade_context(state: AgentState) -> AgentState:
    messages = [
        SystemMessage(prompts.GRADER_SYSTEM),
        HumanMessage(
            f"Question: {state['search_query']}\n\n"
            f"Context fragments:\n{prompts.format_context(state['context'])}"
        ),
    ]
    data = _parse_json(get_json_llm().invoke(messages).content)
    value = data.get("sufficient")
    # If the model returns something unparsable we trust the similarity threshold.
    sufficient = value if isinstance(value, bool) else str(value).lower() != "false"
    log.info("context_sufficient=%s", sufficient)
    return {"context_sufficient": sufficient}


def route_after_grade(state: AgentState) -> str:
    return "generate" if state.get("context_sufficient") else "reject"


# 4) Answer only with the retrieved information --------------------------------------------
def generate(state: AgentState) -> AgentState:
    context = state["context"]
    system = prompts.ANSWER_SYSTEM.replace("{context}", prompts.format_context(context))
    messages = [
        SystemMessage(system),
        *_history_messages(state.get("history", [])),
        HumanMessage(state["question"]),
    ]
    answer = get_llm().invoke(messages).content.strip()

    if not answer or prompts.NO_ANSWER_TOKEN in answer:
        return {"answer": "", "status": "rejected", "reject_reason": "model_declined"}

    cited = sorted({int(n) for n in re.findall(r"\[(\d+)\]", answer) if 0 < int(n) <= len(context)})
    used = cited or list(range(1, len(context) + 1))
    sources = [
        {
            "index": i,
            "document_id": context[i - 1]["document_id"],
            "title": context[i - 1]["title"],
            "source_url": context[i - 1]["source_url"],
            "page": context[i - 1]["page"],
            "section": context[i - 1]["section"],
            "similarity": context[i - 1]["similarity"],
            "snippet": context[i - 1]["content"][:400],
        }
        for i in used
    ]
    return {"answer": answer, "status": "answered", "sources": sources}


def route_after_generate(state: AgentState) -> str:
    return "reject" if state.get("status") == "rejected" else "save_history"


# 5) Explicit rejection ----------------------------------------------------------------------
def reject(state: AgentState) -> AgentState:
    if not state.get("context"):
        reason = "no_relevant_chunks"
    elif state.get("context_sufficient") is False:
        reason = "insufficient_context"
    else:
        reason = state.get("reject_reason") or "model_declined"
    return {
        "answer": f"{prompts.NOT_ENOUGH_INFO} {prompts.UPLOAD_SUGGESTION}",
        "status": "rejected",
        "reject_reason": reason,
        "sources": [],
    }


def greet(state: AgentState) -> AgentState:
    return {"answer": prompts.GREETING_REPLY, "status": "greeting", "sources": []}


def ask_clarification(state: AgentState) -> AgentState:
    return {"answer": prompts.CLARIFICATION_REPLY, "status": "clarification", "sources": []}


# 6) Save the interaction in the history ----------------------------------------------------
def save_history(state: AgentState, config: RunnableConfig) -> AgentState:
    store = _deps(config).get("history_store")
    if store is not None:
        conversation_id = uuid.UUID(str(state["conversation_id"]))
        store.add_message(conversation_id, "user", state["question"])
        store.add_message(
            conversation_id,
            "assistant",
            state["answer"],
            status=state["status"],
            sources=state.get("sources", []),
        )
    return {}
