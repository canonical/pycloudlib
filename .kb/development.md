# Preface

Dev environment, lint, typecheck, and test commands for pycloudlib. Read before running checks; for env/flag specifics read `tox.ini`, `Makefile`, and `pyproject.toml` directly.

Read the top-level `.kb/agents.md` file before continuing below.


# Overview

pycloudlib uses `uv` (wrapped by a thin `Makefile`) and `tox` for the multi-check workflow. Supported Python range is >=3.8; CI covers 3.8/3.10/3.12. ruff handles lint+format, mypy handles typing, pytest runs unit tests with `--doctest-modules`.


# Important

- After editing any Python in `pycloudlib/` or `examples/`, run ruff and mypy. Prefer `make test` (full tox) or the individual tox envs defined in `tox.ini`.
- Default `tox` envlist only **checks** (does not reformat): `ruff`, `mypy`, `py38`. Use `tox -e format` to apply formatting.
- Unit tests live in `tests/unit_tests/` and run in CI; integration tests in `tests/integration_tests/` need live cloud credentials and are marker-gated (see `tests/.kb/testing.md`).
- New code: prefer Markdown for new docs (per `docs/contributing.md`), follow ruff's pep257 docstring convention, and keep PRs to a single issue.


# Architecture

- `pyproject.toml` is the source of truth for dependencies, ruff/mypy/pytest config, and build (hatchling). mypy has `ignore_missing_imports` overrides for many cloud SDKs and `check_untyped_defs = false` for a known TODO module list — read the `[tool.mypy.overrides]` sections rather than assuming; prefer fixing typing over widening the relaxed list.
- `tox.ini` defines all envs (`pytest`, `py38`/`py310`/`py312`, `mypy`, `ruff`, `format`, `docs`, `integration-tests*`); read it for exact commands/flags.
- `Makefile` wraps `uv` (`build`/`install`/`test`/`venv`/`clean`/`publish`); `uv.lock` pins the dependency set; `VERSION` is read by hatchling.