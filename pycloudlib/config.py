"""Deal with configuration file."""
import logging
import os
from io import StringIO
from pathlib import Path
from typing import Any, MutableMapping, Optional, Union

import toml

# Order matters here. Local should take precedence over global.
CONFIG_PATHS = [
    Path("~/.config/pycloudlib.toml").expanduser(),
    Path("/etc/pycloudlib.toml"),
]

ConfigFile = Union[Path, StringIO]
log = logging.getLogger(__name__)


class Config(dict):
    """Override dict to allow raising a more meaningful KeyError."""

    def __getitem__(self, key):
        """Provide more meaningful KeyError on access."""
        try:
            return super().__getitem__(key)
        except KeyError:
            raise KeyError(
                "{} must be defined in pycloudlib.toml to make this "
                "call".format(key)
            ) from None


def parse_config(
    config_file: Optional[ConfigFile] = None,
) -> MutableMapping[str, Any]:
    """Find the relevant TOML, load, and return it."""
    possible_configs = []
    if config_file:
        possible_configs.append(config_file)
    if os.environ.get("PYCLOUDLIB_CONFIG"):
        possible_configs.append(Path(os.environ["PYCLOUDLIB_CONFIG"]))
    possible_configs.extend(CONFIG_PATHS)
    for path in possible_configs:
        try:
            config = toml.load(path, _dict=Config)
            log.debug("Loaded configuration from %s", path)
            return config
        except FileNotFoundError:
            continue
        except toml.TomlDecodeError as e:
            raise ValueError(
                "Could not parse configuration file pointed to by "
                "{}".format(path)
            ) from e
    raise ValueError(
        "No configuration file found! Copy pycloudlib.toml.template to "
        "~/.config/pycloudlib.toml or /etc/pycloudlib.toml"
    )
