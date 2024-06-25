# This file is part of pycloudlib. See LICENSE file for license information.
"""EC2 instance."""

import string
import time
from typing import Dict, List, Optional

import botocore

from pycloudlib.errors import PycloudlibError
from pycloudlib.instance import BaseInstance


class EC2Instance(BaseInstance):
    """EC2 backed instance."""

    _type = "ec2"

    def __init__(
        self, key_pair, client, instance, *, username: Optional[str] = None
    ):
        """Set up instance.

        Args:
            key_pair: SSH key object
            client: boto3 client object
            instance: created boto3 instance object
            username: username to use when connecting via SSH
        """
        super().__init__(key_pair, username)

        self._instance = instance
        self._ip = None
        self._client = client

        self.boot_timeout = 300

        self.created_interfaces: List[str] = []

    def __repr__(self):
        """Create string representation for class."""
        return "{}(key_pair={}, client={}, instance={})".format(
            self.__class__.__name__,
            self.key_pair,
            self._client,
            self._instance,
        )

    @property
    def availability_zone(self):
        """Return availability zone."""
        return self._instance.placement["AvailabilityZone"]

    @property
    def ip(self):
        """Return IP address of instance."""
        self._instance.reload()
        return self._instance.public_ip_address

    @property
    def public_ips(self) -> List[str]:
        """Return public IP addresses of instance."""
        self._instance.reload()
        public_ips = []
        nic_ids = [nic.id for nic in self._instance.network_interfaces]
        nics_resp = self._client.describe_network_interfaces(
            NetworkInterfaceIds=nic_ids
        )
        _check_response(nics_resp)
        for association in self._find_nic_associations(nics_resp):
            public_ip = association.get("PublicIp")
            if public_ip:
                public_ips.append(public_ip)
        return public_ips

    @property
    def id(self):
        """Return id of instance."""
        return self._instance.instance_id

    @property
    def name(self):
        """Return id of instance."""
        return self.id

    @property
    def image_id(self):
        """Return id of instance."""
        return self._instance.image_id

    def add_network_interface(
        self,
        *,
        ipv4_address_count: int = 1,
        ipv6_address_count: int = 0,
        ipv4_public_ip_count: int = 0,
        **kwargs,
    ) -> str:
        """Add network interface to instance.

        Creates an ENI device and attaches it to the running instance. This
        is effectively a hot-add of a network device. Returns the IP address
        of the added network interface as a string.

        See the AWS documentation for more info:
        https://boto3.readthedocs.io/en/latest/reference/services/ec2.html?#EC2.Client.create_network_interface
        https://boto3.readthedocs.io/en/latest/reference/services/ec2.html?#EC2.Client.attach_network_interface

        Args:
            ipv4_address_count: number of private ipv4s
            ipv6_address_count: number of private ipv6s
            ipv4_public_ip_count: number of public ips associated to private
                ips
        Returns: private primary ip
        """
        self._log.debug("adding network interface to %s", self.id)
        interface_id = self._create_network_interface(ipv6_address_count)
        if ipv4_address_count < ipv4_public_ip_count:
            raise PycloudlibError(
                f"Invalid configuration:"
                f" `ipv4_public_ip_count={ipv4_public_ip_count}` cannot be"
                f" greater than `ipv4_address_count={ipv4_address_count}`"
            )

        if ipv4_address_count > 1:
            assignment_resp = self._client.assign_private_ip_addresses(
                NetworkInterfaceId=interface_id,
                # Minus one to account for the private_ipv4 that comes by
                # default with the NIC
                SecondaryPrivateIpAddressCount=ipv4_address_count - 1,
            )
            _check_response(assignment_resp)
        if ipv4_public_ip_count > 0:
            nics_resp = self._client.describe_network_interfaces(
                NetworkInterfaceIds=[interface_id]
            )
            _check_response(nics_resp)
            priv_ips = [nics_resp["NetworkInterfaces"][0]["PrivateIpAddress"]]
            if ipv4_address_count > 1:
                priv_ips.extend(
                    (
                        x["PrivateIpAddress"]
                        for x in assignment_resp["AssignedPrivateIpAddresses"]
                    )
                )
            for i in range(ipv4_public_ip_count):
                allocation = self._client.allocate_address(Domain="vpc")
                _check_response(allocation)
                association = self._client.associate_address(
                    AllocationId=allocation["AllocationId"],
                    NetworkInterfaceId=interface_id,
                    PrivateIpAddress=priv_ips[i],
                )
                _check_response(association)

        return self._attach_network_interface(interface_id)

    def add_volume(self, size=8, drive_type="gp2"):
        """Add storage volume to instance.

        Creates an EBS volume and attaches it to the running instance. This
        is effectively a hot-add of a storage device.

        See AWS documentation for more info:
        https://boto3.readthedocs.io/en/latest/reference/services/ec2.html?#EC2.Client.create_volume
        https://boto3.readthedocs.io/en/latest/reference/services/ec2.html?#EC2.Client.attach_volume

        Args:
            size: Size in GB of the drive to add
            drive_type: Type of EBS volume to add
        """
        self._log.debug("adding storage volume to %s", self.id)
        volume = self._create_ebs_volume(size, drive_type)
        self._attach_ebs_volume(volume)

    def console_log(self):
        """Collect console log from instance.

        The console log is buffered and not always present, therefore
        may return empty string.

        Returns:
            The console log or error message

        """
        start = time.time()
        while time.time() < start + 300:
            response = self._instance.console_output(Latest=True)
            try:
                return response["Output"]
            except KeyError:
                self._log.debug("Console output not yet available; sleeping")
                time.sleep(5)
        return "No Console Output [%s]" % self._instance

    # pylint: disable=broad-except
    def delete(self, wait=True) -> List[Exception]:
        """Delete instance."""
        exceptions = []
        # Even with DeleteOnTermination set True, nics can outlive instances
        for ip in self.created_interfaces[:]:
            try:
                self.remove_network_interface(ip)
            except Exception as e:
                exceptions.append(e)
        self._log.debug("deleting instance %s", self._instance.id)
        try:
            self._instance.terminate()
            if wait:
                self.wait_for_delete()
        except Exception as e:
            exceptions.append(e)

        return exceptions

    def _do_restart(self, **kwargs):
        """Restart the instance."""
        self._log.debug("restarting instance %s", self._instance.id)
        self._instance.reboot()

    def shutdown(self, wait=True, **kwargs):
        """Shutdown the instance.

        Args:
            wait: wait for the instance shutdown
        """
        self._log.debug("shutting down instance %s", self._instance.id)
        self._instance.stop()

        if wait:
            self.wait_for_stop()

    def start(self, wait=True):
        """Start the instance.

        Args:
            wait: wait for the instance to start.
        """
        if self._instance.state["Name"] == "running":
            return

        self._log.debug("starting instance %s", self._instance.id)
        self._instance.start()

        if wait:
            self.wait()

    def _wait_for_instance_start(self, **kwargs):
        """Wait for instance to be up."""
        self._log.debug("wait for instance running %s", self._instance.id)
        self._instance.wait_until_running()
        self._log.debug("reloading instance state %s", self._instance.id)
        self._instance.reload()

    def wait_for_delete(self, **kwargs):
        """Wait for instance to be deleted."""
        self._instance.wait_until_terminated()
        self._instance.reload()

    def wait_for_stop(self, **kwargs):
        """Wait for instance stop."""
        self._instance.wait_until_stopped()
        self._instance.reload()

    def _attach_ebs_volume(self, volume):
        """Attach EBS volume to an instance.

        The volume will get added at the next available volume name.

        The volume will also be set to delete on termination of the
        instance.

        Args:
            volume: boto3 volume object
        """
        mount_point = self._get_free_volume_name()
        args = {
            "Device": mount_point,
            "InstanceId": self.id,
            "VolumeId": volume["VolumeId"],
        }

        self._client.attach_volume(**args)

        waiter = self._client.get_waiter("volume_in_use")
        waiter.wait(VolumeIds=[volume["VolumeId"]])

        self._instance.reload()

        self._instance.modify_attribute(
            BlockDeviceMappings=[
                {
                    "DeviceName": mount_point,
                    "Ebs": {"DeleteOnTermination": True},
                }
            ]
        )

    def _attach_network_interface(self, interface_id: str) -> str:
        """Attach ENI device to an instance.

        This will attach the interface at the next available index.

        The device will also be set to delete on termination of the
        instance.

        Args:
            interface_id: string, id of interface to attach
        Returns:
            IP address of the added interface
        """
        device_index = self._get_free_nic_index()
        args = {
            "DeviceIndex": device_index,
            "InstanceId": self.id,
            "NetworkInterfaceId": interface_id,
        }

        response = self._client.attach_network_interface(**args)

        # It's possible the attach worked correctly but it's not yet
        # present in the nic attributes
        for _ in range(5):
            self._instance.reload()
            for nic in self._instance.network_interfaces:
                if nic.attachment["AttachmentId"] == response["AttachmentId"]:
                    nic.modify_attribute(
                        Attachment={
                            "AttachmentId": response["AttachmentId"],
                            "DeleteOnTermination": True,
                        }
                    )
                    self.created_interfaces.append(nic.private_ip_address)
                    return nic.private_ip_address
            time.sleep(1)
        raise PycloudlibError(
            "Could not attach NIC with AttachmentId: "
            f'{response.get("AttachmentId", None)} after 5 attempts'
        )

    def _create_ebs_volume(self, size, drive_type):
        """Create EBS volume.

        Args:
            size: Size of drive to create in GB
            drive_type: Type of drive to create

        Returns:
            The boto3 volume object

        """
        args = {
            "AvailabilityZone": self.availability_zone,
            "Size": size,
            "VolumeType": drive_type,
            "TagSpecifications": [
                {
                    "ResourceType": "volume",
                    "Tags": [{"Key": "Name", "Value": self.id}],
                }
            ],
        }

        volume = self._client.create_volume(**args)

        waiter = self._client.get_waiter("volume_available")
        waiter.wait(VolumeIds=[volume["VolumeId"]])

        return volume

    def _create_network_interface(
        self,
        ipv6_address_count: Optional[int] = None,
    ) -> str:
        """Create ENI device.

        Returns:
            The ENI device id

        """
        args = {
            "Groups": [
                group["GroupId"] for group in self._instance.security_groups
            ],
            "SubnetId": self._instance.subnet_id,
        }
        if ipv6_address_count:
            args["Ipv6AddressCount"] = ipv6_address_count

        response = self._client.create_network_interface(**args)
        interface_id = response["NetworkInterface"]["NetworkInterfaceId"]

        waiter = self._client.get_waiter("network_interface_available")
        waiter.wait(NetworkInterfaceIds=[interface_id])

        return interface_id

    def _get_free_nic_index(self) -> int:
        """Determine a free NIC interface for an instance.

        Per the following doc the maximum number of NICs is 16:
        https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-eni.html

        Returns:
            integer to use as index for NIC

        """
        used_indexes = [
            nic.attachment["DeviceIndex"]
            for nic in self._instance.network_interfaces
        ]
        for possible_index in range(16):
            if possible_index not in used_indexes:
                return possible_index
        raise PycloudlibError("No free nics left!")

    def _get_free_volume_name(self):
        """Determine a free volume mount point for an instance.

        Loop through used mount names (e.g. /dev/sda1, /dev/sdb) and
        the possible device names (e.g. /dev/sdf, /dev/sdg... /dev/sdz)
        and find the first that is available.

        This also works for instances which only have NVMe devices or
        when mounting NVMe EBS volumes. In which case, this suggestion
        is ignored an the number number is used.

        Using /dev/sd* per the following doc:
        https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/device_naming.html

        Returns:
            string of latest name available

        """
        all_device_names = []
        for name in string.ascii_lowercase:
            if name not in "abcde":
                all_device_names.append("/dev/sd%s" % name)

        used_device_names = set()
        for device in self._instance.block_device_mappings:
            used_device_names.add(device["DeviceName"])

        return list(set(all_device_names) - used_device_names)[0]

    def _get_nic_matching_ip(self, ip_address):
        return next(
            (
                nic
                for nic in self._instance.network_interfaces
                if nic.private_ip_address == ip_address
            ),
            None,
        )

    def _find_nic_associations(self, nics_resp: Dict) -> List[Dict]:
        associations: List[Dict] = []
        if not nics_resp["NetworkInterfaces"]:
            return associations
        for nic_md in nics_resp["NetworkInterfaces"]:
            # Global associations
            association = nic_md.get("Association")
            if association:
                associations.append(association)
            # Per-ip associations
            for priv_address in nic_md.get("PrivateIpAddresses", []):
                if priv_address.get("Primary", False):
                    continue
                association = priv_address.get("Association")
                if association:
                    associations.append(association)
        return associations

    def _release_address(self, private_ip: str):
        nics_resp = self._client.describe_network_interfaces(
            Filters=[
                {
                    "Name": "private-ip-address",
                    "Values": [private_ip],
                },
            ]
        )
        for association in self._find_nic_associations(nics_resp):
            try:
                self._client.disassociate_address(
                    AssociationId=association["AssociationId"]
                )
            except botocore.exceptions.ClientError as ex:
                self._log.debug(
                    "Error disassociating Public IP from NIC with IP"
                    " %s: %s",
                    private_ip,
                    str(ex),
                )
            try:
                self._client.release_address(
                    AllocationId=association["AllocationId"]
                )
            except botocore.exceptions.ClientError as ex:
                self._log.debug(
                    "Error deleting Public IP from NIC with IP" " %s: %s",
                    private_ip,
                    str(ex),
                )
                return
            self._log.debug(
                "Public IP released %s from NIC with IP %s.",
                association["PublicIp"],
                private_ip,
            )

    def remove_network_interface(self, ip_address):
        """Remove network interface based on IP address.

        Find the NIC from the IP, detach from the instance, then delete the
        NIC.
        """
        self._release_address(ip_address)
        # Get the NIC from the IP
        nic = self._get_nic_matching_ip(ip_address)
        if not nic:
            self._log.debug(
                "Not deleting NIC because no NIC with IP {} found."
            )
            return

        # Detach from the instance
        self._client.detach_network_interface(
            AttachmentId=nic.attachment["AttachmentId"]
        )

        # Wait for detach
        for _ in range(60):
            self._instance.reload()
            if not self._get_nic_matching_ip(ip_address):
                break
            time.sleep(1)
        else:
            raise PycloudlibError("Network interface did not detach")

        # Delete the NIC
        try:
            self._client.delete_network_interface(NetworkInterfaceId=nic.id)
            self._log.debug("NIC with IP %s deleted.", ip_address)
            self.created_interfaces.remove(ip_address)
        except botocore.exceptions.ClientError:
            self._log.debug(
                "Failed manually deleting network interface. "
                "Interface should get destroyed on instance cleanup."
            )


def _check_response(resp):
    if resp.get("ResponseMetadata", {}).get("HTTPStatusCode", 200) != 200:
        raise PycloudlibError(f"Internal error in client response: {resp}")
