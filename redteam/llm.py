"""Thin OpenAI-compatible client with an on-disk response cache.

Provider/model names come from env (see .env.example), never hard-coded.
Set REDTEAM_CACHE=0 to bypass the cache. Cached replies make reruns offline,
deterministic, and immune to rate limits.
"""
import hashlib
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import APIConnectionError, APITimeoutError, OpenAI, RateLimitError

load_dotenv()

CACHE_DIR = Path(__file__).parent / "cache"


def cache_enabled() -> bool:
    return os.getenv("REDTEAM_CACHE", "1") != "0"


def _client() -> OpenAI:
    return OpenAI(
        base_url=os.getenv("LLM_BASE_URL", "https://ollama.com/v1"),
        api_key=os.environ.get("OLLAMA_API_KEY") or os.getenv("LLM_API_KEY", ""),
    )


def _cache_path(model: str, temperature: float, messages: list[dict]) -> Path:
    key = hashlib.sha256(json.dumps([model, temperature, messages], sort_keys=True).encode()).hexdigest()
    return CACHE_DIR / f"{key}.json"


def evict(messages: list[dict], model: str, temperature: float = 0.0) -> None:
    """Drop a cached reply (e.g. one that turned out to be unusable)."""
    _cache_path(model, temperature, messages).unlink(missing_ok=True)


def chat(messages: list[dict], model: str | None = None, temperature: float = 0.0) -> str:
    model = model or os.environ.get("TARGET_MODEL", "nemotron-3-nano:30b")
    path = _cache_path(model, temperature, messages)
    if cache_enabled() and path.exists():
        return json.loads(path.read_text())["text"]
    text = ""
    for attempt in range(6):  # cloud rate limits (429) and empty reasoning-only replies are transient
        try:
            resp = _client().chat.completions.create(
                model=model, messages=messages, temperature=temperature, seed=0,
                max_tokens=4096,  # reasoning models spend tokens thinking; leave headroom
            )
            text = resp.choices[0].message.content or ""
        except (RateLimitError, APIConnectionError, APITimeoutError):
            text = ""
        if text:
            break
        time.sleep(min(2 ** attempt, 20))
    if not text:
        raise RuntimeError(f"no completion from {model} after retries; not caching")
    if cache_enabled():
        CACHE_DIR.mkdir(exist_ok=True)
        path.write_text(json.dumps({"model": model, "messages": messages, "text": text}))
    return text

