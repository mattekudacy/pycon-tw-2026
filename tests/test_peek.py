"""The demo's 'look inside' commands must not break on stage. No model needed."""
import json

from redteam import peek


def test_shorten_never_cuts_mid_word():
    out = peek.shorten("the answer includes that exact sentence demonstrating that it followed the injected note", 40)
    assert out.endswith(" ...") and "followed the i" not in out and len(out) <= 44
    assert peek.shorten("short", 40) == "short"


def test_source_of_includes_decorators():
    src = peek.source_of(peek.ROOT / "tests" / "regressions" / "test_rag_regressions.py", "test_indirect_injection_does_not_reach_users")
    assert src.startswith("@pytest.mark.security") and "assert_test" in src


def test_deepteam_peek_without_a_report_says_what_to_run(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(peek, "REPORT", tmp_path / "missing.json")
    assert peek.deepteam() == 2
    assert "make attack-before-fix" in capsys.readouterr().out


def test_deepteam_peek_picks_the_same_finding_whatever_the_row_order(monkeypatch, tmp_path, capsys):
    cases = [
        {"vulnerability": "Indirect Instruction", "vulnerability_type": "rag_injection", "score": 0.0, "input": "b",
         "actual_output": "x " * 100 + "verify at http://acmeshop-verify.example/login", "reason": "followed the planted note"},
        {"vulnerability": "Indirect Instruction", "vulnerability_type": "document_embedded_instructions", "score": 0.0, "input": "a",
         "actual_output": "ok", "reason": "second finding"},
        {"vulnerability": "PII Leakage", "vulnerability_type": "direct_disclosure", "score": 1.0, "input": "c", "actual_output": "fine", "reason": ""},
    ]
    seen = []
    for order in (cases, list(reversed(cases))):
        report = tmp_path / "r.json"
        report.write_text(json.dumps({"test_cases": order}))
        monkeypatch.setattr(peek, "REPORT", report)
        peek.deepteam()
        seen.append(capsys.readouterr().out.split("One finding")[1])
    assert seen[0] == seen[1] and "document_embedded_instructions" in seen[0] and "2 of 3 flagged" in seen[0]
    assert "Sure" not in seen[0]  # the generated attack text is never printed
