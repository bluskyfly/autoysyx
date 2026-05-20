.PHONY: help bootstrap run resume status test reproduce clean

PY ?= python3

help:
	@echo "autoysyx targets:"
	@echo "  make bootstrap   - Install toolchain + clone YSYX repos + write env-lock"
	@echo "  make run         - Run the orchestrator (resume from last state)"
	@echo "  make resume      - Alias for run"
	@echo "  make status      - Print task status table"
	@echo "  make test        - Run pytest self-checks (under 2 minutes)"
	@echo "  make reproduce   - Run orchestrator on a fresh state.db (smoke check)"
	@echo "  make clean       - Remove caches, keep ysyx-workbench/ + state.db"

bootstrap:
	$(PY) -m orchestrator.main bootstrap

run:
	$(PY) -m orchestrator.main run

resume:
	$(PY) -m orchestrator.main resume

status:
	$(PY) -m orchestrator.main status

test:
	pytest -q

reproduce:
	rm -f orchestrator/state.db
	$(PY) -m orchestrator.main run --max-tasks 1

clean:
	rm -rf .pytest_cache __pycache__ orchestrator/__pycache__ \
	       tests/__pycache__ .humanize/ /tmp/autoysyx-* /tmp/difftest-*.log
