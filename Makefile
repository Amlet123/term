PYTHON ?= python3
ARGS ?=

.PHONY: run test lint

run:
	$(PYTHON) src/terminalus.py $(ARGS)

test:
	$(PYTHON) -m unittest discover -s tests -t . -v

lint:
	$(PYTHON) -m flake8 --max-line-length=80 src tests
