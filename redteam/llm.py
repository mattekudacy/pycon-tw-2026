"""Thin OpenAI-compatible client with an on-disk response cache.

Provider/model names come from env (see .env.example), never hard-coded.
Set REDTEAM_CACHE=0 to bypass the cache. Cached replies make reruns offline,
deterministic, and immune to rate limits.
"""
import hashlib
import json
import os
import random
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError

load_dotenv()

CACHE_DIR = Path(__file__).parent / "cache"


def offline() -> bool:
    """REDTEAM_OFFLINE=1: replay from the cache only. A cache miss fails at once with a clear error
    instead of retrying against a dead network (use when the venue wifi is down)."""
    return os.getenv("REDTEAM_OFFLINE", "0") == "1"


def _hit(path: Path) -> None:
    """For curating the committed cache: REDTEAM_CACHE_HITLOG=file appends every entry that is read."""
    log = os.getenv("REDTEAM_CACHE_HITLOG")
    if log:
        with open(log, "a") as f:
            f.write(path.name + "\n")


def _miss(model: str) -> "LLMUnavailable":
    return LLMUnavailable(f"offline mode (REDTEAM_OFFLINE=1): no cached reply for this request to {model}")


def cache_enabled() -> bool:
    return os.getenv("REDTEAM_CACHE", "1") != "0"


def _client() -> OpenAI:
    # The SDK default is a 10-minute timeout with 2 retries. One hung connection then froze a whole
    # sequential probe (promptinject) for ten minutes; a 4096-token reply takes ~95 s at most.
    return OpenAI(
        base_url=os.getenv("LLM_BASE_URL", "https://ollama.com/v1"),
        api_key=os.environ.get("OLLAMA_API_KEY") or os.getenv("LLM_API_KEY", ""),
        timeout=float(os.getenv("REDTEAM_TIMEOUT", "150")),
        max_retries=1,
    )


class LLMUnavailable(RuntimeError):
    """The model API gave no usable reply after all retries (rate limit, outage, empty replies).
    This is an infrastructure problem, not a verdict about the app, so tests and the CI gate
    report it separately from a failed assertion."""


class EmptyCompletion(LLMUnavailable):
    """The model spent its whole token budget thinking and returned no answer (finish_reason=length).
    With temperature 0 and a fixed seed a retry gives the same result, so we do not retry: an
    attempt that cost 93 s used to cost minutes of backoff on top."""


def max_tokens_default() -> int:
    """REDTEAM_MAX_TOKENS lowers the reply budget (the nightly garak scan uses 1500)."""
    return int(os.getenv("REDTEAM_MAX_TOKENS", "4096"))


def _backoff(attempt: int) -> None:
    time.sleep(min(2 ** attempt, 45) * random.uniform(0.7, 1.3))  # jitter: parallel jobs must not retry in lockstep


def _cache_path(model: str, temperature: float, messages: list[dict]) -> Path:
    parts = [model, temperature, messages]
    if max_tokens_default() != 4096:  # keeps every cache entry made at the default budget valid
        parts.append(max_tokens_default())
    key = hashlib.sha256(json.dumps(parts, sort_keys=True).encode()).hexdigest()
    return CACHE_DIR / f"{key}.json"


def evict(messages: list[dict], model: str, temperature: float = 0.0) -> None:
    """Drop a cached reply (e.g. one that turned out to be unusable)."""
    _cache_path(model, temperature, messages).unlink(missing_ok=True)


def chat(messages: list[dict], model: str | None = None, temperature: float = 0.0) -> str:
    model = model or os.environ.get("TARGET_MODEL", "nemotron-3-nano:30b")
    path = _cache_path(model, temperature, messages)
    if cache_enabled() and path.exists():
        _hit(path)
        return json.loads(path.read_text())["text"]
    if offline():
        raise _miss(model)
    text = ""
    for attempt in range(8):  # cloud rate limits (429) and empty reasoning-only replies are transient
        try:
            resp = _client().chat.completions.create(
                model=model, messages=messages, temperature=temperature, seed=0,
                max_tokens=max_tokens_default(),  # reasoning models spend tokens thinking; leave headroom
            )
            text = resp.choices[0].message.content or ""
            if not text and resp.choices[0].finish_reason == "length":
                raise EmptyCompletion(f"{model} used all {max_tokens_default()} tokens thinking and returned no answer")
        except (RateLimitError, APIConnectionError, APITimeoutError):
            text = ""
        if text:
            break
        _backoff(attempt)
    if not text:
        raise LLMUnavailable(f"no completion from {model} after retries; not caching")
    if cache_enabled():
        CACHE_DIR.mkdir(exist_ok=True)
        path.write_text(json.dumps({"model": model, "messages": messages, "text": text}))
    return text



def chat_tools(messages: list[dict], tools: list[dict], model: str | None = None) -> dict:
    """One chat turn with native function calling. Returns the assistant message as a dict
    ({"content": str, "tool_calls": [{"id", "name", "arguments"(str)}]}). Cached like chat();
    unlike chat(), an empty reply is valid when the model made tool calls."""
    model = model or os.environ.get("TARGET_MODEL", "nemotron-3-nano:30b")
    path = _cache_path(model, 0.0, [messages, tools])
    if cache_enabled() and path.exists():
        _hit(path)
        return json.loads(path.read_text())["message"]
    if offline():
        raise _miss(model)
    msg = None
    for attempt in range(8):
        try:
            resp = _client().chat.completions.create(
                model=model, messages=messages, tools=tools or None, temperature=0.0, seed=0,
                max_tokens=max_tokens_default(),
            )
            m = resp.choices[0].message
            if not (m.content or "").strip() and not m.tool_calls and resp.choices[0].finish_reason == "length":
                raise EmptyCompletion(f"{model} used all {max_tokens_default()} tokens thinking and returned no answer")
            if (m.content or "").strip() or m.tool_calls:
                msg = {
                    "content": m.content or "",
                    "tool_calls": [
                        {"id": t.id, "name": t.function.name, "arguments": t.function.arguments}
                        for t in (m.tool_calls or [])
                    ],
                }
                break
        except (RateLimitError, APIConnectionError, APITimeoutError):
            pass
        _backoff(attempt)
    if msg is None:
        raise LLMUnavailable(f"no completion from {model} after retries; not caching")
    if cache_enabled():
        CACHE_DIR.mkdir(exist_ok=True)
        path.write_text(json.dumps({"model": model, "message": msg}))
    return msg
