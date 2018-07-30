# This file is part of pycloudlib. See LICENSE file for license information.
"""Base Key Class."""

import logging
import os

from pycloudlib.exceptions import SSHKeyExistsError
from pycloudlib.util import subp


class KeyPair:
    """Key Class."""

    def __init__(self, name, public_key_path=None):
        """Initialize key class to generate key or reuse existing key.

        The public key path is given then the key is stored and the
        private key is assumed to be named the same minus '.pub'.

        Can be used to generate keys if no public key path is a folder.

        Args:
            name: generic name to reference key by
            public_key_path: Path to public key, if none generate a key
            key_path: Path to use for generating keys
        """
        self._log = logging.getLogger(__name__)

        self.name = name
        self.public_key_path = public_key_path
        if not public_key_path or os.path.isdir(public_key_path):
            self.public_key_path = self.generate_key_pair(public_key_path)

        self.private_key_path = self.public_key_path.replace('.pub', '')

    @property
    def public_key_content(self):
        """Read the contents of the public key.

        Returns:
            output of public key

        """
        return open(self.public_key_path).read()

    def generate_key_pair(self, key_path=os.path.curdir,
                          algorithm='rsa', bits='4096'):
        """Generate key pair to connect to instances.

        Args:
            key_path: path where the file should get generated
            algorithm: default rsa, algorithm to use
            bits: default 4096, bits to use

        Returns:
            file path to generate keys

        """
        filename = os.path.join(key_path, '%s_id_rsa' % self.name)
        if os.path.exists(filename):
            raise SSHKeyExistsError

        subp(['ssh-keygen', '-t', algorithm, '-b', bits,
              '-f', filename, '-P', '', '-C', self.name])

        return filename
