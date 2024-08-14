# pylint: disable=E1101
# This file is part of pycloudlib. See LICENSE file for license information.
"""OCI instance."""

from time import sleep
from typing import Dict, List, Optional

import oci

from pycloudlib.errors import PycloudlibError
from pycloudlib.instance import BaseInstance
from pycloudlib.oci.utils import get_subnet_id, wait_till_ready


class OciInstance(BaseInstance):
    """OCI backed instance."""

    _type = "oci"

    def __init__(
        self,
        key_pair,
        instance_id,
        compartment_id,
        availability_domain,
        oci_config=None,
        *,
        username: Optional[str] = None,
    ):
        """Set up the instance.

        Args:
            key_pair: A KeyPair for SSH interactions
            instance_id: The instance id representing the cloud instance
            compartment_id: A compartment found at
                https://console.us-phoenix-1.oraclecloud.com/a/identity/compartments
            availability_domain: One of the availability domains from:
                'oci iam availability-domain list'
            oci_config: OCI configuration dictionary
            username: username to use when connecting via SSH
        """
        super().__init__(key_pair, username=username)
        self.instance_id = instance_id
        self.compartment_id = compartment_id
        self.availability_domain = availability_domain
        self._fault_domain = None
        self._ip = None

        if oci_config is None:
            oci_config = oci.config.from_file("~/.oci/config")  # noqa: E501
        self.compute_client = oci.core.ComputeClient(oci_config)  # noqa: E501
        self.network_client = oci.core.VirtualNetworkClient(oci_config)  # noqa: E501

    def __repr__(self):
        """Create string representation of class."""
        return "{}(instance_id={}, compartment_id={})".format(
            self.__class__.__name__,
            self.instance_id,
            self.compartment_id,
        )

    @property
    def id(self) -> str:
        """Return instance id."""
        return self.instance_id

    @property
    def name(self):
        """Return the instance name."""
        return self.instance_id

    @property
    def ip(self):
        """Return IP address of instance."""
        if not self._ip:
            vnic_attachment = self.compute_client.list_vnic_attachments(
                compartment_id=self.compartment_id,
                instance_id=self.instance_data.id,
            ).data[0]
            vnic_info = self.network_client.get_vnic(
                vnic_attachment.vnic_id
            ).data
            # if not public IP, check for ipv6
            if vnic_info.public_ip is None:
                if vnic_info.ipv6_addresses:
                    self._ip = vnic_info.ipv6_addresses[0]
                    self._log.info("Using ipv6 address: %s", self._ip)
                else:
                    raise PycloudlibError(
                        "No public ipv4 address or ipv6 address found"
                    )
            else:
                self._ip = vnic_info.public_ip
                self._log.info("Using ipv4 address: %s", self._ip)
            return self._ip
        return self._ip

    @property
    def instance_data(self):
        """Return JSON formatted details from OCI about this instance."""
        return self.compute_client.get_instance(self.instance_id).data

    @property
    def fault_domain(self):
        """Obtain the fault domain the instance resides in."""
        if self._fault_domain is None:
            self._fault_domain = self.instance_data.fault_domain
        return self._fault_domain

    def console_log(self):
        """Not currently implemented."""
        # This is possible, but we need to capture console history first
        # self.compute_client.capture_console_history(...)
        # self.compute_client.get_console_history_content(...)
        raise NotImplementedError

    # pylint: disable=broad-except
    def delete(self, wait=True) -> List[Exception]:
        """Delete the instance.

        Args:
            wait: wait for instance to be deleted
        """
        try:
            self.compute_client.terminate_instance(self.instance_data.id)
            if wait:
                self.wait_for_delete()
        except Exception as e:
            return [e]
        return []

    def _do_restart(self, **kwargs):
        """Restart the instance."""
        last_exception = None
        for _ in range(30):
            try:
                self.compute_client.instance_action(
                    self.instance_data.id, "RESET"
                )
                return
            except oci.exceptions.ServiceError as e:
                last_exception = e
                if last_exception.status != 409:
                    raise
                self._log.debug(
                    "Received 409 attempting to RESET instance. Retrying"
                )
                sleep(0.5)
        if last_exception:
            raise last_exception

    def shutdown(self, wait=True, **kwargs):
        """Shutdown the instance.

        Args:
            wait: wait for the instance to shutdown
        """
        self._sync_filesystem()
        self.compute_client.instance_action(self.instance_data.id, "STOP")
        if wait:
            self.wait_for_stop()

    def start(self, wait=True):
        """Start the instance.

        Args:
            wait: wait for the instance to start.
        """
        self.compute_client.instance_action(self.instance_data.id, "START")
        if wait:
            self.wait()

    def _wait_for_instance_start(
        self, *, func_kwargs: Optional[Dict[str, str]] = None, **kwargs
    ):
        """Wait for instance to be up."""
        wait_till_ready(
            func=self.compute_client.get_instance,
            current_data=self.instance_data,
            desired_state="RUNNING",
            func_kwargs=func_kwargs,
        )

    def wait_for_delete(
        self, *, func_kwargs: Optional[Dict[str, str]] = None, **kwargs
    ):
        """Wait for instance to be deleted."""
        wait_till_ready(
            func=self.compute_client.get_instance,
            current_data=self.instance_data,
            desired_state="TERMINATED",
            func_kwargs=func_kwargs,
        )

    def wait_for_stop(
        self, *, func_kwargs: Optional[Dict[str, str]] = None, **kwargs
    ):
        """Wait for instance stop."""
        wait_till_ready(
            func=self.compute_client.get_instance,
            current_data=self.instance_data,
            desired_state="STOPPED",
            func_kwargs=func_kwargs,
        )

    def add_network_interface(self, **kwargs) -> str:
        """Add network interface to running instance.

        Creates a nic and attaches it to the instance. This is effectively a
        hot-add of a network device. Returns the IP address of the added
        network interface as a string.

        Note: It assumes the associated compartment has at least one subnet and
        creates the vnic in the first encountered subnet.
        """
        subnet_id = get_subnet_id(
            self.network_client, self.compartment_id, self.availability_domain
        )
        create_vnic_details = oci.core.models.CreateVnicDetails(  # noqa: E501
            subnet_id=subnet_id,
        )
        attach_vnic_details = oci.core.models.AttachVnicDetails(  # noqa: E501
            create_vnic_details=create_vnic_details,
            instance_id=self.instance_id,
        )
        vnic_attachment_data = self.compute_client.attach_vnic(
            attach_vnic_details
        ).data
        vnic_attachment_data = wait_till_ready(
            func=self.compute_client.get_vnic_attachment,
            current_data=vnic_attachment_data,
            desired_state=vnic_attachment_data.LIFECYCLE_STATE_ATTACHED,
        )
        vnic_data = self.network_client.get_vnic(
            vnic_attachment_data.vnic_id
        ).data
        return vnic_data.private_ip

    def remove_network_interface(self, ip_address: str):
        """Remove network interface based on IP address.

        Find the NIC from the IP, detach from the instance.

        Note: In OCI, detaching triggers deletion.
        """
        vnic_attachments = oci.pagination.list_call_get_all_results_generator(  # noqa: E501
            self.compute_client.list_vnic_attachments,
            "record",
            self.compartment_id,
            instance_id=self.instance_id,
        )
        for vnic_attachment in vnic_attachments:
            vnic_data = self.network_client.get_vnic(
                vnic_attachment.vnic_id
            ).data
            if vnic_data.private_ip == ip_address:
                try:
                    self.compute_client.detach_vnic(vnic_attachment.id)
                except oci.exceptions.ServiceError:
                    self._log.debug(
                        "Failed manually detaching and deleting network "
                        "interface. Interface should get destroyed on instance"
                        " cleanup."
                    )
                return
        raise PycloudlibError(
            f"Network interface with ip_address={ip_address} did not detach"
        )
