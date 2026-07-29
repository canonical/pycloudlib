# Preface

SSH key handling, paramiko usage in `BaseInstance`, and the `Result` exec model. Read when debugging instance connectivity or key wiring; for signatures and defaults read `instance.py`/`key.py`/`result.py` directly.

Read the top-level `.kb/agents.md` file before continuing below.


# Overview

`BaseInstance` reaches instances over SSH via paramiko using a `KeyPair`; commands return a `Result`. SSH clients are lazily opened and reused for the instance lifetime.


# Important

- Do not log or echo key material. `KeyPair.__str__` includes paths but not key contents; preserve that boundary when handling keys.
- `Result` is a `str` subclass whose string value is stdout, so `bool(result)` reflects success and `if not result:` detects failure. See `result.py` for the full attribute surface; do not assume attributes beyond what's defined there.
- Backends that do not use paramiko for transport (LXD: `lxc` CLI via `subp`; QEMU: QMP socket; VMWare: `govc`) still expose the same `execute`/`run`/`Result` surface for cloud-agnostic callers, translating their transport into a `Result`. See each `pycloudlib/<cloud>/.kb/<cloud>.md`.


# Architecture

- `BaseInstance` holds cached, lazily-initialized `_ssh_client`/`_sftp_client` reused across `execute`/`run`/file transfer; the connect logic (with its paramiko exception handling and `boot_timeout`/`ready_timeout` retry) lives in `instance.py`.
- `BaseCloud` builds `self.key_pair` in `__init__` from config (`public_key_path`/`private_key_path`/`key_name`); `KeyPair` path/`public_key_content`/`UnsetSSHKeyError` behavior is defined in `key.py`. A cloud may expose `use_key(...)` to swap keys at runtime — consult the cloud's `cloud.py`.