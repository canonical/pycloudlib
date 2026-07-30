# Preface

Openstack backend specifics for `pycloudlib.openstack`. Read before editing `openstack/`; for config keys and constructor kwargs read `openstack/cloud.py` and `pycloudlib.toml.template`.

Read the top-level `.kb/agents.md` file before continuing below.


# Overview

`Openstack(BaseCloud)` authenticates via `openstacksdk` (`openstack.connect()`), relying on pre-configured `OS_*` env vars or `clouds.yaml`; `OpenstackInstance(BaseInstance)` wraps a compute instance. Openstack is a private-cloud backend with no canonical Ubuntu image catalog.


# Important

- `released_image`/`daily_image` raise `PycloudlibError` and `image_serial` raises `NotImplementedError` because Openstack deployments have no guaranteed Ubuntu image catalog. Cloud-agnostic code must tolerate this (see `examples/base_api.py`, which falls back from `released_image` to `daily_image` on `NotImplementedError`).
- Auth is delegated entirely to openstacksdk (`OS_*` env vars or `clouds.yaml` — see the openstacksdk config docs); only `network` is required in pycloudlib config.
- **SDK version is constrained** in `pyproject.toml` (`openstacksdk >= 1.1.0, < 1.5.0`, `python-openstackclient >= 5.2.1`); do not bump without testing.
- mypy: openstacksdk is imported but not in `ignore_missing_imports`; if typing breaks, add `openstack.*` to the overrides rather than relaxing the module. `openstack/errors.py` defines `OpenStackFlavorNotFound` (inheriting `PycloudlibException`).


# Architecture

- `self.conn = openstack.connect()` performs the connection at init; network name → id resolution lives in `_get_network_id()` (network-not-found → `NetworkNotFoundError`).
- `clean()` extends `BaseCloud.clean()` for any Openstack-specific tracked resources.