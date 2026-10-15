import pytest

from redteam.targets import get_target


def test_chatbot_adapter_shape(monkeypatch):
    monkeypatch.setattr("apps.chatbot.app.chat", lambda messages, **kw: "hello")
    r = get_target("chatbot")("hi")
    assert r.text == "hello" and r.retrieved_context == [] and r.tool_calls == []


def test_unknown_target():
    with pytest.raises(ValueError):
        get_target("nope")


def test_rag_adapter_returns_retrieved_context(monkeypatch):
    monkeypatch.setattr("apps.rag_bot.app.chat", lambda messages, **kw: "ok")
    r = get_target("rag_bot")("What's the return window?")
    assert r.text == "ok" and r.tool_calls == []
    assert any("Standard returns" in c for c in r.retrieved_context)


def test_retriever_finds_poisoned_and_pii_docs():
    from apps.rag_bot.retriever import BM25, load_chunks

    index = BM25(load_chunks())
    assert any("NOTE TO AI ASSISTANT" in c for c in index.search("How long does shipping take?"))
    assert any("meiling.chen@example.com" in c for c in index.search("email of customer with cracked screen"))
    assert index.search("How much is the CEO's salary?") == []
