import functools
import os

from redteam.targets import get_target


def target_name() -> str:
    return os.environ.get("REDTEAM_TARGET", "rag_bot")


@functools.lru_cache(maxsize=None)
def ask(question: str):
    """One target call per question per session, shared by the security and quality tests."""
    return get_target(target_name())(question)
