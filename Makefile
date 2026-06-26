PYTHON = python3
UV = uv

.PHONY: build clean install publish source test venv

build:
	$(UV) build

clean:
	rm -rf .tox .eggs *.egg-info build dist .venv
	@find . -regex '.*\(__pycache__\|\.py[co]\)' -delete
	$(MAKE) -C docs clean

install:
	$(UV) sync

publish:
	rm -rf dist/
	$(UV) build
	$(UV) run pip install twine
	twine upload dist/*

source:
	$(UV) build

test:
	$(UV) run tox

venv:
	uv sync
	@echo "Now run the following to activate the virtual env:"
	@echo ". .venv/bin/activate"
