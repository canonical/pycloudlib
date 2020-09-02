# pylint: disable=E1101
# This file is part of pycloudlib. See LICENSE file for license information.
"""OCI instance."""

import oci

from pycloudlib.instance import BaseInstance
from pycloudlib.oci.utils import wait_till_ready


class OciInstance(BaseInstance):
    """OCI backed instance."""

    _type = 'oci'

    def __init__(self, key_pair, instance_id, compartment_id,
                 config_path='~/.oci/config'):
        """Set up the instance.

        Args:
            key_pair: A KeyPair for SSH interactions
            instance_id: The instance id representing the cloud instance
            compartment_id: A compartment found at
                https://console.us-phoenix-1.oraclecloud.com/a/identity/compartments
            config_path: Path of OCI config file

        """
        super().__init__(key_pair)
        self.instance_id = instance_id
        self.compartment_id = compartment_id
        self._ip = None

        config = oci.config.from_file(str(config_path))
        self.compute_client = oci.core.ComputeClient(config)
        self.network_client = oci.core.VirtualNetworkClient(config)

    def __repr__(self):
        """Create string representation of class."""
        return '{}(instance_id={}, compartment_id={})'.format(
            self.__class__.__name__,
            self.instance_id,
            self.compartment_id,
        )

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
                instance_id=self.instance_data.id
            ).data[0]

            self._ip = self.network_client.get_vnic(
                vnic_attachment.vnic_id
            ).data.public_ip
        return self._ip

    @property
    def instance_data(self):
        """Return JSON formatted details from OCI about this instance."""
        return self.compute_client.get_instance(self.instance_id).data

    def console_log(self):
        """Not currently implemented."""
        # This is possible, but we need to capture console history first
        # self.compute_client.capture_console_history(...)
        # self.compute_client.get_console_history_content(...)
        raise NotImplementedError

    def delete(self, wait=True):
        """Delete the instance.

        Args:
            wait: wait for instance to be deleted
        """
        self.compute_client.terminate_instance(self.instance_data.id)
        if wait:
            self.wait_for_delete()

    def restart(self, wait=True):
        """Restart the instance.

        Args:
            wait: wait for the instance to be fully started
        """
        self.compute_client.instance_action(self.instance_data.id, 'RESET')
        if wait:
            self.wait()

    def shutdown(self, wait=True):
        """Shutdown the instance.

        Args:
            wait: wait for the instance to shutdown
        """
        self.compute_client.instance_action(self.instance_data.id, 'STOP')
        if wait:
            self.wait_for_stop()

    def start(self, wait=True):
        """Start the instance.

        Args:
            wait: wait for the instance to start.
        """
        self.compute_client.instance_action(self.instance_data.id, 'START')
        if wait:
            self.wait()

    def wait(self):
        """Wait for instance to be up and cloud-init to be complete."""
        wait_till_ready(
            func=self.compute_client.get_instance,
            current_data=self.instance_data,
            desired_state='RUNNING',
        )

    def wait_for_delete(self):
        """Wait for instance to be deleted."""
        wait_till_ready(
            func=self.compute_client.get_instance,
            current_data=self.instance_data,
            desired_state='TERMINATED',
        )

    def wait_for_stop(self):
        """Wait for instance stop."""
        wait_till_ready(
            func=self.compute_client.get_instance,
            current_data=self.instance_data,
            desired_state='STOPPED',
        )
