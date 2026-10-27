# Preface

IBM Classic backend specifics for `pycloudlib.ibm_classic` (distinct from the IBM VPC backend `pycloudlib.ibm`). Read before editing `ibm_classic/`; for config keys and method behavior read `ibm_classic/cloud.py` and `pycloudlib.toml.template`.

Read the top-level `.kb/agents.md` file before continuing below.


# Overview

`IBMClassic(BaseCloud)` uses the SoftLayer SDK to manage classic (pre-VPC) IBM Cloud virtual servers; `IBMClassicInstance(BaseInstance)` wraps a VSManager virtual guest. This backend has no daily images and uses `globalIdentifier` for image references.


# Important

- **No daily images**: `daily_image` delegates to `released_image` (see `ibm_classic/cloud.py`).
- **`delete_image` expects the integer image ID, not the `globalIdentifier`** returned by `released_image` — translating between the two is the caller's responsibility; a non-int raises `IBMClassicException`. This is a non-obvious footgun unique to this backend.
- Auth requires `username` + `api_key`; missing credentials raise `IBMClassicException`. See `pycloudlib.toml.template` `[ibm_classic]` for keys.
- `ibm_classic/errors.py` defines `IBMClassicException`; mypy: `Softlayer.*` is in `ignore_missing_imports` (`pyproject.toml`).


# Architecture

- A single SoftLayer client is built from env and wrapped by four managers (`VSManager`/`ImageManager`/`SshKeyManager`/`NetworkManager`); `domain_name` is used to construct instance FQDNs.
- `clean()` extends `BaseCloud.clean()` to tear down `created_keys`/`created_security_groups`.