"""Thin LLM abstraction so every agent depends on a narrow `ChatModel`
protocol rather than the OpenAI SDK directly — this is what lets every
agent be unit tested with `FakeChatModel` and no network/API key
(see docs/TESTING_STRATEGY.md)."""
from __future__ import annotations

from typing import Protocol

from app.core.config import get_settings


class ChatModel(Protocol):
    def complete(self, *, system: str, user: str) -> str:
        """Return the model's text completion for a single-turn exchange."""
        ...


class OpenAIChatModel:
    """Production implementation, backed by `langchain_openai.ChatOpenAI`."""

    def __init__(self, model: str | None = None) -> None:
        settings = get_settings()
        self._model_name = model or settings.openai_model
        self._api_key = settings.openai_api_key

    def complete(self, *, system: str, user: str) -> str:
        from langchain_core.messages import HumanMessage, SystemMessage
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(model=self._model_name, api_key=self._api_key, temperature=0.2)
        response = llm.invoke([SystemMessage(content=system), HumanMessage(content=user)])
        return str(response.content)


class FakeChatModel:
    """Deterministic stub for tests: returns scripted responses keyed by a
    substring of the user prompt, or a default echo if nothing matches."""

    def __init__(self, scripted: dict[str, str] | None = None, default: str = "") -> None:
        self._scripted = scripted or {}
        self._default = default
        self.calls: list[tuple[str, str]] = []

    def complete(self, *, system: str, user: str) -> str:
        self.calls.append((system, user))
        for trigger, response in self._scripted.items():
            if trigger in user:
                return response
        return self._default


_default_model: ChatModel | None = None


def get_chat_model() -> ChatModel:
    global _default_model
    if _default_model is None:
        _default_model = OpenAIChatModel()
    return _default_model
