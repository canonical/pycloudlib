# This file is part of pycloudlib. See LICENSE file for license information.
"""EC2 instance."""

import string
import time

from paramiko.ssh_exception import (
    SSHException
)

from pycloudlib.instance import BaseInstance


class EC2Instance(BaseInstance):
    """EC2 backed instance."""

    _type = 'ec2'

    def __init__(self, key_pair, client, instance):
        """Set up instance.

        Args:
            key_pair: SSH key object
            client: boto3 client object
            instance: created boto3 instance object
        """
        super().__init__(key_pair)

        self._instance = instance
        self._ip = None
        self._client = client

        self.boot_timeout = 300

    def __repr__(self):
        """Create string representation for class."""
        return '{}(key_pair={}, client={}, instance={})'.format(
            self.__class__.__name__,
            self.key_pair,
            self._client,
            self._instance
        )

    @property
    def availability_zone(self):
        """Return availability zone."""
        return self._instance.placement['AvailabilityZone']

    @property
    def ip(self):
        """Return IP address of instance."""
        self._instance.reload()
        return self._instance.public_ip_address

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

    def add_network_interface(self):
        """Add network interface to instance.

        Creates an ENI device and attaches it to the running instance. This
        is effectively a hot-add of a network device.

        See the AWS documentation for more info:
        https://boto3.readthedocs.io/en/latest/reference/services/ec2.html?#EC2.Client.create_network_interface
        https://boto3.readthedocs.io/en/latest/reference/services/ec2.html?#EC2.Client.attach_network_interface
        """
        self._log.debug('adding network interface to %s', self.id)
        interface_id = self._create_network_interface()
        self._attach_network_interface(interface_id)

    def add_volume(self, size=8, drive_type='gp2'):
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
        self._log.debug('adding storage volume to %s', self.id)
        volume = self._create_ebs_volume(size, drive_type)
        self._attach_ebs_volume(volume)

    def console_log(self):
        """Collect console log from instance.

        The console log is buffered and not always present, therefore
        may return empty string.

        Returns:
            The console log or error message

        """
        try:
            # OutputBytes comes from platform._decode_console_output_as_bytes
            response = self._instance.console_output()
            return response['OutputBytes']
        except KeyError:
            return 'No Console Output [%s]' % self._instance

    def delete(self, wait=True):
        """Delete instance."""
        self._log.debug('deleting instance %s', self._instance.id)
        self._instance.terminate()

        if wait:
            self.wait_for_delete()

    def restart(self, wait=True):
        """Restart the instance."""
        self._log.debug('restarting instance %s', self._instance.id)

        # Case 1: wait=False. Call boto3's reboot() and return.
        if not wait:
            self._instance.reboot()
            return

        pre_reboot_boot_id = None

        # Exceptions that may be raised when the instances is not reachable
        # via ssh.
        ssh_exceptions = (
            ConnectionRefusedError,
            ConnectionResetError,
            EOFError,
            RuntimeError,
            SSHException,
            TimeoutError,
        )

        try:
            # Try to get the current boot_id. We shouldn't assume this will
            # succeed, as one may want to restart the instance exactly because
            # it become unreachable.
            pre_reboot_boot_id = self._get_boot_id()
        except ssh_exceptions:
            # Case 2: wait=True, but the instance is unreachable.
            # The best we can do is to send a reboot signal and wait.
            self._log.debug('Instance seems down; '
                            'will send reboot signal and wait.')
            self._instance.reboot()
            self.wait()
            return

        self._log.debug('Pre-reboot boot_id: %s', pre_reboot_boot_id)

        # Case 3: wait=True, the instance is reachable. Call boto3's reboot()
        # and wait for the instance to change its boot_id, then wait().
        current_boot_id = pre_reboot_boot_id
        self._instance.reboot()
        while current_boot_id == pre_reboot_boot_id:
            time.sleep(5)
            try:
                self._log.debug('Reading the current boot_id.')
                current_boot_id = self._get_boot_id()
                self._log.debug('Current boot_id: %s', current_boot_id)
            except ssh_exceptions:
                # The instance went down. Exit the loop and delegate the rest
                # of the waiting to wait().
                self._log.debug('Instance went down (rebooting).')
                break

        self.wait()
        current_boot_id = self._get_boot_id()
        if current_boot_id == pre_reboot_boot_id:
            raise RuntimeError("Reboot failed (boot_id didn't change)")

    def shutdown(self, wait=True):
        """Shutdown the instance.

        Args:
            wait: wait for the instance shutdown
        """
        self._log.debug('shutting down instance %s', self._instance.id)
        self._instance.stop()

        if wait:
            self.wait_for_stop()

    def start(self, wait=True):
        """Start the instance.

        Args:
            wait: wait for the instance to start.
        """
        if self._instance.state['Name'] == 'running':
            return

        self._log.debug('starting instance %s', self._instance.id)
        self._instance.start()

        if wait:
            self.wait()

    def wait(self):
        """Wait for instance to be up and cloud-init to be complete."""
        self._log.debug('wait for instance running %s', self._instance.id)
        self._instance.wait_until_running()
        self._log.debug('reloading instance state %s', self._instance.id)
        self._instance.reload()
        self._wait_for_system()

    def wait_for_delete(self):
        """Wait for instance to be deleted."""
        self._instance.wait_until_terminated()
        self._instance.reload()

    def wait_for_stop(self):
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
            'Device': mount_point,
            'InstanceId': self.id,
            'VolumeId': volume['VolumeId'],
        }

        self._client.attach_volume(**args)

        waiter = self._client.get_waiter('volume_in_use')
        waiter.wait(VolumeIds=[volume['VolumeId']])

        self._instance.reload()

        self._instance.modify_attribute(
            BlockDeviceMappings=[{
                'DeviceName': mount_point,
                'Ebs': {
                    'DeleteOnTermination': True
                }
            }]
        )

    def _attach_network_interface(self, interface_id):
        """Attach ENI device to an instance.

        This will attach the interface at the next available index.

        The device will also be set to delete on termination of the
        instance.

        Args:
            interface_id: string, id of interface to attach
        """
        device_index = self._get_free_nic_index()
        args = {
            'DeviceIndex': device_index,
            'InstanceId': self.id,
            'NetworkInterfaceId': interface_id
        }

        response = self._client.attach_network_interface(**args)

        self._instance.reload()

        for nic in self._instance.network_interfaces:
            if nic.attachment['AttachmentId'] == response['AttachmentId']:
                nic.modify_attribute(
                    Attachment={
                        'AttachmentId': response['AttachmentId'],
                        'DeleteOnTermination': True
                    }
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
            'AvailabilityZone': self.availability_zone,
            'Size': size,
            'VolumeType': drive_type,
            'TagSpecifications': [{
                'ResourceType': 'volume',
                'Tags': [{
                    'Key': 'Name',
                    'Value': self.id
                }]
            }]
        }

        volume = self._client.create_volume(**args)

        waiter = self._client.get_waiter('volume_available')
        waiter.wait(VolumeIds=[volume['VolumeId']])

        return volume

    def _create_network_interface(self):
        """Create ENI device.

        Returns:
            The ENI device id

        """
        args = {
            'Groups': [
                group['GroupId'] for group in self._instance.security_groups
            ],
            'SubnetId': self._instance.subnet_id
        }

        response = self._client.create_network_interface(**args)
        interface_id = response['NetworkInterface']['NetworkInterfaceId']

        waiter = self._client.get_waiter('network_interface_available')
        waiter.wait(NetworkInterfaceIds=[interface_id])

        return interface_id

    def _get_free_nic_index(self):
        """Determine a free NIC interface for an instance.

        Loop through used device index (e.g. 0, 1) and the possible
        device index (e.g. 0, 1, 2... 15) and find the lower number
        that is available.

        Per the following doc the maximum number of NICs is 16:
        https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/using-eni.html

        Returns:
            integer to use as index for NIC

        """
        all_index = range(0, 16)

        used_index = set()
        for nic in self._instance.network_interfaces:
            used_index.add(nic.attachment['DeviceIndex'])

        return list(all_index - used_index)[0]

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
            if name not in 'abcde':
                all_device_names.append("/dev/sd%s" % name)

        used_device_names = set()
        for device in self._instance.block_device_mappings:
            used_device_names.add(device['DeviceName'])

        return list(set(all_device_names) - used_device_names)[0]

    def _get_boot_id(self):
        """Get the instance boot_id.

        Returns:
            string with the boot UUID

        """
        boot_id = self.execute("cat /proc/sys/kernel/random/boot_id")
        return boot_id
