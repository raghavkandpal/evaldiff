PYTHON ?= python3
TEST ?=

.PHONY: context test check

# Session start (AGENTS.md "Git and GitHub workflow"): fetch so ahead/behind is current.
context:
	@git fetch -q origin
	@git status --short --branch

test:
	$(PYTHON) -m unittest $(if $(TEST),$(TEST),discover -s tests) -q

check: test
	git diff --check
