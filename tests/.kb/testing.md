# Preface

pytest markers, CI environments, and how to run unit vs integration tests for pycloudlib. Read before running tests; for marker/env specifics read `pyproject.toml` and `tox.ini` directly.

Read the top-level `.kb/agents.md` file before continuing below.


# Overview

Unit tests (`tests/unit_tests/`) are hermetic and mocked, run on every PR across Python 3.8/3.10/3.12. Integration tests (`tests/integration_tests/`) exercise real cloud APIs, require credentials, and are marker-gated; they run in dedicated tox envs, not the default `tox`.


# Important

- Default `tox` envlist is `ruff, mypy, py38` — it does NOT run integration tests. Use `make test` (= `uv run tox`) for the CI-equivalent check.
- Unit tests run with `--doctest-modules`, so docstring doctests in `pycloudlib/` are executed too — keep them hermetic (no network, no real cloud calls). A failing doctest fails the unit test env.
- `integration-tests-main-check` exists because forked PRs can't access GH secrets: cloud-based tests run post-merge on main instead. Prefer the `ci` marker for new integration tests that should gate PRs.
- When adding a cloud, add `tests/unit_tests/<cloud>/` (mocked SDK, runs in CI) and optionally `tests/integration_tests/<cloud>/` (live, marker-gated).


# Architecture

- Unit tests use `pytest-mock`/`mock` to patch SDK clients so no network calls occur; the `mock_ssh_keys` marker centralizes SSH-key mocking across the suite.
- pytest markers and `testpaths` live in `pyproject.toml`; integration tox envs and their flags live in `tox.ini`. CI badges reference `.github/workflows/ci.yaml`; the marker split lets one workflow run different subsets in PR vs post-merge contexts.