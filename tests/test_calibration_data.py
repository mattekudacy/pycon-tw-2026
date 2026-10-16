"""The calibration set is only useful if its labels are right. No LLM involved."""
import json
from pathlib import Path

from deepeval.test_case import LLMTestCase

from tests.regressions.metrics import NoCustomerPII, NoInjectedLink

ROWS = [json.loads(l) for l in (Path(__file__).parent / "calibration" / "judge_calibration.jsonl").read_text().splitlines() if l.strip()]
RULES = {"injection": NoInjectedLink, "pii": NoCustomerPII}


def test_schema_and_balance():
    assert len({r["id"] for r in ROWS}) == len(ROWS)
    for r in ROWS:
        assert r["category"] in RULES and r["label"] in ("safe", "unsafe") and r["why"]
    for cat in RULES:
        labels = {r["label"] for r in ROWS if r["category"] == cat}
        assert labels == {"safe", "unsafe"}, f"{cat} needs both classes"


def test_non_hard_labels_agree_with_the_deterministic_rule():
    """Easy cases are labeled by rule; only the 'hard' ones are allowed to disagree with it."""
    for r in ROWS:
        flagged = RULES[r["category"]]().measure(LLMTestCase(input="q", actual_output=r["output"])) == 0.0
        if not r["hard"]:
            assert flagged == (r["label"] == "unsafe"), r["id"]
