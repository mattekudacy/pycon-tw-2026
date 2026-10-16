"""The gate decides what CI means, so it gets tests (no LLM)."""
import json
import subprocess
import sys

JUNIT = """<testsuite tests="{n}">{cases}</testsuite>"""
OK, BAD = '<testcase name="t{i}"/>', '<testcase name="t{i}"><failure message="x"/></testcase>'
DOWN = '<testcase name="t{i}"><skipped message="Skipped: LLM unavailable"/></testcase>'


def run(tmp_path, cases, deepteam=None, target="rag_bot"):
    junit = tmp_path / "junit.xml"
    junit.write_text(JUNIT.format(n=len(cases), cases="".join(c.format(i=i) for i, c in enumerate(cases))))
    cmd = [sys.executable, "-m", "redteam.gate", "--target", target, "--junit", str(junit)]
    if deepteam:
        f = tmp_path / "dt.json"
        f.write_text(json.dumps({"summary": deepteam}))
        cmd += ["--deepteam", str(f)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    return r.returncode, r.stdout


def test_all_pass(tmp_path):
    assert run(tmp_path, [OK] * 4)[0] == 0


def test_real_failure_is_a_fail_not_inconclusive(tmp_path):
    code, out = run(tmp_path, [OK, OK, OK, BAD])
    assert code == 1 and "FAIL" in out and "INCONCLUSIVE" not in out


def test_api_down_for_most_tests_is_inconclusive(tmp_path):
    code, out = run(tmp_path, [OK, DOWN, DOWN, DOWN])
    assert code == 3 and "INCONCLUSIVE" in out


def test_one_unavailable_test_is_tolerated_but_never_hides_a_failure(tmp_path):
    assert run(tmp_path, [OK] * 7 + [DOWN])[0] == 0
    assert run(tmp_path, [OK] * 6 + [BAD, DOWN])[0] == 1


def test_everything_skipped_is_not_a_pass(tmp_path):
    assert run(tmp_path, [DOWN] * 3)[0] == 3


def test_errored_deepteam_cases_are_inconclusive(tmp_path):
    s = {"target": "rag_bot", "total_cases": 8, "scored": 2, "errored": 6, "passed": 2, "failed": 0}
    code, out = run(tmp_path, [OK] * 4, deepteam=s)
    assert code == 3 and "INCONCLUSIVE" in out
