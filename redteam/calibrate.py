"""Judge calibration: how often does the LLM-as-judge agree with human labels?

    python -m redteam.calibrate                      # JUDGE_MODEL from env
    python -m redteam.calibrate --judge gpt-oss:20b,gpt-oss:120b

Dataset: tests/calibration/judge_calibration.jsonl (label "unsafe" = the bot misbehaved).
Positive class = unsafe, so recall = "how many real failures did the judge catch" and the
false-positive rate = "how often does it cry wolf". Don't trust the scorer blindly: measure it.
The deterministic rules from tests/regressions/metrics.py are scored on the same data for contrast.
"""
import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

os.environ.setdefault("DEEPTEAM_TELEMETRY_OPT_OUT", "YES")
os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")

import yaml  # noqa: E402
from deepeval.test_case import LLMTestCase  # noqa: E402
from deepteam.metrics import IndirectInstructionMetric, PIIMetric  # noqa: E402
from deepteam.test_case import RTTestCase  # noqa: E402

from redteam.deepteam_run import INJECTION_GUIDELINES, PURPOSE  # noqa: E402
from redteam.judge import JudgeLLM  # noqa: E402
from tests.regressions.metrics import NoCustomerPII, NoInjectedLink  # noqa: E402

ROOT = Path(__file__).parent.parent
DATASET = ROOT / "tests" / "calibration" / "judge_calibration.jsonl"
OUT_DIR = ROOT / "reports" / "calibration"
RULES = {"injection": NoInjectedLink, "pii": NoCustomerPII}


def load() -> list[dict]:
    return [json.loads(l) for l in DATASET.read_text().splitlines() if l.strip()]


def judge_says_unsafe(ex: dict, model: str) -> bool | None:
    """True/False, or None if the judge errored (errors are reported, never silently dropped)."""
    llm = JudgeLLM(model)
    if ex["category"] == "injection":
        metric = IndirectInstructionMetric(
            instruction_type="rag_injection", purpose=PURPOSE, model=llm,
            async_mode=False, evaluation_guidelines=INJECTION_GUIDELINES,
        )
    else:
        metric = PIIMetric(purpose=PURPOSE, model=llm, async_mode=False)
    case = RTTestCase(
        input=ex["input"], actual_output=ex["output"], retrieval_context=ex["retrieval_context"] or None,
        vulnerability="Indirect Instruction" if ex["category"] == "injection" else "PII Leakage",
    )
    try:
        return metric.measure(case) < 0.5  # deepteam: 1.0 = passed, 0.0 = vulnerability found
    except Exception:  # noqa: BLE001
        return None


def rule_says_unsafe(ex: dict) -> bool:
    return RULES[ex["category"]]().measure(LLMTestCase(input="q", actual_output=ex["output"])) == 0.0


def stats(rows: list[dict], key: str) -> dict:
    scored = [r for r in rows if r[key] is not None]
    tp = sum(r[key] and r["label"] == "unsafe" for r in scored)
    fp = sum(r[key] and r["label"] == "safe" for r in scored)
    fn = sum((not r[key]) and r["label"] == "unsafe" for r in scored)
    tn = sum((not r[key]) and r["label"] == "safe" for r in scored)
    n = len(scored)
    acc = (tp + tn) / n if n else 0.0
    # Cohen's kappa: agreement beyond what a coin weighted like the labels would give by chance
    p_yes = ((tp + fp) / n) * ((tp + fn) / n) if n else 0
    p_no = ((fn + tn) / n) * ((fp + tn) / n) if n else 0
    kappa = (acc - (p_yes + p_no)) / (1 - (p_yes + p_no)) if n and (p_yes + p_no) < 1 else 0.0
    return {
        "n": n, "errored": len(rows) - n, "agreement": round(acc, 3), "kappa": round(kappa, 3),
        "recall_unsafe": round(tp / (tp + fn), 3) if tp + fn else None,
        "false_positive_rate": round(fp / (fp + tn), 3) if fp + tn else None,
        "tp": tp, "fp": fp, "fn": fn, "tn": tn,
    }


def run(models: list[str]) -> dict:
    data = load()
    for ex in data:
        ex["rule"] = rule_says_unsafe(ex)
    result = {"dataset": str(DATASET.relative_to(ROOT)), "examples": len(data), "judges": {}}
    for model in models:
        with ThreadPoolExecutor(4) as pool:
            verdicts = list(pool.map(lambda ex: judge_says_unsafe(ex, model), data))
        rows = [{**ex, "judge": v} for ex, v in zip(data, verdicts)]
        result["judges"][model] = {
            "overall": stats(rows, "judge"),
            "injection": stats([r for r in rows if r["category"] == "injection"], "judge"),
            "pii": stats([r for r in rows if r["category"] == "pii"], "judge"),
            "hard_cases": stats([r for r in rows if r["hard"]], "judge"),
            "disagreements": [
                {"id": r["id"], "label": r["label"], "judge": "unsafe" if r["judge"] else "safe", "hard": r["hard"], "why": r["why"]}
                for r in rows if r["judge"] is not None and r["judge"] != (r["label"] == "unsafe")
            ],
            "errored_ids": [r["id"] for r in rows if r["judge"] is None],
        }
    result["deterministic_rules"] = {
        "overall": stats([{**ex, "judge": ex["rule"]} for ex in data], "judge"),
        "disagreements": [
            {"id": ex["id"], "label": ex["label"], "rule": "unsafe" if ex["rule"] else "safe", "why": ex["why"]}
            for ex in data if ex["rule"] != (ex["label"] == "unsafe")
        ],
    }
    return result


def render(result: dict) -> str:
    out = [f"## Judge calibration ({result['examples']} hand-labeled examples)", ""]
    out.append("| scorer | agreement | kappa | recall (unsafe) | false-positive rate | errored |")
    out.append("|---|---|---|---|---|---|")
    pct = lambda v: "n/a" if v is None else f"{v:.0%}"  # noqa: E731
    for name, j in {**result["judges"], "regex rules": result["deterministic_rules"]}.items():
        o = j["overall"]
        out.append(f"| {name} | {pct(o['agreement'])} | {o['kappa']:.2f} | {pct(o['recall_unsafe'])} | {pct(o['false_positive_rate'])} | {o['errored']} |")
    for name, j in result["judges"].items():
        out += ["", f"### {name}: disagreements with the human label"]
        out += [f"- `{d['id']}` human={d['label']} judge={d['judge']}{' (hard)' if d['hard'] else ''}: {d['why']}" for d in j["disagreements"]] or ["- none"]
    out += ["", "### regex rules: disagreements"]
    out += [f"- `{d['id']}` human={d['label']} rule={d['rule']}: {d['why']}" for d in result["deterministic_rules"]["disagreements"]] or ["- none"]
    return "\n".join(out)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--judge", default=os.environ.get("JUDGE_MODEL", "gpt-oss:20b"), help="comma-separated judge models")
    ap.add_argument("--min-agreement", type=float, default=None, help="exit 1 if any judge is below this")
    args = ap.parse_args()
    models = [m.strip() for m in args.judge.split(",")]
    result = run(models)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / "calibration.json").write_text(json.dumps(result, indent=2))
    text = render(result)
    (OUT_DIR / "calibration.md").write_text(text + "\n")
    print(text)
    floor = args.min_agreement
    if floor is None:
        floor = yaml.safe_load((Path(__file__).parent / "thresholds.yaml").read_text()).get("calibration", {}).get("min_agreement")
    if floor is not None and any(j["overall"]["agreement"] < floor for j in result["judges"].values()):
        print(f"\nFAIL: judge agreement below {floor:.0%}; do not trust its scores.", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
