# Preface

Azure backend specifics for `pycloudlib.azure`. Read before editing `azure/`; for config keys, constructor kwargs, and image dicts read `azure/cloud.py` and `pycloudlib.toml.template`.

Read the top-level `.kb/agents.md` file before continuing below.


# Overview

`Azure(BaseCloud)` uses the Azure mgmt SDK with service-principal credentials; `AzureInstance(BaseInstance)` wraps a compute VM plus its network interface. Azure has the richest `ImageType` flavor support (generic, minimal, Pro, Pro FIPS, Pro FIPS Updates, CVM).


# Important

- Credentials can be obtained via `az ad sp create-for-rbac --sdk-auth`; otherwise read from `~/.azure`. See `pycloudlib.toml.template` `[azure]` for the required/optional keys.
- Image selection dispatches `ImageType` to module-level URN dicts in `cloud.py`; when adding a release, update every relevant dict rather than relying on a single map.
- mypy has `check_untyped_defs = false` for `pycloudlib.azure.cloud`/`instance` (see the TODO overrides in `pyproject.toml`); prefer fixing typing over widening this.


# Architecture

- Three SDK clients are constructed (`ComputeManagementClient`/`NetworkManagementClient`/`ResourceManagementClient`); the instance holds the compute + network clients and created VM/NIC objects. Helpers (security profile models, API version constants, nested-update util) live in `azure/security_types.py` and `azure/util.py`.
- Resources are tagged with `self.tag` and grouped under a resource group (`azure/util.py` `AzureParams`); `clean()` extends `BaseCloud.clean()` for Azure-specific teardown.
- The Azure SDK HTTP logging policy is silenced to reduce noise.