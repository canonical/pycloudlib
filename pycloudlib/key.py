# This file is part of pycloudlib. See LICENSE file for license information.
"""Base Key Class."""

import os
from typing import Optional

from pycloudlib.errors import UnsetSSHKeyError


class KeyPair:
    """Key Class."""

    def __init__(
        self,
        public_key_path: Optional[str],
        private_key_path: Optional[str] = None,
        name: Optional[str] = None,
    ):
        """Initialize key class to generate key or reuse existing key.

        The public key path is given then the key is stored and the
        private key is assumed to be named the same minus '.pub'
        otherwise the user should also specify the private key path.

        Args:
            public_key_path: Path to public key
            private_key_path: Path to private key
            name: Name to reference key by in clouds
        """
        self.name = name
        self.public_key_path = public_key_path

        # don't set private key path if public key path is None (ssh key is unset)
        if self.public_key_path is None:
            self.private_key_path = None
            return

        self.private_key_path = private_key_path or self.public_key_path.replace(".pub", "")

        # Expand user paths after setting private key path
        self.public_key_path = os.path.expanduser(self.public_key_path)
        self.private_key_path = os.path.expanduser(self.private_key_path)

    def __str__(self):
        """Create string representation of class."""
        return "KeyPair({}, {}, name={})".format(
            self.private_key_path, self.public_key_path, self.name
        )

    @property
    def public_key_content(self):
        """Read the contents of the public key.

        Returns:
            str: The public key content
        """
        if self.public_key_path is None:
            raise UnsetSSHKeyError()
        return open(self.public_key_path, encoding="utf-8").read()
