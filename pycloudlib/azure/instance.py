# This file is part of pycloudlib. See LICENSE file for license information.
"""Azure instance."""

import time
from typing import List, Optional

from pycloudlib.errors import PycloudlibTimeoutError
from pycloudlib.instance import BaseInstance


class AzureInstance(BaseInstance):
    """Azure backed instance."""

    _type = "azure"

    def __init__(
        self, key_pair, client, instance, *, username: Optional[str] = None
    ):
        """Set up instance.

        Args:
            key_pair: SSH key object
            client: Azure compute management client
            instance: created azure instance object
            username: username to use when connecting via SSH
        """
        super().__init__(key_pair, username=username)

        self._client = client
        self._instance = instance
        self.boot_timeout = 300
        self.status = "active"

    def wait_for_delete(self):
        """Wait for instance to be deleted."""
        raise NotImplementedError

    def wait_for_stop(self):
        """Wait for instance stop."""
        for _ in range(100):
            power_state = (
                self._client.virtual_machines.get(
                    resource_group_name=self._instance["rg_name"],
                    vm_name=self.name,
                    expand="instanceView",
                )
                .instance_view.statuses[1]
                .display_status
            )
            if power_state == "VM stopped":
                return
            time.sleep(1)
        raise PycloudlibTimeoutError

    @property
    def image_id(self):
        """Return the image_id from which this instance was created."""
        storage_profile = (
            self._instance["vm"].as_dict().get("storage_profile", {})
        )
        image_ref = storage_profile.get("image_reference", {})

        if image_ref:
            return ":".join(
                [
                    image_ref.get("publisher", "").lower(),
                    image_ref.get("offer", ""),
                    image_ref.get("sku", ""),
                    image_ref.get("version", ""),
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
        return getattr(image_profile, "sku", "")

    @property
    def offer(self):
        """Return instance sku."""
        image_profile = self._instance["vm"].storage_profile.image_reference
        return getattr(image_profile, "offer", "")

    def shutdown(self, wait=True, **kwargs):
        """Shutdown the instance.

        Args:
            wait: wait for the instance shutdown
        """
        shutdown = self._client.virtual_machines.begin_power_off(
            resource_group_name=self._instance["rg_name"], vm_name=self.name
        )

        if wait:
            shutdown.wait()

    def generalize(self):
        """Set the OS state of the instance to generalized."""
        self._client.virtual_machines.generalize(
            resource_group_name=self._instance["rg_name"], vm_name=self.name
        )

    def start(self, wait=True):
        """Start the instance.

        Args:
            wait: wait for the instance to start.
        """
        start = self._client.virtual_machines.begin_start(
            resource_group_name=self._instance["rg_name"], vm_name=self.name
        )

        if wait:
            start.wait()
            self.wait()

    def _do_restart(self, **kwargs):
        """Restart the instance."""
        self._client.virtual_machines.begin_restart(
            resource_group_name=self._instance["rg_name"], vm_name=self.name
        )

    # pylint: disable=broad-except
    def delete(self, wait=True) -> List[Exception]:
        """Delete instance."""
        if self.status == "deleted":
            return []
        try:
            poller = self._client.virtual_machines.begin_delete(
                resource_group_name=self._instance["rg_name"],
                vm_name=self.name,
            )

            if wait:
                poller.wait(timeout=300)
                if not poller.done():
                    return [
                        PycloudlibTimeoutError(
                            "Resource not deleted after 300 seconds"
                        )
                    ]
            self.status = "deleted"
        except Exception as e:
            return [e]

        return []
