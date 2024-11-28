# This file is part of pycloudlib. See LICENSE file for license information.
"""Base class for all other clouds to provide consistent set of functions."""

import enum
import getpass
import io
import logging
import os
import re
from abc import ABC, abstractmethod
from typing import Any, List, MutableMapping, Optional, Sequence

import paramiko

from pycloudlib.config import ConfigFile, parse_config
from pycloudlib.errors import (
    CleanupError,
    InvalidTagNameError,
    PycloudlibError,
)
from pycloudlib.instance import BaseInstance
from pycloudlib.key import KeyPair
from pycloudlib.util import (
    get_timestamped_tag,
    log_exception_list,
)

_RequiredValues = Optional[Sequence[Optional[Any]]]


@enum.unique
class ImageType(enum.Enum):
    """Allowed image types when launching cloud images."""

    GENERIC = "generic"
    MINIMAL = "minimal"
    PRO = "Pro"
    PRO_FIPS = "Pro FIPS"


class BaseCloud(ABC):
    """Base Cloud Class."""

    _type = "base"

    def __init__(
        self,
        tag: str,
        timestamp_suffix: bool = True,
        config_file: Optional[ConfigFile] = None,
        required_values: Optional[_RequiredValues] = None,
    ):
        """Initialize base cloud class.

        Args:
            tag: string used to name and tag resources with
            timestamp_suffix: Append a timestamped suffix to the tag string.
            config_file: path to pycloudlib configuration file
        """
        self.created_instances: List[BaseInstance] = []
        self.created_images: List[str] = []

        self._log = logging.getLogger("{}.{}".format(__name__, self.__class__.__name__))
        self.config = self._check_and_get_config(config_file, required_values)

        self.tag = get_timestamped_tag(tag) if timestamp_suffix else tag
        self._validate_tag(self.tag)

        self.key_pair = self._get_ssh_keys(
            public_key_path=self.config.get("public_key_path", ""),
            private_key_path=self.config.get("private_key_path", ""),
            name=self.config.get("key_name", getpass.getuser()),
        )

    def __enter__(self):
        """Enter context manager for this class."""
        return self

    def __exit__(self, _type, _value, _trackback):
        """Cleanup context manager for this class."""
        exceptions = self.clean()
        log_exception_list(exceptions)
        if exceptions:
            raise CleanupError(exceptions)

    @abstractmethod
    def delete_image(self, image_id: str, **kwargs):
        """Delete an image.

        Args:
            image_id: string, id of the image to delete
            **kwargs: dictionary of other arguments to pass to delete_image
        """
        raise NotImplementedError

    @abstractmethod
    def released_image(self, release, **kwargs):
        """ID of the latest released image for a particular release.

        Args:
            release: The release to look for

        Returns:
            A single string with the latest released image ID for the
            specified release.

        """
        raise NotImplementedError

    @abstractmethod
    def daily_image(self, release: str, **kwargs):
        """ID of the latest daily image for a particular release.

        Args:
            release: The release to look for

        Returns:
            A single string with the latest daily image ID for the
            specified release.

        """
        raise NotImplementedError

    @abstractmethod
    def image_serial(self, image_id):
        """Find the image serial of the latest daily image for a particular release.

        Args:
            image_id: string, Ubuntu image id

        Returns:
            string, serial of latest image

        """
        raise NotImplementedError

    def get_image_id_from_name(self, name: str) -> str:
        """
        Get the id of the first image whose name contains the given name.

        The name does not need to be an exact match, just a substring of
        the image name.

        Args:
            name: string, name of the image to search for

        Returns:
            string, image ID
        """
        raise NotImplementedError

    @abstractmethod
    def get_instance(
        self, instance_id, *, username: Optional[str] = None, **kwargs
    ) -> BaseInstance:
        """Get an instance by id.

        Args:
            instance_id: ID identifying the instance
            username: username to use when connecting via SSH

        Returns:
            An instance object to use to manipulate the instance further.

        """
        raise NotImplementedError

    @abstractmethod
    def launch(
        self,
        image_id: str,
        instance_type=None,
        user_data=None,
        **kwargs,
    ) -> BaseInstance:
        """Launch an instance.

        Args:
            image_id: string, image ID to use for the instance
            instance_type: string, type of instance to create
            user_data: used by cloud-init to run custom scripts/configuration
            username: username to use when connecting via SSH
            **kwargs: dictionary of other arguments to pass to launch

        Returns:
            An instance object to use to manipulate the instance further.

        """
        raise NotImplementedError

    @abstractmethod
    def snapshot(self, instance, clean=True, **kwargs):
        """Snapshot an instance and generate an image from it.

        Args:
            instance: Instance to snapshot
            clean: run instance clean method before taking snapshot

        Returns:
            An image id

        """
        raise NotImplementedError

    # pylint: disable=broad-except
    def clean(self) -> List[Exception]:
        """Cleanup ALL artifacts associated with this Cloud instance.

        This includes all instances, snapshots, resources, etc.
        To ensure cleanup isn't interrupted, any exceptions raised during
        cleanup operations will be collected and returned.
        """
        exceptions: List[Exception] = []
        for instance in self.created_instances:
            try:
                instance.delete()
            except Exception as e:
                exceptions.append(e)
        for image_id in self.created_images:
            try:
                self.delete_image(image_id)
            except Exception as e:
                exceptions.append(e)
        return exceptions

    def list_keys(self):
        """List ssh key names present on the cloud for accessing instances.

        Returns:
           A list of strings of key pair names accessible to the cloud.

        """
        raise NotImplementedError

    def create_key_pair(self):
        """Create and set a ssh key pair for a cloud instance.

        Returns:
            A tuple containing the public and private key created
        """
        key = paramiko.RSAKey.generate(4096)
        priv_str = io.StringIO()

        pub_key = "{} {}".format(key.get_name(), key.get_base64())
        key.write_private_key(priv_str, password=None)

        return pub_key, priv_str.getvalue()

    def use_key(self, public_key_path, private_key_path=None, name=None):
        """Use an existing key.

        Args:
            public_key_path: path to the public key to upload
            private_key_path: path to the private key
            name: name to reference key by
        """
        self._log.debug("using SSH key from %s", public_key_path)
        self.key_pair = self._get_ssh_keys(
            public_key_path=public_key_path,
            private_key_path=private_key_path,
            name=name,
        )

    def _check_and_get_config(
        self,
        config_file: Optional[ConfigFile],
        required_values: _RequiredValues,
    ) -> MutableMapping[str, Any]:
        """Set pycloudlib configuration.

        Checks if values required to launch a cloud instance are present.
        Values should be present in pycloudlib config file or passed to the
        cloud's constructor directly.

        Args:
            config_file: path to pycloudlib configuration file
            required_values: a list containing all the required values for
                the cloud that were passed to the cloud's constructor
        """
        # if all required values were passed to the cloud's constructor,
        # there is no need to parse the config file. If some (but not all)
        # of them were provided, config file is loaded and the values that
        # were passed in work as overrides
        if required_values and all(v is not None for v in required_values):
            return {}
        return parse_config(config_file)[self._type]

    @staticmethod
    def _validate_tag(tag: str):
        """
        Ensure that this tag is a valid name for cloud resources.

        Rules:
        - All letters must be lowercase
        - Must be between 1 and 63 characters long
        - Must not start or end with a hyphen
        - Must be alphanumeric and hyphens only

        :param tag: tag to validate

        :raises InvalidTagNameError: if the tag is invalid
        """
        rules_failed = []
        # all letters must be lowercase
        if any(c.isupper() for c in tag):
            rules_failed.append("All letters must be lowercase")
        # must be between 1 and 63 characters long
        if len(tag) < 1 or len(tag) > 63:
            rules_failed.append("Must be between 1 and 63 characters long")
        # must not start or end with a hyphen
        if tag and (tag[0] in ("-") or tag[-1] in ("-")):
            rules_failed.append("Must not start or end with a hyphen")
        # must be alphanumeric and hyphens only
        if not re.match(r"^[a-z0-9-]*$", tag):
            rules_failed.append("Must be alphanumeric and hyphens only")

        if rules_failed:
            raise InvalidTagNameError(tag=tag, rules_failed=rules_failed)

    def _get_ssh_keys(
        self,
        public_key_path: Optional[str] = None,
        private_key_path: Optional[str] = None,
        name: Optional[str] = None,
    ) -> KeyPair:
        """Retrieve SSH key pair paths.

        This method attempts to retrieve the paths to the public and private SSH keys.
        If no public key path is provided, it will look for default keys in the user's
        `~/.ssh` directory. If no keys are found, it logs a warning and returns a KeyPair
        with None values.

        Args:
            public_key_path (Optional[str]): The path to the public SSH key. If not provided,
                the method will search for default keys.
            private_key_path (Optional[str]): The path to the private SSH key. Defaults to None.
            name (Optional[str]): An optional name for the key pair. Defaults to None.

        Returns:
            KeyPair: An instance of KeyPair containing the paths to the public and private keys,
            and the optional name.

        Raises:
            PycloudlibError: If the provided public key path does not exist.
        """
        possible_default_keys = [
            os.path.expanduser("~/.ssh/id_rsa.pub"),
            os.path.expanduser("~/.ssh/id_ed25519.pub"),
        ]
        public_key_path = os.path.expanduser(public_key_path or "")
        if not public_key_path:
            for pubkey in possible_default_keys:
                if os.path.exists(pubkey):
                    self._log.info("No public key path provided, using: %s", pubkey)
                    public_key_path = pubkey
                    break
            if not public_key_path:
                self._log.warning(
                    "No public key path provided and no key found in default locations: "
                    "'~/.ssh/id_rsa.pub' or '~/.ssh/id_ed25519.pub'. SSH key authentication will "
                    "not be possible unless a key is later provided with the 'use_key' method."
                )
                return KeyPair(None, None, None)
        if not os.path.exists(os.path.expanduser(public_key_path)):
            raise PycloudlibError(f"Provided public key path '{public_key_path}' does not exist")
        if public_key_path not in possible_default_keys:
            self._log.info("Using provided public key path: '%s'", public_key_path)

        return KeyPair(
            public_key_path=public_key_path,
            private_key_path=private_key_path,
            name=name,
        )
