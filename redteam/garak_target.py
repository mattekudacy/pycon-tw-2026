"""garak entry point: lets garak attack our chatbot (system prompt included).

garak only sees text in / text out, so it knows nothing about retrieval or tools.
That is why we point it at the chatbot, not at rag_bot / agent_bot.

Usage: --target_type function.Single --target_name redteam.garak_target#chatbot
"""
from redteam.targets import get_target


def chatbot(prompt, **kwargs) -> list[str]:
    try:
        return [get_target("chatbot")(str(prompt)).text]
    except RuntimeError:  # exhausted retries: record as no output rather than abort the scan
        return [None]
