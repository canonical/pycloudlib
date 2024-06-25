# This file is part of pycloudlib. See LICENSE file for license information.
"""Azure instance."""

import datetime
import time
from collections import namedtuple
from enum import Enum, auto
from typing import Any, Dict, List, Optional

import requests
from azure.core.exceptions import ResourceExistsError
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.network.models import NetworkInterface

from pycloudlib.errors import PycloudlibError, PycloudlibTimeoutError
from pycloudlib.instance import BaseInstance
from pycloudlib.util import update_nested

BootDiagnostics = namedtuple("BootDiagnostics", ["console_log_url", "logs"])

BOOT_DIAGNOSTICS_URI_DELAY = 60


class VMInstanceStatus(Enum):
    """Represents VM Instance state during its lifecycle."""

    FAILED_PROVISION = auto()
    ACTIVE = auto()
    DELETED = auto()
    STOPPED = auto()


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
        get_boot_diagnostics: bool = False,
        status: VMInstanceStatus = VMInstanceStatus.ACTIVE,
    ):
        """Set up instance.

        Args:
            key_pair: SSH key object
            client: Azure compute management client
            instance: created azure instance object
            username: username to use when connecting via SSH
        """
        super().__init__(key_pair, username=username)

        self._client: ComputeManagementClient = client
        self._network_client: NetworkManagementClient = network_client
        self._instance = instance
        self.boot_timeout = 300
        self._status: VMInstanceStatus = status
        self._boot_diagnostics_log = (
            self._get_boot_diagnostics() if get_boot_diagnostics else None
        )

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

    def console_log(self) -> Optional[str]:
        """Return the instance console log."""
        if not self._boot_diagnostics_log:
            return None
        return self._boot_diagnostics_log

    @property
    def status(self) -> VMInstanceStatus:
        """Return VM instance status."""
        return self._status

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

    def _get_boot_diagnostics(self) -> Optional[str]:
        """Get VM boot diagnostics logs.

        Returns the boot diagnostics logs.
        """
        response = None
        self._log.info(
            "Obtaining boot diagnostics logs for instance: %s",
            self._instance["rg_name"],
        )
        try:
            virtual_machines = self._client.virtual_machines
            diagnostics = virtual_machines.retrieve_boot_diagnostics_data(
                self._instance["rg_name"], self.name
            )
            # Azure has a 60 secs delay for the boot diagnostics to be active.
            time.sleep(BOOT_DIAGNOSTICS_URI_DELAY)
            response = requests.get(diagnostics.serial_console_log_blob_uri)
        except ResourceExistsError:
            self._log.warning(
                "Boot diagnostics not enabled, so none is collected."
            )
            return None
        return response.text

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
        self._status = VMInstanceStatus.ACTIVE

    def _wait_for_instance_start(self, **kwargs):
        for _ in range(120):
            view = self._client.virtual_machines.instance_view(
                self._instance["rg_name"], self.name
            )
            status = view.statuses[1].display_status
            if status.lower() == "vm running":
                return True
            time.sleep(1)
        raise PycloudlibTimeoutError("VM did not start.")

    def _do_restart(self, **kwargs):
        """Restart the instance."""
        self._client.virtual_machines.begin_restart(
            resource_group_name=self._instance["rg_name"], vm_name=self.name
        )

    # pylint: disable=broad-except
    def delete(self, wait=True) -> List[Exception]:
        """Delete instance."""
        if self._status == VMInstanceStatus.DELETED:
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
            self._status = VMInstanceStatus.DELETED
            self._instance = None
        except Exception as e:
            return [e]

        return []

    def add_network_interface(self, **kwargs) -> str:
        """Add network interface to instance.

        Creates NIC and adds to the VM instance.

        NOTE: It will deallocate the virtual machine, add the NIC,
        then start the virtual machine.

        Returns the private ip address of the new NIC.
        """
        # pylint: disable=too-many-locals
        # get subnet id and network security group id of primary nic
        default_nic_id = (
            self._instance["vm"].network_profile.network_interfaces[0].id
        )
        all_nics = list(self._network_client.network_interfaces.list_all())
        default_nic = [nic for nic in all_nics if nic.id == default_nic_id]
        if len(default_nic) == 0:
            raise PycloudlibError("Could not get the first/default NIC")
        default_nic = default_nic[0]
        subnet_id = default_nic.ip_configurations[0].subnet.id  # type: ignore
        nsg_id = default_nic.network_security_group.id  # type: ignore

        us = datetime.datetime.now().strftime("%f")
        # get ip address object
        ip_address_obj = self._create_ip_address()
        ip_config_name = f"{self.name}-{us}-ip-config"

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
        return created_nic.ip_configurations[0].private_ip_address

    def remove_network_interface(self, ip_address: str):
        """Remove nic from running instance.

        Args:
        ip_address: private ip address of the NIC
        """
        # Get details of the NICs attached to the VM.
        vm_nics_ids = [
            nic.id
            for nic in self._instance["vm"].network_profile.network_interfaces
        ]
        all_nics: List[NetworkInterface] = list(
            self._network_client.network_interfaces.list_all()
        )
        vm_nics = [nic for nic in all_nics if nic.id in vm_nics_ids]
        primary_nic = [nic for nic in vm_nics if nic.primary][0]
        nic_params = []
        nic_to_remove: Optional[NetworkInterface] = None
        for vm_nic in vm_nics:
            nic_private_ip = vm_nic.ip_configurations[0].private_ip_address  # type: ignore
            if nic_private_ip == ip_address:
                nic_to_remove = vm_nic
            else:
                nic_params.append({"id": vm_nic.id, "primary": vm_nic.primary})
        if not nic_to_remove:
            raise PycloudlibError(
                f"Did not find NIC with private ip address: {ip_address}"
            )
        # if primary nic is removed, then make the next NIC as primary
        if nic_to_remove.primary:
            primary_nic = None
            for nic_param in nic_params:
                primary_nics = [
                    nic for nic in vm_nics if nic.id == nic_param["id"]
                ]
                if len(primary_nics) > 0:
                    primary_nic = primary_nics[0]
                    nic_param["primary"] = True
                    break
            if not primary_nic:
                raise PycloudlibError("Could not set Primary NIC.")

        self._remove_nic_from_vm(nic_params, primary_nic)
        # delete the removed NIC
        self._network_client.network_interfaces.begin_delete(
            self._instance["rg_name"], nic_to_remove.name
        )

    def _remove_nic_from_vm(
        self,
        new_nic_params: List[Dict[str, Any]],
        primary_nic: NetworkInterface,
    ):
        do_start: bool = False
        if self._status != VMInstanceStatus.STOPPED:
            self._log.debug("Deallocating instance to remove NICs")
            # Azure deallocates VM before removing NiCs
            self.deallocate()
            do_start = True

        # Deleting will be async, no need to wait
        all_ips = list(self._network_client.public_ip_addresses.list_all())
        params = self._instance["vm"].as_dict()
        net_params = {
            "network_profile": {"network_interfaces": new_nic_params}
        }
        update_nested(params, net_params)
        poll = self._client.virtual_machines.begin_create_or_update(
            self._instance["rg_name"], self.name, params
        )
        # Update VM and Ip address
        self._instance["vm"] = poll.result()
        self._instance["ip_address"] = [
            ip_addr.ip_address
            for ip_addr in all_ips
            if ip_addr.id
            == primary_nic.ip_configurations[0].public_ip_address.id  # type: ignore
        ][0]
        if do_start:
            self.start()

    def _attach_nic_to_vm(self, nics: List[Dict[str, Any]]):
        """Attach nics to instance."""
        do_start: bool = False
        # NOTE: Azure needs the VM to be deallocated to add NICs
        if self._status != VMInstanceStatus.STOPPED:
            self._log.debug("Deallocating instance to attach NICs.")
            self.deallocate()
            do_start = True

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
        self._instance["vm"] = poll.result()
        if do_start:
            self.start()

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
        self._status = VMInstanceStatus.STOPPED
