# Preface

The `tests/` tree: unit tests run in CI, integration tests need live cloud credentials. Read before adding or running tests.

Read the top-level `.kb/agents.md` file before continuing below.


# Directory

- `unit_tests/` - Mocked, hermetic tests run in CI via `tox` (`py38`/`py310`/`py312`). Mirrors the `pycloudlib/` layout with a subdir per cloud plus root-level modules.
- `integration_tests/` - Live cloud tests requiring real credentials. Gated by pytest markers; not run by default `tox`. Subdirs: `ec2/`, `gce/`, `ibm/`, `oracle/`.


# Documents

- `.kb/testing.md` - pytest markers, CI environments, and how to run unit vs integration tests.
