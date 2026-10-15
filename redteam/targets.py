"""One adapter for every app, so the harness never special-cases architecture.

    target = get_target("rag_bot")
    r = target("What is your return policy?")
    r.text, r.retrieved_context, r.tool_calls
"""
import unicodedata
from dataclasses import dataclass, field
from typing import Callable

TARGET_NAMES = ["chatbot", "rag_bot", "agent_bot"]


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


def get_target(name: str) -> Callable[[str], TargetResponse]:
    if name == "chatbot":
        from apps.chatbot.app import respond

        return lambda prompt: TargetResponse(text=clean(respond(prompt)))
    if name == "rag_bot":
        from apps.rag_bot.app import respond

        def rag(prompt: str) -> TargetResponse:
            text, context = respond(prompt)
            return TargetResponse(text=clean(text), retrieved_context=context)

        return rag
    if name == "agent_bot":
        from apps.agent_bot.app import respond

        def agent(prompt: str) -> TargetResponse:
            text, context, calls = respond(prompt)
            return TargetResponse(text=clean(text), retrieved_context=context, tool_calls=calls)

        return agent
    raise ValueError(f"unknown or not-yet-built target {name!r}; choose from {TARGET_NAMES}")


def deepteam_callback(name: str):
    """Async model callback in the shape deepteam expects (text in, text out)."""
    target = get_target(name)

    async def callback(input: str) -> str:
        return target(input).text

    return callback
