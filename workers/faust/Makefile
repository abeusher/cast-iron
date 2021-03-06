SHELL := /bin/bash

.PHONY: $(SERVICES) logs

## NOTE: Add this to your .bashrc to enable make target tab completion
##    complete -W "\`grep -oE '^[a-zA-Z0-9_.-]+:([^=]|$)' ?akefile | sed 's/[^a-zA-Z0-9_.-]*$//'\`" make
## Reference: https://stackoverflow.com/a/38415982

help: ## This info
	@echo '_________________'
	@echo '| Make targets: |'
	@echo '-----------------'
	@echo
	@cat Makefile | grep -E '^[a-zA-Z\/_-]+:.*?## .*$$' | awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
	@echo


build:
	docker build -t cast-iron/workers/faust .

nag: lint type sort test ## Run all checks

lint: ## Run pylint over the main project files
	pylint python_worker

sort: ## Sort files
	isort -rc python_worker tests

test: ## Run integration tests
	coverage run --source python_worker -m pytest
	coverage report -m
	coverage html -d tests/htmlcov

type: ## Run mypy
	mypy python_worker --ignore-missing-imports --follow-imports=skip
