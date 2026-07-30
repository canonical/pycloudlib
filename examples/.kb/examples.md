# Preface

The `examples/` directory holds runnable scripts demonstrating each cloud's API. Read before adding an example; the demo pattern is documented in `examples/base_api.py`.

Read the top-level `.kb/agents.md` file before continuing below.


# Overview

Each cloud has a top-level `examples/<cloud>.py` demonstrating launch, exec, snapshot, and cleanup. `base_api.py` is a shared helper that exercises the `BaseCloud` API surface generically; per-cloud scripts wire a concrete `pycloudlib.<Cloud>` client into it.


# Important

- New examples should follow the `base_api.py` shape: construct a cloud client with a tag and config, call `exercise_api`, and let the cloud's context manager clean up. Avoid ad-hoc cleanup that diverges from the library's intended usage.
- Examples are imported by `tox -e mypy` (`mypy pycloudlib examples`) and by `tox -e ruff`, so they must stay ruff-clean and type-check.
- `examples/oracle/` contains OCI-specific multi-instance demos; the top-level `oracle.py` is the basic single-instance demo. Mirror this split if a cloud needs both.
- Examples use `#cloud-config` user-data for cloud-init; keep cloud-config hermetic and idempotent.