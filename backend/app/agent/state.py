"""State that flows through the LangGraph graph."""

from typing import TypedDict


class AgentState(TypedDict, total=False):
    # Input
    question: str
    user_id: str
    conversation_id: str
    history: list[dict]  # [{"role": "user"|"assistant", "content": str}, ...]

    # validate_intent
    intent: str  # question | greeting | unclear
    search_query: str

    # retrieve
    retrieved: list[dict]  # top-k chunks before the threshold (kept for debugging)
    context: list[dict]  # chunks that passed the similarity threshold

    # grade_context
    context_sufficient: bool

    # Output
    answer: str
    status: str  # answered | rejected | greeting | clarification
    reject_reason: str  # no_relevant_chunks | insufficient_context | model_declined
    sources: list[dict]
