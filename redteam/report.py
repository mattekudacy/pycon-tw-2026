"""Print one summary of the garak and deepteam reports, and write it to reports/summary.md.

    python -m redteam.report                      # live reports in reports/
    python -m redteam.report --prebaked           # the saved before/after-fix reports
    python -m redteam.report --deepteam FILE ...  # specific deepteam files

Failures are marked with the word FAIL, not only a colour, so it reads from the back of a room.
"""
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
REPORTS = ROOT / "reports"


def garak_rows(path: Path) -> list[dict]:
    rows = []
    for line in path.read_text().splitlines():
        e = json.loads(line)
        if e.get("entry_type") == "eval":
            rows.append(e)
    return rows


def deepteam_rows(path: Path) -> tuple[dict, list[dict]]:
    d = json.loads(path.read_text())
    return d["summary"], d["overview"]["vulnerability_type_results"]


def pct(n: int, d: int) -> str:
    return f"{n / d:.0%}" if d else "n/a"


def build(garak_files: list[Path], deepteam_files: list[Path]) -> list[str]:
    out: list[str] = []
    for f in garak_files:
        out += [f"## garak: {f.name}", "", "| probe | detector | passed | failed | rate | |", "|---|---|---|---|---|---|"]
        for e in garak_rows(f):
            tot = e["total_evaluated"]
            out.append(
                f"| {e['probe']} | {e['detector']} | {e['passed']} | {e['fails']} | "
                f"{pct(e['passed'], tot)} | {'FAIL' if e['fails'] else 'ok'} |"
            )
        out.append("")
    for f in deepteam_files:
        s, vulns = deepteam_rows(f)
        out += [
            f"## deepteam: {f.name}",
            "",
            f"target **{s['target']}**: {s['passed']}/{s['scored']} passed "
            f"({pct(s['passed'], s['scored'])}), {s['failed']} failed, {s['errored']} errored, {s['seconds']}s",
            "",
            "| vulnerability | type | passed | failed | rate | |",
            "|---|---|---|---|---|---|",
        ]
        for v in vulns:
            n = v["passing"] + v["failing"]
            out.append(
                f"| {v['vulnerability']} | {v['vulnerability_type']} | {v['passing']} | {v['failing']} | "
                f"{pct(v['passing'], n)} | {'FAIL' if v['failing'] else 'ok'} |"
            )
        out.append("")
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--prebaked", action="store_true", help="use reports/prebaked/ instead of live reports")
    ap.add_argument("--garak", type=Path, nargs="*")
    ap.add_argument("--deepteam", type=Path, nargs="*")
    ap.add_argument("--out", type=Path, default=REPORTS / "summary.md")
    args = ap.parse_args()

    if args.prebaked:
        garak = []
        deepteam = sorted((REPORTS / "prebaked").glob("*deepteam.json"))
    else:
        garak = args.garak if args.garak is not None else sorted((REPORTS / "garak" / "runs").glob("*.report.jsonl"))
        deepteam = args.deepteam if args.deepteam is not None else sorted((REPORTS / "deepteam").glob("*.json"))
    if not garak and not deepteam:
        print("no reports found. Run `make scan` / `make attack` first, or `python -m redteam.report --prebaked`.")
        return 2

    lines = ["# Red-team summary", ""] + build(garak, deepteam)
    text = "\n".join(lines)
    print(text)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text + "\n")
    print(f"written to {args.out.relative_to(ROOT) if args.out.is_relative_to(ROOT) else args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
