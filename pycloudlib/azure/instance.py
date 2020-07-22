# This file is part of pycloudlib. See LICENSE file for license information.
"""Azure instance."""

from pycloudlib.instance import BaseInstance


class AzureInstance(BaseInstance):
    """Azure backed instance."""

    _type = 'ec2'

    def __init__(self, client, key_pair, instance):
        """Set up instance.

        Args:
            client: Azure compute management client
            key_pair: SSH key object
            instance: created azure instance object
        """
        super(AzureInstance, self).__init__(key_pair)

        self._client = client
        self._instance = instance
        self.boot_timeout = 300

    @property
    def ip(self):
        """Return IP address of instance."""
        return self._instance["ip_address"]

    @property
    def instance_name(self):
        """Return instance name."""
        return self._instance["vm"].name

    @property
    def id(self):
        """Return instance id."""
        return self._instance["vm"].id

    def shutdown(self, wait=False):
        """Shutdown the instance.

        Args:
            wait: wait for the instance shutdown
        """
        shutdown = self._client.virtual_machines.power_off(
            resource_group_name=self._instance["rg_name"],
            vm_name=self.instance_name
        )

        if wait:
            shutdown.wait()

    def generalize(self):
        """Set the OS state of the instance to generalized."""
        self._client.virtual_machines.generalize(
            resource_group_name=self._instance["rg_name"],
            vm_name=self.instance_name
        )

    def start(self, wait=False):
        """Start the instance.

        Args:
            wait: wait for the instance to start.
        """
        start = self._client.virtual_machines.start(
            resource_group_name=self._instance["rg_name"],
            vm_name=self.instance_name
        )

        if wait:
            start.wait()
