# Preface

OCI (Oracle Cloud Infrastructure) backend specifics for `pycloudlib.oci`. Read before editing `oci/`; for config keys and constructor kwargs read `oci/cloud.py` and `pycloudlib.toml.template`.

Read the top-level `.kb/agents.md` file before continuing below.


# Overview

`OCI(BaseCloud)` authenticates via the `oci` python SDK reading pycloudlib.toml oci.confg_path value or falling back to `~/.oci/config` (CLI or SDK initialized), a config dict, or env vars; `OciInstance(BaseInstance)` wraps a compute instance. OCI uses availability domains, compartments, and VCNs.


# Important

- The OCI CLI must be initialized first (see the launch doc referenced in `oci/cloud.py`'s docstring). `compartment_id` falls back to `oci iam compartment get` via the CLI; failure raises `CloudSetupError`.
- Auth precedence: `config_dict` (validated via `oci.config.validate_config`) > env vars (`parse_oci_config_from_env_vars`) > `config_path` (default `~/.oci/config`). Passing `profile` alongside `config_dict` logs a warning and ignores the profile.
- `oci/utils.py` provides subnet lookup and `wait_till_ready`; `vcn_name` selects a VCN by exact name, else the newest VCN in the compartment is used.
- mypy: `oci.*` is in `ignore_missing_imports` (`pyproject.toml`); the module has `# pylint: disable=E1101` due to dynamic OCI SDK attributes.


# Architecture

- The resolved OCI config dict (`self.oci_config`) drives all SDK clients; `get_instance` builds an `OciInstance` with the resolved network/subnet id.
- `clean()` extends `BaseCloud.clean()` for any OCI-specific tracked resources.
