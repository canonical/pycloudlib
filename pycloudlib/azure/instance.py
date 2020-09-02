# This file is part of pycloudlib. See LICENSE file for license information.
"""Azure instance."""

from pycloudlib.instance import BaseInstance


class AzureInstance(BaseInstance):
    """Azure backed instance."""

    _type = 'azure'

    def __init__(self, key_pair, client, instance):
        """Set up instance.

        Args:
            key_pair: SSH key object
            client: Azure compute management client
            instance: created azure instance object
        """
        super().__init__(key_pair)

        self._client = client
        self._instance = instance
        self.boot_timeout = 300
        self.status = "active"

    def wait_for_delete(self):
        """Wait for instance to be deleted."""
        raise NotImplementedError

    def wait_for_stop(self):
        """Wait for instance stop."""
        raise NotImplementedError

    @property
    def image_id(self):
        """Return the image_id from which this instance was created."""
        storage_profile = self._instance['vm'].as_dict().get(
            'storage_profile', {})
        image_ref = storage_profile.get(
            'image_reference', {})

        if image_ref:
            return ":".join(
                [
                    image_ref.get('publisher', '').lower(),
                    image_ref.get('offer', ''),
                    image_ref.get('sku', ''),
                    image_ref.get('version', '')
                ]
            )

        # Snapshot instances will not contain such info. For them, we will
        # return a default string
        return "snapshot-image"

    @property
    def ip(self):
        """Return IP address of instance."""
        return self._instance["ip_address"]

    @property
    def id(self):
        """Return instance id."""
        return self._instance["vm"].id

    @property
    def name(self):
        """Return instance name."""
        return self._instance["vm"].name

    @property
    def sku(self):
        """Return instance sku."""
        image_profile = self._instance["vm"].storage_profile.image_reference
        return getattr(image_profile, 'sku', '')

    @property
    def offer(self):
        """Return instance sku."""
        image_profile = self._instance["vm"].storage_profile.image_reference
        return getattr(image_profile, 'offer', '')

    def shutdown(self, wait=True):
        """Shutdown the instance.

        Args:
            wait: wait for the instance shutdown
        """
        shutdown = self._client.virtual_machines.power_off(
            resource_group_name=self._instance["rg_name"],
            vm_name=self.name
        )

        if wait:
            shutdown.wait()

    def generalize(self):
        """Set the OS state of the instance to generalized."""
        self._client.virtual_machines.generalize(
            resource_group_name=self._instance["rg_name"],
            vm_name=self.name
        )

    def start(self, wait=True):
        """Start the instance.

        Args:
            wait: wait for the instance to start.
        """
        start = self._client.virtual_machines.start(
            resource_group_name=self._instance["rg_name"],
            vm_name=self.name
        )

        if wait:
            start.wait()
            self.wait()

    def restart(self, wait=True):
        """Restart the instance."""
        restart = self._client.virtual_machines.restart(
            resource_group_name=self._instance["rg_name"],
            vm_name=self.name
        )

        if wait:
            restart.wait()
            self.wait()

    def delete(self, wait=True):
        """Delete instance."""
        delete = self._client.virtual_machines.delete(
            resource_group_name=self._instance["rg_name"],
            vm_name=self.name
        )

        if wait:
            delete.wait()

        self.status = "deleted"

    def wait(self):
        """Wait for instance to be up and cloud-init to be complete."""
        self._wait_for_system()

    def console_log(self):
        """Return the instance console log."""
        raise NotImplementedError
