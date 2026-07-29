# Preface

Architectural intent behind the `BaseCloud` / `BaseInstance` abstractions in `pycloudlib/cloud.py` and `pycloudlib/instance.py`. Read before auditing cross-cloud behavior or deciding where new functionality belongs; for the concrete method list and signatures, read the base classes directly.

Read the top-level `.kb/agents.md` file before continuing below.


# Overview

`BaseCloud` and `BaseInstance` are ABCs defining a uniform surface every backend implements. The point of the abstraction is that cloud-agnostic callers work unchanged across backends; backends subclass and add cloud-specific helpers without exposing backend-specific shapes to generic code.


# Important

- Read `cloud.py` and `instance.py` for the authoritative abstract method list and `__init__` signatures — they are the source of truth and this note intentionally does not restate them.
- Both base classes are context managers whose `__exit__` calls cleanup and raises `CleanupError` on failure. `CleanupError` usually means leaked resources — do not silently swallow it.
- Backends track created instances/images in `created_instances`/`created_images` and extend `clean()` (calling `super().clean()` first) for cloud-specific resources (e.g. EC2 VPCs/keys, LXD profiles/snapshots). Generic `launch`/`snapshot` callers rely on this tracking for automatic cleanup.
- `ImageType` (in `cloud.py`) dispatches image flavors on clouds that support them (Azure, EC2, GCE, LXD); other clouds accept and ignore it via `**kwargs`.
- Not every abstract method is meaningfully supported by every cloud: some raise `PycloudlibError` (e.g. `Openstack.released_image`/`daily_image`) or fall back to a sibling (e.g. `IBMClassic.daily_image` → `released_image`). Cloud-agnostic code must tolerate this.
- The `_type` class attribute identifies the backend for logging and helpers.


# Architecture

- `BaseInstance` exec is paramiko-based for most clouds, but LXD/QEMU/VMWare translate a non-SSH transport (the `lxc` CLI, a QMP socket, `govc`) into the same `execute`/`run`/`Result` surface. See `.kb/ssh-and-instances.md` for the `Result`/paramiko model.
- Tag validation lives in `BaseCloud._validate_tag` with per-cloud override rules; invalid tags raise `InvalidTagNameError(tag, rules_failed)`.
- Configuration is resolved in `BaseCloud.__init__` and shared with instances via the `key_pair`; see `.kb/configuration.md` for precedence.