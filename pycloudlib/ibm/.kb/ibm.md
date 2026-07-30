# Preface

IBM VPC backend specifics for `pycloudlib.ibm`. Read before editing `ibm/`; for config keys, constructor kwargs, and method behavior read `ibm/cloud.py`, `ibm/instance.py`, and `pycloudlib.toml.template`.

Read the top-level `.kb/agents.md` file before continuing below.


# Overview

`IBM(BaseCloud)` authenticates to IBM Cloud VPC via an IAM API key (`ibm-vpc` SDK + `ibm_platform_services` for resource groups); `IBMInstance(BaseInstance)` wraps a VPC instance. IBM supports custom VPC creation/reuse and a resource-group model.


# Important

- **The `ibm-vpc` API version is pinned** in `ibm/cloud.py` (`VpcV1(..., version=...)` plus a `set_service_url` per region), and the SDK upper bound is constrained in `pyproject.toml` (`ibm-vpc >= 0.10, < 0.29.0`). When updating: check the SDK releases and update **both** the version string and the `<` upper bound together.
- `resource_group_id` and `vpc` are lazy properties (looked up on first access); a missing resource group raises `IBMException`. See `ibm/cloud.py` for the `from_existing`/`from_default` VPC selection.
- `ibm/_util.py` provides the iteration/wait helpers used across the backend; `ibm/errors.py` defines `IBMException`.
- mypy: `ibm_vpc.*`/`ibm_cloud_sdk_core.*`/`ibm_platform_services.*` are in `ignore_missing_imports`; `pycloudlib.ibm.instance` has `check_untyped_defs = false` (TODO overrides in `pyproject.toml`).


# Architecture

- `IAMAuthenticator(api_key)` authenticates both `VpcV1` and `ResourceManagerV2`. The `VPC` helper (in `ibm/instance.py`) pairs the IBM VPC resource with the resolved resource-group id, region, and zone; floating IPs are selected by `floating_ip_substring` when provided.
- `clean()` extends `BaseCloud.clean()` to tear down `created_vpcs`/`created_keys`.