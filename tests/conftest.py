"""An unreachable model API is not a test verdict.

If a test dies with LLMUnavailable we report it as SKIPPED with the reason "LLM unavailable"
(not as a failure), and redteam/gate.py counts those separately: a few are tolerated, many make
the gate INCONCLUSIVE instead of silently green or misleadingly red.
"""
import pytest

from redteam.llm import LLMUnavailable


@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_makereport(item, call):
    outcome = yield
    rep = outcome.get_result()
    if call.excinfo is not None and call.excinfo.errisinstance(LLMUnavailable):
        rep.outcome = "skipped"
        rep.longrepr = (str(item.path), item.reportinfo()[1] or 0, "Skipped: LLM unavailable")
