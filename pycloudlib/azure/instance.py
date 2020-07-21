# This file is part of pycloudlib. See LICENSE file for license information.
"""Azure instance."""

import string
import time

from paramiko.ssh_exception import (
    SSHException
)

from pycloudlib.instance import BaseInstance


class AzureInstance(BaseInstance):
    """Azure backed instance."""

    _type = 'ec2'

    def __init__(self, key_pair, instance, ip_address):
        """Set up instance.

        Args:
            key_pair: SSH key object
            instance: created azure instance object
            ip_address: the ip_address used by this instance
        """
        super(AzureInstance, self).__init__(key_pair)

        self._instance = instance
        self._ip = ip_address
        self.boot_timeout = 300

    @property
    def ip(self):
        """Return IP address of instance."""
        return self._ip
