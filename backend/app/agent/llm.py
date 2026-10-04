"""Local LLM served by Ollama (default: qwen2.5:3b)."""

from functools import lru_cache

from langchain_core.language_models import BaseChatModel
from langchain_ollama import ChatOllama

from app.core.config import get_settings

_override: dict[str, BaseChatModel] = {}


def set_llm(text_llm: BaseChatModel | None, json_llm: BaseChatModel | None = None) -> None:
    """Swap the models (used by tests)."""
    _override.clear()
    if text_llm is not None:
        _override["text"] = text_llm
        _override["json"] = json_llm or text_llm


@lru_cache
def _ollama(json_mode: bool) -> ChatOllama:
    s = get_settings()
    return ChatOllama(
        model=s.llm_model,
        base_url=s.ollama_base_url,
        temperature=s.llm_temperature,
        num_ctx=s.llm_num_ctx,
        format="json" if json_mode else "",
    )


def get_llm() -> BaseChatModel:
    """Free-text model, used to write the final answer."""
    return _override.get("text") or _ollama(False)


def get_json_llm() -> BaseChatModel:
    """Same model forced to output JSON, used by the classifier / grader nodes."""
    return _override.get("json") or _ollama(True)
