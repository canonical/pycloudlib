# Preface

The `docs/` tree is the user-facing Sphinx documentation (distinct from the agent-oriented `.kb/` knowledge base). Read before editing docs or the Sphinx build; for config read `docs/conf.py` and `docs/index.rst`.

Read the top-level `.kb/agents.md` file before continuing below.


# Overview

Sphinx builds MyST Markdown (`.md`) and reStructuredText (`.rst`) into the published docs at pycloudlib.readthedocs.io. Per-cloud guides live in `docs/clouds/*.md`; API autodoc stubs in `docs/source/pycloudlib.<module>.rst`; the index/config in `docs/index.rst`/`docs/conf.py`.


# Important

- Build with `tox -e docs` (separate env because it `cd`s into `docs/`); it runs `sphinx-build ... -W`, so **warnings are errors** — a missing autodoc target or broken cross-reference fails the build.
- Prefer **Markdown** for new prose docs (per `docs/contributing.md`); use `.rst` only where Sphinx autodoc tooling expects it.
- The `.kb/` knowledge base and `AGENTS.md` files are NOT part of the Sphinx toctree (they live outside `docs/` and are agent-oriented only); do not link them from `docs/index.rst`.
- `docs/_build/` is generated output — never edit it (cleaned by `make -C docs clean` / root `make clean`).


# Architecture

- `index.rst` defines the toctree (read it for the exact groups); `docs/clouds/*` and `docs/examples/*` are globs that pick up new files automatically, so adding a cloud's `docs/clouds/<cloud>.md` and `docs/source/pycloudlib.<cloud>.*.rst` is sufficient for autodoc.
- `docs/conf.py` inserts `..` into `sys.path` so autodoc can import `pycloudlib`; do not break that path setup. `docs/_static/`/`docs/_templates/` hold theme assets.