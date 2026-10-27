# Preface

QEMU backend specifics for `pycloudlib.qemu`. Read before editing `qemu/`; for config keys and constructor kwargs read `qemu/cloud.py` and `pycloudlib.toml.template`.

Read the top-level `.kb/agents.md` file before continuing below.


# Overview

`Qemu(BaseCloud)` manages **local** QEMU VMs from cloud images (no cloud account); `QemuInstance(BaseInstance)` controls a running VM via the QMP socket (`qemu.qmp`). It requires `qemu-system-x86_64`, `qemu-img`, and `genisoimage` on PATH and uses local directories for images and working files.


# Important

- Missing prerequisites (`qemu-system-x86_64`/`qemu-img`/`genisoimage` on PATH) raise `MissingPrerequisiteError` at init with the Ubuntu apt hint. `image_dir` must be a valid existing path (`ValueError` otherwise).
- mypy: handled via `qemu.qmp`; `pycloudlib.qemu` is NOT in the relaxed-typing TODO overrides — keep it typed.


# Architecture

- QEMU uses no remote cloud API: `launch` builds a disk from `image_dir`, attaches a cloud-init ISO (genisoimage), starts `qemu-system-x86_64` with port-forwarded SSH, and returns a `QemuInstance` connected via QMP. A per-session `parent_dir` (`working_dir / pycl-qemu-{tag}`) holds all artifacts; `qemu/util.py` provides `get_free_port`.
- Despite the local transport, `QemuInstance` exposes the standard `BaseInstance` SSH/exec/`Result` surface (SSH over the forwarded port) so cloud-agnostic callers work unchanged — see `.kb/ssh-and-instances.md`.
- `clean()` extends `BaseCloud.clean()` to remove the per-session `parent_dir` artifacts.