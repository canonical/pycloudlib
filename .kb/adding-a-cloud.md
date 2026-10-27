# Preface

End-to-end checklist for adding a new cloud backend to pycloudlib. Read before starting a new backend; cross-reference `.kb/cloud-abstraction.md` for the contract.

Read the top-level `.kb/agents.md` file before continuing below.


# Overview

A new backend is a subpackage under `pycloudlib/<cloud>/` providing a concrete `BaseCloud` subclass and a concrete `BaseInstance` subclass, wired into the public API, build, config template, docs, examples, and tests. Each step below mirrors how existing backends are structured.


# Important

1. **Subpackage** `pycloudlib/<cloud>/` with `__init__.py`, `cloud.py` (`<Cloud>(BaseCloud)`), `instance.py` (`<Cloud>Instance(BaseInstance)`). Add `errors.py`/`util.py` only if needed; cloud-specific exceptions MUST inherit from `PycloudlibException` (root in `pycloudlib/errors.py`).
2. **Implement every abstract method** of `BaseCloud` and `BaseInstance` (read `cloud.py`/`instance.py` for the list). If a method is genuinely unsupported, raise `PycloudlibError` (see `Openstack.released_image`).
3. **Register the class** in `pycloudlib/__init__.py` (import + `__all__` entry).
4. **Add SDK deps** to `pyproject.toml` `[project.dependencies]` and, if the SDK lacks type stubs, add it to the `[[tool.mypy.overrides]] ignore_missing_imports` list. Prefer strict typing where possible.
5. **Config template**: add a `[<cloud>]` section to `pycloudlib.toml.template` mirroring constructor kwargs; uncommented keys = required. Update `.kb/configuration.md` if precedence behavior changes.
6. **Docs**: add `docs/clouds/<cloud>.md` (user-facing) and `docs/source/pycloudlib.<cloud>.*.rst` per module (Sphinx autodoc). Add the cloud to the `docs/clouds` toctree glob if not already covered by `clouds/*`.
7. **Example**: add `examples/<cloud>.py` demonstrating launch/snapshot/cleanup. See `examples/.kb/examples.md`.
8. **Tests**: add `tests/unit_tests/<cloud>/` with mocked SDK tests (CI runs these). Add `tests/integration_tests/<cloud>/` for live tests, gated by pytest markers `ci`/`main_check` as appropriate (see `tests/.kb/testing.md`).
9. **Knowledge base**: create `pycloudlib/<cloud>/.kb/<cloud>.md` capturing config keys, SDK auth flow, cloud-specific methods, and gotchas; link it from `pycloudlib/AGENTS.md` _Documents_.
10. **Verify**: `tox -e ruff`, `tox -e mypy`, `tox -e py38` (or `make test`), and `tox -e docs` (Sphinx with `-W` treats warnings as errors, so missing autodoc targets will fail the build).


# Architecture

For the abstract contract each backend must satisfy, read `cloud.py`/`instance.py` directly and see `.kb/cloud-abstraction.md` for the architectural intent. The steps above are the wiring checklist around that contract; this article intentionally does not restate the API surface.
