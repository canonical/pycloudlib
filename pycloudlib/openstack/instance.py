"""Openstack instance type."""
import time

import openstack
from openstack.exceptions import BadRequestException, ConflictException

from pycloudlib.instance import BaseInstance


class OpenstackInstance(BaseInstance):
    """Openstack instance object."""

    _type = 'openstack'

    def __init__(self, key_pair, instance_id, connection=None):
        """Set up the instance.

        Args:
            key_pair: A KeyPair for SSH interactions
            instance_id: The instance id representing the cloud instance
            connection: The connection used to create this instance.
                If None, connection will be created.

        """
        super().__init__(key_pair)

        if not connection:
            connection = openstack.connect()
        self.conn = connection

        self.server = self.conn.compute.get_server(instance_id)

        self.floating_ip = self.conn.create_floating_ip(
            wait=True,
        )
        # TODO: Is there no blocking call for this?
        tries = 30
        while tries:
            try:
                self.conn.compute.add_floating_ip_to_server(
                    self.server,
                    self.floating_ip.floating_ip_address
                )
                break
            except BadRequestException as e:
                if 'Instance network is not ready yet' in str(e):
                    tries -= 1
                    time.sleep(1)
                    continue
                raise e

    def __repr__(self):
        """Create string representation of class."""
        return '{}(instance_id={})'.format(
            self.__class__.__name__,
            self.server.id
        )

    @property
    def name(self):
        """Return instance name."""
        return self.server.name

    @property
    def ip(self):
        """Return IP address of instance."""
        return self.floating_ip.floating_ip_address

    def console_log(self):
        """Return the instance console log."""
        # Returning nothing for me but might work in other contexts?
        self.conn.compute.get_server_console_output(self.server)

    def delete(self, wait=True):
        """Delete the instance.

        Args:
            wait: wait for instance to be deleted
        """
        self.conn.compute.delete_server(self.server.id)
        self.conn.delete_floating_ip(self.floating_ip.id)

    def restart(self, wait=True, **kwargs):
        """Restart the instance.

        Args:
            wait: wait for the instance to be fully started
        """
        self.shutdown(wait=wait)
        self.start(wait=wait)

    def shutdown(self, wait=True, **kwargs):
        """Shutdown the instance.

        Args:
            wait: wait for the instance to shutdown
        """
        self.conn.compute.stop_server(self.server)
        if wait:
            self.wait_for_stop()

    def start(self, wait=True):
        """Start the instance.

        Args:
            wait: wait for the instance to start.
        """
        try:
            self.conn.compute.start_server(self.server)
        except ConflictException as e:
            if 'while it is in vm_state active' in str(e):
                return
        if wait:
            self.wait()

    def _wait_for_instance_start(self):
        """Wait for instance to be up."""
        self.conn.compute.wait_for_server(self.server, status='ACTIVE')

    def wait_for_delete(self):
        """Wait for instance to be deleted."""
        self.conn.compute.wait_for_server(self.server, status='DELETED')

    def wait_for_stop(self):
        """Wait for instance stop."""
        self.conn.compute.wait_for_server(self.server, status='SHUTOFF')
