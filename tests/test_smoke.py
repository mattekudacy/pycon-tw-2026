import pytest

from redteam.targets import get_target


def test_chatbot_adapter_shape(monkeypatch):
    monkeypatch.setattr("apps.chatbot.app.chat", lambda messages, **kw: "hello")
    r = get_target("chatbot")("hi")
    assert r.text == "hello" and r.retrieved_context == [] and r.tool_calls == []


def test_unknown_target():
    with pytest.raises(ValueError):
        get_target("nope")
