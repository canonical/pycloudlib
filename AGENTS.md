# Preface

pycloudlib is a Python library (Python >=3.8) that launches, interacts with, and snapshots Ubuntu cloud instances across many public and private clouds through a uniform `BaseCloud` / `BaseInstance` abstraction. This file is relevant to any task touching the source tree, build, tests, docs, or examples.

Read the top-level `.kb/agents.md` file before continuing below.


# Overview

The package supports Azure, EC2, GCE, IBM VPC, IBM Classic, LXD (containers and VMs), OCI, Openstack, QEMU, and VMWare. Each cloud lives in its own subpackage under `pycloudlib/<cloud>/` and implements the abstract API defined in `pycloudlib/cloud.py` and `pycloudlib/instance.py`. The library is consumed both as a library (via `pycloudlib` top-level exports) and via the example scripts under `examples/`.


# Architecture

- `BaseCloud` (`pycloudlib/cloud.py`) and `BaseInstance` (`pycloudlib/instance.py`) define the abstract contract every backend satisfies; read them for the method list, and see `.kb/cloud-abstraction.md` for architectural intent.
- Each `<cloud>` subpackage provides a concrete cloud class and instance class plus optional helpers (`vpc.py`, `util.py`, `errors.py`, `_util.py`).
- Cross-cutting modules live at the package root: `config.py` (TOML config), `key.py` (`KeyPair`), `result.py` (`Result`), `errors.py` (root exception hierarchy), `util.py` (release maps, shell helpers), `constants.py`.
- Configuration is layered: constructor kwargs > `pycloudlib.toml` (see `pycloudlib.toml.template`) > cloud SDK defaults / env vars; see `.kb/configuration.md`.

See `.kb/cloud-abstraction.md` for the abstract API surface agents should rely on, and each `pycloudlib/<cloud>/.kb/<cloud>.md` for backend-specific behavior and gotchas.


# Directory

- `pycloudlib/` - The Python package; see `pycloudlib/AGENTS.md` for module-level detail.
- `tests/` - Unit tests (`unit_tests/`, run in CI) and integration tests (`integration_tests/`, require live cloud credentials). See `tests/AGENTS.md`.
- `examples/` - Runnable scripts demonstrating each cloud's API. See `examples/.kb/examples.md`.
- `docs/` - Sphinx user-facing documentation (MyST Markdown + reStructuredText). See `docs/.kb/documentation.md`.
- `pyproject.toml` - Build (hatchling), dependencies, ruff/mypy/pytest config.
- `tox.ini` - Tox environments: `ruff`, `mypy`, `py38`/`py310`/`py312` (pytest), `format`, `docs`, `integration-tests*`.
- `Makefile` - Thin wrappers around `uv` (`build`, `install`, `test`, `venv`, `clean`).
- `pycloudlib.toml.template` - Reference template for the per-cloud config file users copy to `~/.config/pycloudlib.toml` or `/etc/pycloudlib.toml`.
- `VERSION` - Single-line version read by hatchling.
- `uv.lock` - Locked dependency set for the `uv` workflow.


# Documents

- `.kb/agents.md` - General rules for the knowledge base reading and writing.
- `.kb/development.md` - Dev environment, lint/typecheck/test commands, and Python version coverage.
- `.kb/configuration.md` - `pycloudlib.toml` resolution precedence and per-cloud required keys.
- `.kb/cloud-abstraction.md` - The `BaseCloud` / `BaseInstance` contract agents should rely on across backends.
- `.kb/ssh-and-instances.md` - SSH key handling, paramiko usage, and the `Result` exec model.
- `.kb/adding-a-cloud.md` - Steps to add a new cloud backend end-to-end.
