"""The Makefile is the demo's command surface, so it gets guards (an escaped \\t once made a target a silent no-op)."""
import re
from pathlib import Path

ROOT = Path(__file__).parent.parent
MAKEFILE = (ROOT / "Makefile").read_text()
TARGETS = set(re.findall(r"^([A-Za-z][\w-]*):", MAKEFILE, flags=re.M))


def test_recipes_start_with_a_real_tab():
    assert not [l for l in MAKEFILE.splitlines() if l.startswith("\\t")], "a recipe line starts with a literal backslash-t"


def test_every_phony_name_has_a_rule():
    phony = set(re.search(r"^\.PHONY:(.*)$", MAKEFILE, flags=re.M).group(1).split())
    assert phony - TARGETS == set(), f"declared .PHONY but no rule: {sorted(phony - TARGETS)}"


def test_every_rule_is_declared_phony():
    phony = set(re.search(r"^\.PHONY:(.*)$", MAKEFILE, flags=re.M).group(1).split())
    assert TARGETS - phony == set(), f"rule not in .PHONY: {sorted(TARGETS - phony)}"


def test_every_make_command_in_the_readme_exists():
    named = set(re.findall(r"`make ([a-z][a-z-]*)", (ROOT / "README.md").read_text()))
    assert named - TARGETS == set(), f"README names missing targets: {sorted(named - TARGETS)}"
