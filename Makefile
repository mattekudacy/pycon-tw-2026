# One command per demo beat. Needs a filled-in .env (see .env.example).
export PYTHONPATH := $(CURDIR)
# garak writes reports under $(XDG_DATA_HOME)/garak
export DEEPTEAM_TELEMETRY_OPT_OUT := YES
export DEEPEVAL_TELEMETRY_OPT_OUT := YES
export XDG_DATA_HOME := $(CURDIR)/reports

.PHONY: install test scan scan-broad attack attack-full regress regress-fast

install:
	uv sync

test:
	uv run pytest -q

# Beat: garak against the chatbot. Narrow config, a few minutes live.
# Reports land in reports/garak/runs/. Broad scan: `make scan-broad` (nightly, slow).
scan:
	uv run garak --config redteam/garak_config.yaml

scan-broad:
	uv run garak --config redteam/garak_config_broad.yaml

# Beat: deepteam against the RAG bot. Small batch (baseline probes, no attack enhancement).
# Results: reports/deepteam/rag_bot-small-baseline.json
attack:
	uv run python -m redteam.deepteam_run --target rag_bot --baseline --per-type 3

# Nightly-size run (slow, costs more).
attack-full:
	uv run python -m redteam.deepteam_run --target rag_bot --full

# Beat: deepeval regression tests born from the findings.
# regress-fast = deterministic security checks only (about a second). regress = plus
# faithfulness/relevancy (LLM-judged; ~2.5 min cold, seconds once the cache is warm).
regress-fast:
	uv run pytest tests/regressions -m security -q -p no:cacheprovider

regress:
	uv run pytest tests/regressions -q -p no:cacheprovider
