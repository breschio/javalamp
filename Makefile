.PHONY: help install reinstall uninstall run list test

PYTHON ?= $(shell if [ -x .venv/bin/python ]; then echo .venv/bin/python; else echo python; fi)
JAVALAMP ?= $(shell if command -v javalamp >/dev/null 2>&1; then echo javalamp; elif [ -x .venv/bin/javalamp ]; then echo .venv/bin/javalamp; else echo javalamp; fi)

help:
	@echo "javalamp shortcuts"
	@echo "  make install    Install globally with pipx"
	@echo "  make reinstall  Reinstall globally after local edits"
	@echo "  make run        Run javalamp"
	@echo "  make list       List scenes"
	@echo "  make test       Run tests"
	@echo "  make uninstall  Remove the global pipx install"

install:
	@command -v pipx >/dev/null 2>&1 || { echo "pipx is required. Install it with: brew install pipx"; exit 1; }
	pipx install .

reinstall:
	@command -v pipx >/dev/null 2>&1 || { echo "pipx is required. Install it with: brew install pipx"; exit 1; }
	pipx install . --force

uninstall:
	pipx uninstall javalamp

run:
	$(JAVALAMP)

list:
	$(JAVALAMP) -l

test:
	$(PYTHON) -m pytest -q
