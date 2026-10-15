"""Deterministic checks on the agent's executor (no LLM)."""
import pytest

from apps.agent_bot import app as agent


@pytest.fixture(autouse=True)
def full_defenses(monkeypatch):
    monkeypatch.setenv("AGENT_DEFENSES", "policy,taint")


def test_policy_denies_other_customers_order_and_large_refunds():
    assert agent.execute("issue_refund", {"order_id": "ORD-2002", "amount": 10})[0] is False
    assert agent.execute("issue_refund", {"order_id": "ORD-1002", "amount": 900})[0] is False
    assert agent.execute("issue_refund", {"order_id": "ORD-1001", "amount": 61})[0] is False  # > order total
    assert agent.execute("issue_refund", {"order_id": "ORD-1001", "amount": -5})[0] is False
    assert agent.execute("issue_refund", {"order_id": "ORD-1001", "amount": 20})[0] is True


def test_lookup_hides_other_customers_orders():
    assert agent.execute("lookup_order", {"order_id": "ORD-2002"}) == (False, "order not found")


def test_naive_agent_executes_anything(monkeypatch):
    monkeypatch.setenv("AGENT_DEFENSES", "none")
    assert agent.execute("issue_refund", {"order_id": "ORD-2002", "amount": 9999})[0] is True
