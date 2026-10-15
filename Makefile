# One command per demo beat. Needs a filled-in .env (see .env.example).
export PYTHONPATH := $(CURDIR)
# garak writes reports under $(XDG_DATA_HOME)/garak
export XDG_DATA_HOME := $(CURDIR)/reports

.PHONY: install test scan scan-broad

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
