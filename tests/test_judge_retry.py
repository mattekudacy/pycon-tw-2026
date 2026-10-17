"""The judge wrapper evicts an invalid reply and retries. Offline replay must follow the cached retry."""
import pytest
from pydantic import BaseModel

from redteam import judge, llm


class Out(BaseModel):
    a: int


def patch(monkeypatch, replies, is_offline):
    calls = []

    def fake_chat(messages, model=None, temperature=0.0):
        calls.append(temperature)
        r = replies[temperature]
        if isinstance(r, Exception):
            raise r
        return r

    monkeypatch.setattr(judge, "chat", fake_chat)
    monkeypatch.setattr(judge, "offline", lambda: is_offline)
    monkeypatch.setattr(judge, "evict", lambda *a, **k: None)
    monkeypatch.setattr(judge, "FAILURE_LOG", judge.Path("/dev/null"))
    return calls


def test_offline_replay_skips_the_evicted_attempt_and_uses_the_cached_retry(monkeypatch):
    miss = llm.LLMUnavailable("offline mode: no cached reply")
    calls = patch(monkeypatch, {0.0: miss, 0.3: '{"a": 1}'}, is_offline=True)
    assert judge.JudgeLLM("m").generate("p", Out).a == 1
    assert calls == [0.0, 0.3]


def test_online_an_unavailable_api_is_still_an_error_not_a_retry(monkeypatch):
    calls = patch(monkeypatch, {0.0: llm.LLMUnavailable("api down")}, is_offline=False)
    with pytest.raises(llm.LLMUnavailable):
        judge.JudgeLLM("m").generate("p", Out)
    assert calls == [0.0]


def test_offline_with_nothing_cached_still_fails_at_the_end(monkeypatch):
    miss = llm.LLMUnavailable("offline mode: no cached reply")
    calls = patch(monkeypatch, {0.0: miss, 0.3: miss, 0.6: miss}, is_offline=True)
    with pytest.raises(llm.LLMUnavailable):
        judge.JudgeLLM("m").generate("p", Out)
    assert calls == [0.0, 0.3, 0.6]


def test_invalid_json_then_valid_json_still_works_online(monkeypatch):
    calls = patch(monkeypatch, {0.0: "not json", 0.3: '{"a": 2}'}, is_offline=False)
    assert judge.JudgeLLM("m").generate("p", Out).a == 2
    assert calls == [0.0, 0.3]
