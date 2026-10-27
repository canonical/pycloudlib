# Preface

GCE backend specifics for `pycloudlib.gce`. Read before editing `gce/`; for config keys, constructor kwargs, and method behavior read `gce/cloud.py`, `gce/instance.py`, and `pycloudlib.toml.template`.

Read the top-level `.kb/agents.md` file before continuing below.


# Overview

`GCE(BaseCloud)` authenticates via Google service-account/application-default credentials and the `google-cloud-compute` v1 SDK; `GceInstance(BaseInstance)` wraps a compute instance. GCE supports `ImageType` and resolves the project from config/env/`gcloud` CLI as a fallback.


# Important

- Credentials resolve: explicit arg > `$GOOGLE_APPLICATION_CREDENTIALS` > config `credentials_path`. Project resolves: explicit arg > config > `$GOOGLE_CLOUD_PROJECT` > `gcloud config get-value project` (runs the CLI; failure raises `CloudSetupError`). See `gce/cloud.py` and `pycloudlib.toml.template` `[gce]` for keys.
- `gce/errors.py` defines GCE-specific exceptions (inheriting `PycloudlibException`); `gce/util.py` holds `get_credentials`/`raise_on_error` and the `gcloud` fallback.
- mypy: `google.*` is in `ignore_missing_imports` overrides; `pycloudlib.gce.cloud`/`util` have `check_untyped_defs = false` (TODO overrides in `pyproject.toml`) — prefer fixing typing over widening.


# Architecture

- Several v1 clients are constructed (`ImagesClient`/`DisksClient`/`InstancesClient`/operations clients); `self.zone` is the full `{region}-{zone}` string. Snapshot/launch operations poll via the operations clients; the `google.cloud` logger is silenced to reduce noise.
- `clean()` extends `BaseCloud.clean()` for any GCE-specific tracked resources.