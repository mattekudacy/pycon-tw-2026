"""The adapter is the contract for 'point it at your own app'. No model calls."""
import pytest

from redteam.targets import REGISTRY, TargetResponse, get_target


def test_module_function_spec_wraps_a_plain_function(monkeypatch):
    monkeypatch.setattr("redteam.llm.chat", lambda messages, **kw: "Tomatoes are fruit.")
    import examples.my_app as app

    monkeypatch.setattr(app, "chat", lambda messages, **kw: "Tomatoes are fruit.")
    r = get_target("examples.my_app:ask")("is a tomato a fruit?")
    assert isinstance(r, TargetResponse) and r.text == "Tomatoes are fruit." and r.tool_calls == []


def test_registry_and_structured_return(monkeypatch):
    monkeypatch.setitem(REGISTRY, "demo", lambda p: TargetResponse(text="x", retrieved_context=["doc"]))
    assert get_target("demo")("q").retrieved_context == ["doc"]


def test_text_is_normalised_for_plain_string_apps(monkeypatch):
    monkeypatch.setitem(REGISTRY, "spacey", lambda p: "30 days")
    assert get_target("spacey")("q").text == "30 days"


def test_unknown_target_message_names_the_options():
    with pytest.raises(ValueError, match="module:function"):
        get_target("nope")
