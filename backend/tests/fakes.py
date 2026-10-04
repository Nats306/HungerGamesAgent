"""Test doubles: deterministic embeddings and a scripted chat model (no Ollama / HF needed)."""

import hashlib
import json
import math
import re
from collections.abc import Callable

from langchain_core.embeddings import Embeddings
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult

DIM = 384
_STOP = {"the", "a", "an", "of", "in", "is", "was", "who", "what", "and", "to", "did", "does"}


def _tokens(text: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", text.lower()) if t not in _STOP]


class HashEmbeddings(Embeddings):
    """Bag-of-words hashed into 384 dims: texts sharing words get high cosine similarity."""

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * DIM
        for tok in _tokens(text):
            v[int(hashlib.md5(tok.encode()).hexdigest(), 16) % DIM] += 1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)


class ScriptedChatModel(BaseChatModel):
    """Answers according to which prompt it receives (router / grader / answer)."""

    responder: Callable[[list[BaseMessage]], str]

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        return ChatResult(generations=[ChatGeneration(message=AIMessage(self.responder(messages)))])


def default_responder(messages: list[BaseMessage]) -> str:
    system = messages[0].content
    last = messages[-1].content
    if "input router" in system:
        return json.dumps({"intent": "question", "search_query": last})
    if "retrieved context is enough" in system:
        return json.dumps({"sufficient": True})
    return "Katniss Everdeen and Peeta Mellark won the 74th Hunger Games [1]."
