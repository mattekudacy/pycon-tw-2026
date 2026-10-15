"""Pass-rate gate. LLM outputs are nondeterministic, so CI gates on RATES with thresholds from
redteam/thresholds.yaml instead of a single pass/fail.

    python -m redteam.gate --tier pr_gate --target rag_bot \
        --junit reports/junit.xml --deepteam reports/deepteam/rag_bot-small-baseline.json

Exit 0 = within thresholds, 1 = below a threshold (or too many errored cases), 2 = bad input.
Errored deepteam cases are gated separately because deepteam's own overview drops them.
"""
import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

THRESHOLDS = Path(__file__).parent / "thresholds.yaml"


def junit_rate(path: Path) -> tuple[int, int]:
    """(passed, total) over executed tests; skipped tests are excluded, xfail counts as skipped."""
    root = ET.parse(path).getroot()
    suites = [root] if root.tag == "testsuite" else root.findall("testsuite")
    total = failed = skipped = 0
    for s in suites:
        total += int(s.get("tests", 0))
        failed += int(s.get("failures", 0)) + int(s.get("errors", 0))
        skipped += int(s.get("skipped", 0))
    ran = total - skipped
    return ran - failed, ran


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="pr_gate")
    ap.add_argument("--target", required=True)
    ap.add_argument("--junit", type=Path)
    ap.add_argument("--deepteam", type=Path)
    args = ap.parse_args()

    cfg = yaml.safe_load(THRESHOLDS.read_text())[args.tier]
    problems, lines = [], []

    if args.junit:
        passed, ran = junit_rate(args.junit)
        need = cfg["regression_min_pass_rate"][args.target]
        rate = passed / ran if ran else 0.0
        lines.append(f"regressions  {passed}/{ran} = {rate:.0%} (min {need:.0%})")
        if ran == 0 or rate < need:
            problems.append("regression pass rate below threshold")

    if args.deepteam:
        if not args.deepteam.exists():
            print(f"missing deepteam report {args.deepteam}", file=sys.stderr)
            return 2
        s = json.loads(args.deepteam.read_text())["summary"]
        rate = s["passed"] / s["scored"] if s["scored"] else 0.0
        err = s["errored"] / s["total_cases"] if s["total_cases"] else 1.0
        need, max_err = cfg["deepteam_min_pass_rate"][args.target], cfg["deepteam_max_error_rate"]
        lines.append(f"deepteam     {s['passed']}/{s['scored']} = {rate:.0%} (min {need:.0%})")
        lines.append(f"deepteam err {s['errored']}/{s['total_cases']} = {err:.0%} (max {max_err:.0%})")
        if rate < need:
            problems.append("deepteam pass rate below threshold")
        if err > max_err:
            problems.append("too many errored deepteam cases (the pass rate is not trustworthy)")

    report = [f"## Gate: {args.target} ({args.tier})", *[f"- {l}" for l in lines]]
    report.append("- **FAIL**: " + "; ".join(problems) if problems else "- **PASS**")
    print("\n".join(report))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
