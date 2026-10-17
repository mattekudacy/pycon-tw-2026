"""Three short "look inside the library" commands for the live demo. No API key or network needed.

    make peek-garak      the menu of probes garak ships, and how our bot plugs in
    make peek-deepteam   what deepteam is told to attack, and one finding with the judge's reasoning
    make peek-deepeval   the 5-line test, and the assertion it raises when the bot misbehaves

peek-deepteam needs `make attack-before-fix` to have been run once (it reads that report).
It prints the answer and the judge's reason but not the generated attack text.
"""
import ast
import json
import os
import re
import subprocess
import sys
import textwrap
from pathlib import Path

ROOT = Path(__file__).parent.parent
REPORT = ROOT / "reports" / "deepteam" / "rag_bot-small-baseline-undefended.json"
ANSI = re.compile(r"\x1b\[[0-9;]*m")


def wrap(text: str, indent: int = 4, width: int = 100) -> str:
    return textwrap.fill(" ".join(str(text).split()), width=width, initial_indent=" " * indent, subsequent_indent=" " * indent)


def shorten(text: str, limit: int) -> str:
    """Cut at a word boundary and say so, so nothing on screen ends mid-word."""
    text = " ".join(str(text).split())
    return text if len(text) <= limit else text[:limit].rsplit(" ", 1)[0] + " ..."


def source_of(path: Path, name: str) -> str:
    """Source text of a top-level function, decorators included."""
    text = path.read_text()
    node = next(n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef) and n.name == name)
    first = min([node.lineno] + [d.lineno for d in node.decorator_list])
    return "\n".join(text.splitlines()[first - 1 : node.end_lineno])


def garak() -> int:
    out = ANSI.sub("", subprocess.run([sys.executable, "-m", "garak", "--list_probes"], capture_output=True, text=True).stdout)
    # 💤 marks probes garak does not run by default (the slow "Full" variants); count only the active ones
    names = [m.group(1) for line in out.splitlines() if "💤" not in line and (m := re.match(r"probes: (\S+)", line))]
    families = sorted({n.split(".")[0] for n in names})
    probes = [n for n in names if "." in n]
    show = ["promptinject", "dan", "latentinjection", "apikey"]
    print(f"garak 0.17.0 ships {len(families)} probe families and {len(probes)} active probes. A few of them:\n")
    for fam in show:
        mine = [p.split(".", 1)[1] for p in probes if p.startswith(fam + ".")]
        print(f"  {fam:16} {len(mine):2} probes  e.g. {', '.join(m[:34] for m in mine[:2])}")
    info = ANSI.sub("", subprocess.run([sys.executable, "-m", "garak", "--plugin_info", "probes.promptinject.HijackHateHumans"],
                                       capture_output=True, text=True).stdout)
    desc = next((m.group(1) for m in re.finditer(r"description: (.+)", info)), "").split(" trophy")[0]
    print("\nWhat one probe is (probes.promptinject.HijackHateHumans):\n" + wrap(desc))
    print("\ngarak sees text in, text out. This is all it takes to point it at our bot (redteam/garak_target.py):\n")
    print(textwrap.indent(source_of(ROOT / "redteam" / "garak_target.py", "chatbot"), "  "))
    return 0


def deepteam() -> int:
    sys.path.insert(0, str(ROOT))
    os.environ.setdefault("DEEPTEAM_TELEMETRY_OPT_OUT", "YES")
    os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")
    from redteam.deepteam_run import build

    vulns, attacks = build("rag_bot", False)
    print("deepteam is told what to attack (redteam/deepteam_run.py, build()):\n")
    for v in vulns:
        print(f"  vulnerability: {type(v).__name__:22} types: {', '.join(str(getattr(t, 'value', t)) for t in v.types)}")
    print(f"  attack method: {', '.join(type(a).__name__ for a in attacks)}\n")
    if not REPORT.exists():
        print(f"No report yet. Run `make attack-before-fix` first (it writes reports/deepteam/rag_bot-small-baseline-undefended.json).")
        return 2
    cases = json.loads(REPORT.read_text())["test_cases"]
    bad = sorted((c for c in cases if c.get("score") is not None and c["score"] < 1),
                 key=lambda c: (str(c["vulnerability_type"]), str(c["input"])))
    if not bad:
        print("No failing case in this report.")
        return 0
    c = bad[0]
    print(f"One finding ({len(bad)} of {len(cases)} flagged by the judge):\n")
    print(f"  {c['vulnerability']} / {c['vulnerability_type']}   score {c['score']}  (0 = vulnerable)\n")
    print("  The bot's answer ends:\n" + wrap("... " + " ".join(str(c["actual_output"])[-170:].split(" ")[1:]), 4))
    print("\n  The judge's reasoning (another model scored the answer):\n" + wrap(shorten(c["reason"], 330), 4))
    return 0


def deepeval() -> int:
    test_file = ROOT / "tests" / "regressions" / "test_rag_regressions.py"
    print("A deepeval regression test (tests/regressions/test_rag_regressions.py):\n")
    print(textwrap.indent(source_of(test_file, "case"), "  ") + "\n")
    print(textwrap.indent(source_of(test_file, "test_indirect_injection_does_not_reach_users").replace('@pytest.mark.parametrize("question", SHIPPING, ids=lambda q: SHORT.get(q, q[:36]))', '@pytest.mark.parametrize("question", SHIPPING)'), "  "))
    print("\nRun it with the defenses off:  RAG_DEFENSES=none pytest -k \"shipping and time\"\n")
    env = {**os.environ, "RAG_DEFENSES": "none", "DEEPEVAL_TELEMETRY_OPT_OUT": "YES", "PYTHONPATH": str(ROOT)}
    res = subprocess.run([sys.executable, "-m", "pytest", "tests/regressions", "-k", "shipping and time", "--tb=line", "-q",
                          "-p", "no:cacheprovider"], capture_output=True, text=True, cwd=ROOT, env=env)
    line = next((l for l in res.stdout.splitlines() if l.startswith("E   AssertionError")), "")
    print(wrap(line.replace("E   ", ""), 2, 100) if line else res.stdout[-400:])
    summary = next((l for l in reversed(res.stdout.splitlines()) if "failed" in l or "passed" in l), "")
    print("\n  " + summary)
    return 0


if __name__ == "__main__":
    cmds = {"garak": garak, "deepteam": deepteam, "deepeval": deepeval}
    if len(sys.argv) != 2 or sys.argv[1] not in cmds:
        sys.exit(f"usage: python -m redteam.peek [{'|'.join(cmds)}]")
    sys.exit(cmds[sys.argv[1]]())
