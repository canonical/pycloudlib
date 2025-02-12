# pylint: disable=E1101
# This file is part of pycloudlib. See LICENSE file for license information.
"""OCI instance."""

import json
from time import sleep
import time
from typing import Dict, List, Optional

import oci

from pycloudlib.errors import PycloudlibError
from pycloudlib.instance import BaseInstance
from pycloudlib.oci.utils import get_subnet_id, get_subnet_id_by_name, wait_till_ready


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
            for _ in range(100):
                vnic_attachment = self.compute_client.list_vnic_attachments(
                    compartment_id=self.compartment_id,
                    instance_id=self.instance_data.id,
                ).data
                if vnic_attachment:
                    break
                self._log.debug("No vnic_attachment found, retrying...")
                sleep(5)
            else:
                raise PycloudlibError("No vnic_attachment found after 100 retries")

            self._log.debug("vnic_attachment: %s", vnic_attachment)
            vnics = [
                self.network_client.get_vnic(vnic_attachment.vnic_id).data
                for vnic_attachment in vnic_attachment
            ]
            # select vnic with is_primary = True
            primary_vnic = [vnic for vnic in vnics if vnic.is_primary][0]
            # if not public IP, check for ipv6
            # None is specifically returned by OCI when ipv6 only vnic
            if primary_vnic.public_ip is None:
                if primary_vnic.ipv6_addresses:
                    self._ip = primary_vnic.ipv6_addresses[0]
                    self._log.info("Using ipv6 address: %s", self._ip)
                else:
                    raise PycloudlibError("No public ipv4 address or ipv6 address found")
            else:
                self._ip = primary_vnic.public_ip
                self._log.info("Using ipv4 address: %s", self._ip)
            return self._ip
        return self._ip

    @property
    def private_ip(self):
        """Return private IP address of instance."""
        for _ in range(100):
            vnic_attachment = self.compute_client.list_vnic_attachments(
                compartment_id=self.compartment_id,
                instance_id=self.instance_data.id,
            ).data
            if vnic_attachment:
                break
            self._log.debug("No vnic_attachment found, retrying...")
            sleep(5)
        else:
            raise PycloudlibError("No vnic_attachment found after 100 retries")

        self._log.debug("vnic_attachment: %s", vnic_attachment)
        vnics = [
            self.network_client.get_vnic(vnic_attachment.vnic_id).data
            for vnic_attachment in vnic_attachment
        ]
        self._log.debug("vnics: %s", vnics)
        # select vnic with is_primary = True
        primary_vnic = [vnic for vnic in vnics if vnic.is_primary][0]
        return primary_vnic.private_ip

    @property
    def secondary_vnic_private_ip(self) -> Optional[str]:
        """Return private IP address of secondary vnic."""
        vnic_attachments = self.compute_client.list_vnic_attachments(
            compartment_id=self.compartment_id,
            instance_id=self.instance_data.id,
        ).data
        if len(vnic_attachments) < 2:
            return None
        vnics = [
            self.network_client.get_vnic(vnic_attachment.vnic_id).data
            for vnic_attachment in vnic_attachments
        ]
        # get vnic that is not primary
        secondary_vnic_attachment = [vnic for vnic in vnics if not vnic.is_primary][0]
        return secondary_vnic_attachment.private_ip

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
                self.compute_client.instance_action(self.instance_data.id, "RESET")
                return
            except oci.exceptions.ServiceError as e:
                last_exception = e
                if last_exception.status != 409:
                    raise
                self._log.debug("Received 409 attempting to RESET instance. Retrying")
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

    def _wait_for_instance_start(self, *, func_kwargs: Optional[Dict[str, str]] = None, **kwargs):
        """Wait for instance to be up."""
        wait_till_ready(
            func=self.compute_client.get_instance,
            current_data=self.instance_data,
            desired_state="RUNNING",
            func_kwargs=func_kwargs,
        )

    def wait_for_delete(self, *, func_kwargs: Optional[Dict[str, str]] = None, **kwargs):
        """Wait for instance to be deleted."""
        wait_till_ready(
            func=self.compute_client.get_instance,
            current_data=self.instance_data,
            desired_state="TERMINATED",
            func_kwargs=func_kwargs,
        )

    def wait_for_stop(self, *, func_kwargs: Optional[Dict[str, str]] = None, **kwargs):
        """Wait for instance stop."""
        wait_till_ready(
            func=self.compute_client.get_instance,
            current_data=self.instance_data,
            desired_state="STOPPED",
            func_kwargs=func_kwargs,
        )

    def get_secondary_vnic_ip(self) -> str:
        """Check if the instance has a secondary VNIC."""
        vnic_attachments = oci.pagination.list_call_get_all_results_generator(  # noqa: E501
            self.compute_client.list_vnic_attachments,
            "record",
            self.compartment_id,
            instance_id=self.instance_id,
        )
        return vnic_attachments[1].data.private_ip

    def add_network_interface(
        self,
        nic_index: int = 0,
        use_private_subnet: bool = False,
        subnet_name: Optional[str] = None,
    ) -> str:
        """Add network interface to running instance.

        Creates a nic and attaches it to the instance. This is effectively a
        hot-add of a network device. Returns the private IP address of the added
        network interface as a string.

        Args:
            nic_index: The index of the NIC to add
            subnet_name: Name of the subnet to add the NIC to. If not provided,
                will use `use_private_subnet` to select first available subnet.
            use_private_subnet: If True, will select the first available private
                subnet. If False, will select the first available public subnet.
                This is only used if `subnet_name` is not provided.
        """
        if subnet_name:
            subnet_id = get_subnet_id_by_name(
                self.network_client, self.compartment_id, subnet_name,
            )
        else:
            subnet_id = get_subnet_id(
                self.network_client, self.compartment_id, self.availability_domain, private=use_private_subnet,
            )
        create_vnic_details = oci.core.models.CreateVnicDetails(  # noqa: E501
            subnet_id=subnet_id,
        )
        attach_vnic_details = oci.core.models.AttachVnicDetails(  # noqa: E501
            create_vnic_details=create_vnic_details,
            instance_id=self.instance_id,
            nic_index=nic_index,
        )
        vnic_attachment_data = self.compute_client.attach_vnic(attach_vnic_details).data
        vnic_attachment_data = wait_till_ready(
            func=self.compute_client.get_vnic_attachment,
            current_data=vnic_attachment_data,
            desired_state=vnic_attachment_data.LIFECYCLE_STATE_ATTACHED,
        )
        vnic_data = self.network_client.get_vnic(vnic_attachment_data.vnic_id).data
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
            vnic_data = self.network_client.get_vnic(vnic_attachment.vnic_id).data
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
        raise PycloudlibError(f"Network interface with ip_address={ip_address} did not detach")

    def configure_secondary_vnic(self) -> str:
        if not self.secondary_vnic_private_ip:
            raise ValueError("Cannot configure secondary VNIC without a secondary VNIC attached")
        secondary_vnic_imds_data: Optional[Dict[str, str]] = None
        # it can take a bit for the 
        for _ in range(60):
            # Fetch JSON data from the Oracle Cloud metadata service
            imds_req = self.execute("curl -s http://169.254.169.254/opc/v1/vnics").stdout
            vnics_data = json.loads(imds_req)
            if len(vnics_data) > 1:
                self._log.debug("Successfully fetched secondary VNIC data from IMDS")
                secondary_vnic_imds_data = vnics_data[1]
                break
            self._log.debug("No secondary VNIC data found from IMDS, retrying...")
            time.sleep(1)

        if not secondary_vnic_imds_data:
            raise PycloudlibError(
                "Failed to fetch secondary VNIC data from IMDS. Cannot configure secondary VNIC"
            )
                      
        # Extract MAC address and private IP from the second VNIC 
        mac_addr = secondary_vnic_imds_data["macAddr"]
        private_ip = secondary_vnic_imds_data["privateIp"]
        subnet_mask = secondary_vnic_imds_data["subnetCidrBlock"].split("/")[1]
        # Find the network interface corresponding to the MAC address
        interface = self.execute(
            f"ip link show | grep -B1 {mac_addr} | head -n1 | awk '{{print $2}}' | sed 's/://' "
        ).stdout.strip()
        # Check if the interface was found
        if not interface:
            raise ValueError(f"No interface found for MAC address {mac_addr}")
        # Add the IP address to the interface
        self.execute(
            f"sudo ip addr add {private_ip}/{subnet_mask} dev {interface}"
        )
        # Verify that the IP address was added
        r = self.execute(f"ip addr show dev {interface}")
        if private_ip not in r.stdout:
            raise ValueError(f"IP {private_ip} was not successfully assigned to interface {interface}")
        self._log.info("Successfully assigned IP %s to interface %s", private_ip, interface)
        return private_ip
