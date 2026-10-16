"""One adapter for every app, so the harness never special-cases architecture.

    target = get_target("rag_bot")
    r = target("What is your return policy?")
    r.text, r.retrieved_context, r.tool_calls
"""
import unicodedata
from dataclasses import dataclass, field
from typing import Callable

TARGET_NAMES = ["chatbot", "rag_bot", "agent_bot"]

# Register your own app by name, or skip this and use "module:function" (see get_target):
#     from redteam.targets import REGISTRY
#     REGISTRY["my_app"] = my_function        # my_function(prompt) -> str | TargetResponse
REGISTRY: dict[str, Callable[..., "str | TargetResponse"]] = {}


@dataclass
class TargetResponse:
    text: str
    retrieved_context: list[str] = field(default_factory=list)  # RAG only
    tool_calls: list[dict] = field(default_factory=list)  # agent only


def clean(text: str) -> str:
    """Models emit U+202F / non-breaking hyphens etc. These broke exact-match checks and
    confused the LLM judge, so every target returns normalised text."""
    text = unicodedata.normalize("NFKC", text)
    return "".join("-" if unicodedata.category(c) == "Pd" else c for c in text)


def _wrap(fn: Callable[..., "str | TargetResponse"]) -> Callable[..., TargetResponse]:
    """Accept a plain `prompt -> str` function (or one returning a TargetResponse)."""

    def target(prompt: str, history: list[dict] | None = None) -> TargetResponse:
        out = fn(prompt, history) if history else fn(prompt)
        return out if isinstance(out, TargetResponse) else TargetResponse(text=clean(str(out)))

    return target


def get_target(name: str) -> Callable[..., TargetResponse]:
    """name = chatbot | rag_bot | agent_bot | a key in REGISTRY | "package.module:function"."""
    if name in REGISTRY:
        return _wrap(REGISTRY[name])
    if ":" in name:
        import importlib

        module, _, attr = name.partition(":")
        return _wrap(getattr(importlib.import_module(module), attr))
    if name == "chatbot":
        from apps.chatbot.app import respond

        def chatbot(prompt: str, history: list[dict] | None = None) -> TargetResponse:
            if history:
                raise ValueError("chatbot does not support multi-turn history; use rag_bot")
            return TargetResponse(text=clean(respond(prompt)))

        return chatbot
    if name == "rag_bot":
        from apps.rag_bot.app import respond

        def rag(prompt: str, history: list[dict] | None = None) -> TargetResponse:
            text, context = respond(prompt, history)
            return TargetResponse(text=clean(text), retrieved_context=context)

        return rag
    if name == "agent_bot":
        from apps.agent_bot.app import respond

        def agent(prompt: str, history: list[dict] | None = None) -> TargetResponse:
            if history:
                raise ValueError("agent_bot does not support multi-turn history; use rag_bot")
            text, context, calls = respond(prompt)
            return TargetResponse(text=clean(text), retrieved_context=context, tool_calls=calls)

        return agent
    raise ValueError(f"unknown target {name!r}; use one of {TARGET_NAMES}, a REGISTRY key, or 'module:function'")


def deepteam_callback(name: str):
    """Async model callback in the shape deepteam expects (text in, text out)."""
    target = get_target(name)

    async def callback(input: str) -> str:
        return target(input).text

    return callback
