import json

from app.agent.llm import set_llm
from app.agent.prompts import NO_ANSWER_TOKEN, NOT_ENOUGH_INFO
from tests.conftest import ALICE, BOB
from tests.fakes import ScriptedChatModel, default_responder
from tests.test_documents import upload


def ask(client, question, conversation_id=None):
    body = {"question": question}
    if conversation_id:
        body["conversation_id"] = conversation_id
    return client.post("/api/chat", json=body)


def test_answers_with_sources_and_saves_history(as_user):
    client = as_user(ALICE)
    upload(client)

    response = ask(client, "Who won the 74th Hunger Games?")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "answered"
    assert "Katniss" in data["answer"]
    assert data["sources"][0]["title"] == "74th Hunger Games"
    assert data["sources"][0]["similarity"] >= 0.3

    conversations = client.get("/api/conversations").json()
    assert len(conversations) == 1
    detail = client.get(f"/api/conversations/{data['conversation_id']}").json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]
    assert detail["messages"][1]["sources"]


def test_rejects_when_nothing_relevant_is_found(as_user):
    client = as_user(ALICE)
    upload(client)
    data = ask(client, "Which country hosted the 2022 FIFA World Cup final?").json()
    assert data["status"] == "rejected"
    assert data["answer"].startswith(NOT_ENOUGH_INFO)
    assert data["sources"] == []


def test_rejects_with_empty_knowledge_base(as_user):
    data = ask(as_user(ALICE), "Who won the 74th Hunger Games?").json()
    assert data["status"] == "rejected"


def test_rejects_when_grader_says_context_is_insufficient(as_user):
    def responder(messages):
        if "retrieved context is enough" in messages[0].content:
            return json.dumps({"sufficient": False})
        return default_responder(messages)

    set_llm(ScriptedChatModel(responder=responder))
    client = as_user(ALICE)
    upload(client)
    data = ask(client, "What did Katniss eat in the 74th Hunger Games arena on day 3?").json()
    assert data["status"] == "rejected"


def test_rejects_when_model_declines(as_user):
    def responder(messages):
        if "ONLY the context fragments" in messages[0].content:
            return NO_ANSWER_TOKEN
        return default_responder(messages)

    set_llm(ScriptedChatModel(responder=responder))
    client = as_user(ALICE)
    upload(client)
    assert ask(client, "Who won the 74th Hunger Games?").json()["status"] == "rejected"


def test_greeting_and_unclear_messages(as_user):
    client = as_user(ALICE)
    assert ask(client, "hello!").json()["status"] == "greeting"
    assert ask(client, "?").json()["status"] == "clarification"


def test_follow_up_uses_same_conversation_and_is_private(as_user):
    client = as_user(ALICE)
    upload(client)
    first = ask(client, "Who won the 74th Hunger Games?").json()
    second = ask(client, "Which district were they from?", first["conversation_id"]).json()
    assert second["conversation_id"] == first["conversation_id"]
    detail = client.get(f"/api/conversations/{first['conversation_id']}").json()
    assert len(detail["messages"]) == 4

    bob = as_user(BOB)
    assert bob.get(f"/api/conversations/{first['conversation_id']}").status_code == 404
    assert ask(bob, "Who won?", first["conversation_id"]).status_code == 404
    assert bob.get("/api/conversations").json() == []


def test_llm_failure_returns_503(as_user):
    def boom(_messages):
        raise ConnectionError("ollama is down")

    set_llm(ScriptedChatModel(responder=boom))
    assert ask(as_user(ALICE), "Who won the 74th Hunger Games?").status_code == 503
