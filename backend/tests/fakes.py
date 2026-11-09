"""A scripted chat model for testing agents offline."""
from typing import Any

from langchain_core.language_models import BaseChatModel
from langchain_core.messages import AIMessage, BaseMessage
from langchain_core.outputs import ChatGeneration, ChatResult
from pydantic import Field


class ScriptedChatModel(BaseChatModel):
    """Returns the scripted replies in order. A reply may be a callable that sees the prompt messages."""
    script: list[Any] = Field(default_factory=list)   # AIMessage, or a callable(messages) -> AIMessage
    seen: list[list[BaseMessage]] = Field(default_factory=list)

    @property
    def _llm_type(self) -> str:
        return "scripted"

    def bind_tools(self, tools, **kwargs):
        return self

    def _generate(self, messages, stop=None, run_manager=None, **kwargs) -> ChatResult:
        self.seen.append(list(messages))
        reply = self.script.pop(0)
        msg = reply(messages) if callable(reply) else reply
        return ChatResult(generations=[ChatGeneration(message=msg)])


def tool_call(name: str, args: dict | None = None, call_id: str = "c1") -> AIMessage:
    return AIMessage(content="", tool_calls=[{"name": name, "args": args or {}, "id": call_id}])
