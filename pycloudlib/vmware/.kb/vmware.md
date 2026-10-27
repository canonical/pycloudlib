# Preface

VMWare backend specifics for `pycloudlib.vmware`. Read before editing `vmware/`; for config keys and constructor kwargs read `vmware/cloud.py` and `pycloudlib.toml.template`.

Read the top-level `.kb/agents.md` file before continuing below.


# Overview

`VMWare(BaseCloud)` shells out to `govc` (the govmomi CLI, not an SDK) against a vSphere endpoint; `VMWareInstance(BaseInstance)` wraps a VM. Image selection maps Ubuntu series to pre-uploaded VM templates.


# Important

- Config mirrors the `GOVC_*` env vars (see `pycloudlib.toml.template` `[vmware]`). Missing `govc` on PATH raises a plain `ValueError` (not a pycloudlib exception) — a known inconsistency to preserve when editing.
- **`delete_image` refuses to delete core templates** (names in `SERIES_TO_TEMPLATE.values()` raise `ValueError`) and tolerates "not found" errors. `daily_image` delegates to `released_image` ("relying on whatever has been created/uploaded").
- mypy: VMWare modules are NOT in the relaxed-typing TODO overrides; keep them typed. There is no `vmware/errors.py` (errors reuse the root `pycloudlib.errors` hierarchy).


# Architecture

- All cloud operations are `govc` CLI invocations via `subprocess.run` with a constructed `GOVC_*` env dict; there is no Python SDK dependency. `folder` is the vSphere folder for both new VMs and template lookup.
- `clean()` extends `BaseCloud.clean()` for any VMWare-specific tracked resources, with the caveat that core templates are never deleted.