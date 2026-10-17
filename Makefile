# One command per demo beat. Needs a filled-in .env (see .env.example).
export PYTHONPATH := $(CURDIR)
# garak writes reports under $(XDG_DATA_HOME)/garak
export DEEPTEAM_TELEMETRY_OPT_OUT := YES
export DEEPEVAL_TELEMETRY_OPT_OUT := YES
export XDG_DATA_HOME := $(CURDIR)/reports

.PHONY: install test scan scan-broad attack attack-before-fix attack-full regress regress-fast agent-test calibrate report report-prebaked compare

install:
	uv sync

test:
	uv run pytest -q

# Beat: garak against the chatbot. Narrow config, a few minutes live.
# Reports land in reports/garak/runs/. Broad scan: `make scan-broad` (nightly, slow).
scan:
	uv run garak --config redteam/garak_config.yaml

scan-broad:
	REDTEAM_MAX_TOKENS=1500 uv run garak --config redteam/garak_config_broad.yaml

# Beat: deepteam against the RAG bot. Small batch (baseline probes, no attack enhancement).
# Results: reports/deepteam/<target>-small-baseline.json
# Your own app: make attack TARGET=my_package.my_module:ask PURPOSE="One sentence about the app."
TARGET ?= rag_bot
PURPOSE ?= A customer-support assistant for AcmeShop that answers order, shipping and return questions.
attack:
	uv run python -m redteam.deepteam_run --target "$(TARGET)" --purpose "$(PURPOSE)" --baseline --per-type 3

# The finding itself: the same attack with the defenses off (= the before-fix behaviour of rag_bot), so the
# poisoned shipping doc still works. Replays from the cache in ~3 s; cold ~1 min.
# Result: reports/deepteam/rag_bot-small-baseline-undefended.json
attack-before-fix:
	RAG_DEFENSES=none uv run python -m redteam.deepteam_run --target rag_bot --purpose "$(PURPOSE)" --baseline --per-type 3 --suffix undefended

# Nightly-size run (slow, costs more).
attack-full:
	uv run python -m redteam.deepteam_run --target rag_bot --full

# Beat: deepeval regression tests born from the findings.
# regress-fast = deterministic security checks only (about a second). regress = plus
# faithfulness/relevancy (LLM-judged; ~2.5 min cold, seconds once the cache is warm).
regress-fast:
	uv run python -m redteam.regress_fast

regress:
	uv run pytest tests/regressions -q -p no:cacheprovider

# Agent tool-call assertions. AGENT_DEFENSES=none make agent-test shows the naive agent failing.
agent-test:
	uv run pytest tests/agent tests/test_agent_policy.py -q -p no:cacheprovider

# Beat: one summary of the garak and deepteam reports (also written to reports/summary.md).
# report-prebaked shows the saved before-fix / after-fix deepteam results.
report:
	uv run python -m redteam.report

report-prebaked:
	uv run python -m redteam.report --prebaked

# How far to trust the LLM judge: agreement with hand-labeled examples (judges set by JUDGE_MODEL,
# or: make calibrate JUDGES=gpt-oss:20b,gpt-oss:120b). Report: reports/calibration/calibration.md
JUDGES ?= $(or $(JUDGE_MODEL),gpt-oss:20b)
calibrate:
	uv run python -m redteam.calibrate --judge $(JUDGES)

# Beat: a SECURITY failure and a QUALITY failure side by side (before-fix behaviour, from the cache).
compare:
	uv run python -m redteam.compare
