PYTHON = python3
SETUP  := $(PYTHON) setup.py

.PHONY: build clean install publish source test venv

build:
	$(SETUP) build

clean:
	$(SETUP) clean
	rm -rf .tox .eggs *.egg-info build dist venv
	@find . -regex '.*\(__pycache__\|\.py[co]\)' -delete

install:
	$(SETUP) install

publish:
	rm -rf dist/
	$(SETUP) sdist
	twine upload dist/*

source:
	$(SETUP) sdist

test:
	$(SETUP) check -r -s
	tox

venv:
	$(PYTHON) -m virtualenv -p /usr/bin/$(PYTHON) venv
	venv/bin/pip install -Ur requirements.txt
	@echo "Now run the following to activate the virtual env:"
	@echo ". venv/bin/activate"
