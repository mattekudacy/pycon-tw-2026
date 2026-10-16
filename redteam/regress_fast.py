"""`make regress-fast`: the deterministic security regressions as a table you can read from the back
of a room. Same tests as `pytest tests/regressions -m security`; only the output differs.

    FAIL  injection  How long does shipping take?       No Injected Link (LLM01)
"""
import contextlib
import io
import os
import re
import sys

os.environ.setdefault("DEEPEVAL_TELEMETRY_OPT_OUT", "YES")

import pytest  # noqa: E402

RED, GREEN, BOLD, END = "\033[31m", "\033[32m", "\033[1m", "\033[0m"


class Table:
    def __init__(self):
        self.rows = []

    def pytest_runtest_logreport(self, report):
        if report.when == "call" or (report.when == "setup" and report.outcome != "passed"):
            kind = "injection" if "injection" in report.nodeid else "pii" if "pii" in report.nodeid else "other"
            question = report.nodeid.split("[", 1)[-1].rstrip("]")
            metric = ""
            if report.failed:
                m = re.search(r"Metrics: (.+?) \(score", str(report.longrepr))
                metric = m.group(1) if m else "see pytest -v"
            self.rows.append((report.outcome, kind, question, metric))


def main() -> int:
    table = Table()
    buffer = io.StringIO()  # pytest's own output is replaced by the table below
    with contextlib.redirect_stdout(buffer):
        code = pytest.main(["tests/regressions", "-m", "security", "-q", "-p", "no:cacheprovider",
                            "--tb=no", "--no-header"], plugins=[table])
    if not table.rows:
        print(buffer.getvalue())
        print("NO TESTS RAN: this is an error, not a pass.")
        return 2
    tty = sys.stdout.isatty()
    paint = lambda text, color: f"{color}{BOLD}{text}{END}" if tty else text  # noqa: E731
    print("\nSECURITY REGRESSIONS (rag_bot)\n")
    for outcome, kind, question, metric in table.rows:
        word = paint("PASS", GREEN) if outcome == "passed" else paint("FAIL", RED) if outcome == "failed" else "SKIP"
        print(f"  {word}  {kind:9} {question:32} {metric}")
    n_fail = sum(r[0] == "failed" for r in table.rows)
    n_pass = sum(r[0] == "passed" for r in table.rows)
    n_skip = len(table.rows) - n_fail - n_pass
    print(f"\n  {n_fail} FAIL   {n_pass} PASS" + (f"   {n_skip} SKIPPED (model API unavailable)" if n_skip else ""))
    return int(code)


if __name__ == "__main__":
    sys.exit(main())
