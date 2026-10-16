"""Pass-rate gate. LLM outputs are nondeterministic, so CI gates on RATES with thresholds from
redteam/thresholds.yaml instead of a single pass/fail.

    python -m redteam.gate --tier pr_gate --target rag_bot \
        --junit reports/junit.xml --deepteam reports/deepteam/rag_bot-small-baseline.json

Exit 0 = within thresholds, 1 = below a threshold, 2 = bad input,
3 = INCONCLUSIVE: too much of the run was infrastructure noise (model API unavailable / deepteam
cases errored) to say anything about the app. Rerun it; do not read it as a regression.
Errored deepteam cases are gated separately because deepteam's own overview drops them.
"""
import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

THRESHOLDS = Path(__file__).parent / "thresholds.yaml"


def junit_rate(path: Path) -> tuple[int, int, int]:
    """(passed, ran, unavailable). `unavailable` = tests skipped because the model API gave no
    reply (see tests/conftest.py); other skips are excluded from `ran` and ignored."""
    root = ET.parse(path).getroot()
    total = failed = skipped = unavailable = 0
    for case in root.iter("testcase"):
        total += 1
        if case.find("failure") is not None or case.find("error") is not None:
            failed += 1
        elif (sk := case.find("skipped")) is not None:
            skipped += 1
            if "LLM unavailable" in (sk.get("message", "") + (sk.text or "")):
                unavailable += 1
    ran = total - skipped
    return ran - failed, ran, unavailable


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--tier", default="pr_gate")
    ap.add_argument("--target", required=True)
    ap.add_argument("--junit", type=Path)
    ap.add_argument("--deepteam", type=Path)
    args = ap.parse_args()

    cfg = yaml.safe_load(THRESHOLDS.read_text())[args.tier]
    problems, inconclusive, lines = [], [], []

    if args.junit:
        passed, ran, unavailable = junit_rate(args.junit)
        need = cfg["regression_min_pass_rate"][args.target]
        rate = passed / ran if ran else 0.0
        seen = ran + unavailable
        down = unavailable / seen if seen else 1.0
        max_down = cfg["max_infra_unavailable_rate"]
        lines.append(f"regressions  {passed}/{ran} = {rate:.0%} (min {need:.0%})")
        lines.append(f"llm unavailable  {unavailable}/{seen} tests = {down:.0%} (max {max_down:.0%})")
        if down > max_down or seen == 0:
            inconclusive.append("the model API was unavailable for too many regression tests")
        elif rate < need:
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
        if err > max_err:
            inconclusive.append("too many errored deepteam cases (the pass rate is not trustworthy)")
        elif rate < need:
            problems.append("deepteam pass rate below threshold")

    report = [f"## Gate: {args.target} ({args.tier})", *[f"- {l}" for l in lines]]
    if inconclusive:
        report.append("- **INCONCLUSIVE**: " + "; ".join(inconclusive) + ". This is infrastructure noise, not a regression: rerun the job.")
    if problems:
        report.append("- **FAIL**: " + "; ".join(problems))
    if not inconclusive and not problems:
        report.append("- **PASS**")
    print("\n".join(report))
    return 1 if problems else 3 if inconclusive else 0

if __name__ == "__main__":
    sys.exit(main())
