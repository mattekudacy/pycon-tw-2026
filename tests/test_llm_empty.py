"""An empty reply that stopped on `length` must fail fast, and the cache keys must not change."""
import hashlib
import json
from types import SimpleNamespace

import pytest

from redteam import llm


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """These tests install a fake API client, so they must not depend on the caller's environment
    (REDTEAM_OFFLINE=1 would fail at the cache check before the fake client is ever used)."""
    for var in ("REDTEAM_OFFLINE", "REDTEAM_MAX_TOKENS", "REDTEAM_TIMEOUT", "REDTEAM_CACHE"):
        monkeypatch.delenv(var, raising=False)


def fake_client(calls, content="", finish="length"):
    def create(**kw):
        calls.append(kw)
        msg = SimpleNamespace(content=content, tool_calls=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg, finish_reason=finish)])

    return SimpleNamespace(chat=SimpleNamespace(completions=SimpleNamespace(create=create)))


def test_empty_reply_after_length_is_not_retried(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(llm, "_client", lambda: fake_client(calls))
    monkeypatch.setattr(llm, "_backoff", lambda attempt: pytest.fail("must not back off on a deterministic empty reply"))
    with pytest.raises(llm.EmptyCompletion):
        llm.chat([{"role": "user", "content": "decode this"}])
    assert len(calls) == 1
    assert list(tmp_path.iterdir()) == []  # nothing cached


def test_empty_completion_is_an_llm_unavailable_so_tests_skip_it():
    assert issubclass(llm.EmptyCompletion, llm.LLMUnavailable) and issubclass(llm.LLMUnavailable, RuntimeError)


def test_reply_budget_is_configurable_and_default_cache_keys_are_unchanged(monkeypatch):
    monkeypatch.delenv("REDTEAM_MAX_TOKENS", raising=False)
    messages = [{"role": "user", "content": "hi"}]
    old_key = hashlib.sha256(json.dumps(["m", 0.0, messages], sort_keys=True).encode()).hexdigest()
    assert llm._cache_path("m", 0.0, messages).name == f"{old_key}.json"  # committed cache stays valid
    monkeypatch.setenv("REDTEAM_MAX_TOKENS", "1500")
    assert llm.max_tokens_default() == 1500
    assert llm._cache_path("m", 0.0, messages).name != f"{old_key}.json"  # a smaller budget never reuses 4096 answers


def test_budget_is_sent_to_the_api(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(llm, "CACHE_DIR", tmp_path)
    monkeypatch.setenv("REDTEAM_MAX_TOKENS", "1500")
    monkeypatch.setattr(llm, "_client", lambda: fake_client(calls, content="ok", finish="stop"))
    assert llm.chat([{"role": "user", "content": "hi"}]) == "ok"
    assert calls[0]["max_tokens"] == 1500


def test_client_has_a_finite_timeout(monkeypatch):
    monkeypatch.setenv("OLLAMA_API_KEY", "x")
    client = llm._client()
    assert client.timeout == 150.0 and client.max_retries == 1
    monkeypatch.setenv("REDTEAM_TIMEOUT", "60")
    assert llm._client().timeout == 60.0
