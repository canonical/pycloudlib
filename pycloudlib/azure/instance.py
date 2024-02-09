# This file is part of pycloudlib. See LICENSE file for license information.
"""Azure instance."""

import datetime
import time
from typing import Any, Dict, List, Optional

from pycloudlib.errors import PycloudlibError, PycloudlibTimeoutError
from pycloudlib.instance import BaseInstance
from pycloudlib.util import update_nested


class AzureInstance(BaseInstance):
    """Azure backed instance."""

    _type = "azure"

    def __init__(
        self,
        key_pair,
        client,
        instance,
        network_client,
        *,
        username: Optional[str] = None,
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
        self._network_client = network_client
        self._instance = instance
        self.boot_timeout = 300
        self.status = "active"

    def wait_for_delete(self):
        """Wait for instance to be deleted."""
        raise NotImplementedError

    def wait_for_stop(self, **kwargs):
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

    @property
    def location(self) -> str:
        """Return instance location."""
        return self._instance["vm"].location

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

    def add_network_interface(self) -> str:
        """Add network interface to instance.

        Creates NIC and adds to the VM instance.
        Returns the ip address of the new NIC.
        """
        us = datetime.datetime.now().strftime("%f")
        # get ip address object
        ip_address_obj = self._create_ip_address()
        ip_config_name = f"{self.name}-{us}-ip-config"
        # get subnet id and network security group id of primary nic
        default_nic_id = (
            self._instance["vm"].network_profile.network_interfaces[0].id
        )
        all_nics = self._network_client.network_interfaces.list_all()
        default_nic = [nic for nic in all_nics if nic.id == default_nic_id]
        if len(default_nic) == 0:
            raise PycloudlibError("Could not get the first/default NIC")
        default_nic = default_nic[0]
        subnet_id = default_nic.ip_configurations[0].subnet.id  # type: ignore
        nsg_id = default_nic.network_security_group.id  # type: ignore

        ip_config = dict(
            name=ip_config_name,
            subnet=dict(id=subnet_id),
            public_ip_address=dict(id=ip_address_obj.id),
        )
        default_config = {
            "location": self.location,
            "ip_configurations": [ip_config],
            "network_security_group": dict(id=nsg_id),
            "tags": None,
        }
        nic_name = f"{self.name}-nic-{us}"
        nic_poller = (
            self._network_client.network_interfaces.begin_create_or_update(
                self._instance["rg_name"], nic_name, default_config
            )
        )
        created_nic = nic_poller.result()
        nic_details = dict(id=created_nic.id, primary=False)
        self._attach_nic_to_vm([nic_details])
        return ip_address_obj.ip_address

    def remove_network_interface(self, ip_address: str):
        """Remove nic from running instance."""
        raise NotImplementedError

    def _attach_nic_to_vm(self, nics: List[Dict[str, Any]]):
        """Attach nics to instance."""
        if self.status != "stopped":
            raise PycloudlibError(
                "VM must be deallocated before attaching NIC"
            )
        params = self._instance["vm"].as_dict()
        vm_attached_nics = params["network_profile"]["network_interfaces"]
        vm_attached_nics.extend(nics)
        net_params = {
            "network_profile": {"network_interfaces": vm_attached_nics}
        }
        update_nested(params, net_params)
        poll = self._client.virtual_machines.begin_create_or_update(
            self._instance["rg_name"], self.name, params
        )
        poll.result()

    def _create_ip_address(self):
        us = datetime.datetime.now().strftime("%f")
        ip_name = f"{self.name}-{us}-ip"
        parameters = {
            "location": self.location,
            "sku": {"name": "Standard"},
            "public_ip_allocation_method": "Static",
            "rpublic_ip_address_version": "IPV4",
            "tags": None,
        }

        ip_poller = (
            self._network_client.public_ip_addresses.begin_create_or_update(
                self._instance["rg_name"],
                ip_name,
                parameters,
            )
        )

        return ip_poller.result()

    def deallocate(self):
        """De-allocates the VM. Releases the resources to modify VM."""
        self._client.virtual_machines.begin_deallocate(
            resource_group_name=self._instance["rg_name"], vm_name=self.name
        ).result()
        self.status = "stopped"
