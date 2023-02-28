# This file is part of pycloudlib. See LICENSE file for license information.
"""Base Key Class."""

import os


class KeyPair:
    """Key Class."""

    def __init__(self, public_key_path, private_key_path=None, name=None):
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
        if private_key_path:
            self.private_key_path = private_key_path
        else:
            self.private_key_path = self.public_key_path.replace(".pub", "")

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
            output of public key

        """
        return open(self.public_key_path, encoding="utf-8").read()
