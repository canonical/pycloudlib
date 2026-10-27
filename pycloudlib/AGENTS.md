# Preface

This directory is the `pycloudlib` Python package. Its root modules define the cross-cutting abstractions and helpers shared by every cloud backend; each `<cloud>/` subpackage implements a concrete backend. Read this when working on the abstract API or shared infrastructure, or before navigating into a specific backend.

Read the top-level `.kb/agents.md` file before continuing below.


# Overview

The package root holds the abstract base classes (`cloud.py`, `instance.py`), configuration (`config.py`), SSH keys (`key.py`), command results (`result.py`), the exception hierarchy (`errors.py`), release/utility helpers (`util.py`), and constants (`constants.py`). Concrete backends live in subpackages and are re-exported from `__init__.py`.


# Directory

- `__init__.py` - Re-exports the concrete cloud classes; this is the public API surface (read it for the `__all__` list).
- `cloud.py` - `BaseCloud` ABC and the `ImageType` enum (see `.kb/cloud-abstraction.md` for the architectural intent).
- `instance.py` - `BaseInstance` ABC (SSH exec, file transfer, lifecycle, snapshotting).
- `config.py` - TOML config parsing (`Config`, `parse_config`, `CONFIG_PATHS`); see `.kb/configuration.md`.
- `key.py` - `KeyPair` (SSH key paths, name, content).
- `result.py` - `Result` (the exec return type, a `str` subclass); see `.kb/ssh-and-instances.md`.
- `errors.py` - Root `PycloudlibException` hierarchy; each cloud may add its own `errors.py`.
- `util.py` - Release maps (`UBUNTU_RELEASE_VERSION_MAP`, `LTS_RELEASES`), `subp`, shell/tag helpers.
- `constants.py` - Shared constants (e.g. `LOCAL_UBUNTU_ARCH`).
- `azure/`, `ec2/`, `gce/`, `ibm/`, `ibm_classic/`, `lxd/`, `oci/`, `openstack/`, `qemu/`, `vmware/` - Backend subpackages; each has its own `.kb/<cloud>.md` knowledge note.
- `py.typed` - PEP 561 marker enabling type-checker consumption of the package.


# Documents

- `azure/.kb/azure.md` - Azure backend specifics (config keys, clients, gotchas).
- `ec2/.kb/ec2.md` - EC2 backend specifics, including VPC handling.
- `gce/.kb/gce.md` - GCE backend specifics.
- `ibm/.kb/ibm.md` - IBM VPC backend specifics.
- `ibm_classic/.kb/ibm-classic.md` - IBM Classic backend specifics.
- `lxd/.kb/lxd.md` - LXD backend specifics (containers vs VMs).
- `oci/.kb/oci.md` - OCI backend specifics.
- `openstack/.kb/openstack.md` - Openstack backend specifics.
- `qemu/.kb/qemu.md` - QEMU backend specifics.
- `vmware/.kb/vmware.md` - VMWare backend specifics.
