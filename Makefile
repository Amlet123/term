PYTHON ?= python3

.PHONY: run test lint

run:
	$(PYTHON) src/terminalus.py

test:
	$(PYTHON) -m unittest discover -s tests -t . -v

lint:
	$(PYTHON) -m flake8 --max-line-length=80 src tests
