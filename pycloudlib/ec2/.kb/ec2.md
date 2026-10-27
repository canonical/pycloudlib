# Preface

EC2 backend specifics for `pycloudlib.ec2`. Read before editing `ec2/`; for config keys, constructor kwargs, and method behavior read `ec2/cloud.py`, `ec2/instance.py`, and `pycloudlib.toml.template`.

Read the top-level `.kb/agents.md` file before continuing below.


# Overview

`EC2(BaseCloud)` authenticates via boto3/botocore (profile, access key pair, or `~/.aws`) and manages instances plus optional custom VPCs. `EC2Instance(BaseInstance)` wraps a boto3 EC2 resource. EC2 supports `ImageType` flavors and custom VPC creation/reuse via `VPC` (`ec2/vpc.py`).


# Important

- Auth falls back to `~/.aws`; missing region/credentials raise `CloudSetupError` with guidance — read `ec2/util.py` `_get_session` and `ec2/cloud.py` for the resolution flow. See `pycloudlib.toml.template` `[ec2]` for keys.
- `NO_GP3_RELEASES` (in `ec2/cloud.py`) lists releases predating the gp3 disk type; launch logic must respect it when selecting the root volume.
- mypy: boto3/botocore are in the `ignore_missing_imports` overrides (`pyproject.toml`); do not rely on their types without local stubs.


# Architecture

- Two boto3 handles are held: `client` (API calls) and `resource` (ORM-style access); `self.region` is `session.region_name`.
- `clean()` extends `BaseCloud.clean()` to tear down `created_vpcs` and `created_keys` alongside tracked instances/images.
- Image IDs are AWS AMI IDs; image lookups query the Ubuntu public AMI catalog filtered by release/arch/`ImageType`/`include_deprecated` (see `ec2/cloud.py`).