install-dev:		## Install development dependencies
	pip install .[test]
	pip install -r requirements.txt
	pip install flit

install:		## Install
	pip install .

test:			## Run unit tests
	python setup.py build_ext --inplace
	coverage run --debug config -m pytest tests

lint:			## Run lint checks
	mypy --show-error-codes
	flake8 esg tests
	black esg tests --check
	isort esg tests --check-only
	python -m tools.cli_usage --check

test-all: lint test	## Run unit tests and lint check

format:			## Format code according to lint checks
	autoflake --remove-all-unused-imports --recursive --remove-unused-variables --in-place esg tests --exclude=__init__.py
	black esg tests
	isort esg tests
	python -m tools.cli_usage

generate-readme:	## Generate README
	python ./scripts/docs.py generate-readme

docs-build:		## Build docs
	python ./scripts/docs.py build-all

docs-live:		## Start docs server
	cd docs/; mkdocs serve --dev-addr 0.0.0.0:8008

help:
	@fgrep -h "##" $(MAKEFILE_LIST) | fgrep -v fgrep | sed -e 's/\\$$//' | sed -e 's/##//'

build:		## Build
	python setup.py sdist bdist_wheel
	twine check dist/*
	mkdocs build

coverage:	## Coverage
	coverage report --show-missing --skip-covered --fail-under=95
