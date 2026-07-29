# Preface

LXD backend specifics for `pycloudlib.lxd`. Read before editing `lxd/`; for class structure and method behavior read `lxd/cloud.py`, `lxd/instance.py`, `lxd/_images.py`.

Read the top-level `.kb/agents.md` file before continuing below.


# Overview

LXD is a **local** backend (containers and VMs, not a public cloud) exposed as three classes: `LXDContainer` (preferred) and `LXDVirtualMachine` share a `_BaseLXD(BaseCloud)`; `LXD` is a deprecated alias of `LXDContainer`. Operations shell out to the `lxc` CLI via `pycloudlib.util.subp` — there is no SDK.


# Important

- `LXD` emits a deprecation warning ("use `LXDContainer` instead"); use `LXDContainer`/`LXDVirtualMachine` in new code.
- Ensure the LXD daemon is initialized (`lxd init`) and the user has access. The `[lxd]` config section in `pycloudlib.toml.template` has no required keys.
- mypy: LXD modules are NOT in the relaxed-typing TODO overrides; keep them typed.


# Architecture

- All cloud operations are `subp(["lxc", ...])` calls, often parsing `--format yaml` output via `yaml.safe_load`; there is no remote API client. Image discovery (fingerprints/serials, honoring `ImageType`) lives in `lxd/_images.py`; profile defaults in `lxd/defaults.py`.
- `LXDInstance`/`LXDVirtualMachineInstance` expose the standard `BaseInstance` `execute`/`run`/`Result` surface via `lxc exec`/`lxc file` (not paramiko) — see `.kb/ssh-and-instances.md` for the cross-cloud contract. `get_instance` returns the configured `_lxd_instance_cls`, enabling the container-vs-VM split.
- `clean()` extends `BaseCloud.clean()` to delete `created_snapshots`/`created_profiles`, tolerating "not found" errors.