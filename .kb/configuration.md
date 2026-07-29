# Preface

How pycloudlib resolves per-cloud configuration. Read before changing precedence or debugging "must be defined in pycloudlib.toml" errors; for per-cloud keys read `pycloudlib.toml.template` and each cloud's `__init__` docstring.

Read the top-level `.kb/agents.md` file before continuing below.


# Overview

Configuration is layered: explicit constructor kwargs > `pycloudlib.toml` values > cloud SDK defaults / env vars. `config.py` parses the TOML; `pycloudlib.toml.template` is the authoritative per-cloud key reference.


# Important

- In `pycloudlib.toml.template`, **uncommented keys are required**, commented keys are optional with shown defaults. Do not check a filled-in `pycloudlib.toml` into version control; secrets belong in a secret manager.
- `Config` (in `config.py`) subclasses `dict` only to raise a clearer `KeyError` on missing-key `__getitem__` access; code using `.get(key)` gets `None` and must handle it. Don't rely on this difference leaking into call sites.
- When adding a cloud, add a `[<cloud>]` section to `pycloudlib.toml.template` mirroring its constructor kwargs.


# Architecture

- `parse_config` (in `config.py`) tries, in order: the `config_file` constructor arg > `$PYCLOUDLIB_CONFIG` > `~/.config/pycloudlib.toml` > `/etc/pycloudlib.toml`. First existing, parseable file wins; later paths are not merged. Read `config.py` for the exact `CONFIG_PATHS` list and `ConfigFile` type.
- Each cloud's `__init__` resolves each value as `kwarg or self.config.get("key") or default` before constructing its SDK client; `BaseCloud.required_values` only validates that at least one supplied value is non-None. See each `pycloudlib/<cloud>/.kb/<cloud>.md` for that cloud's auth flow.