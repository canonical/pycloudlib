"""Openstack instance type."""
import time
from itertools import chain

import openstack
from openstack.exceptions import (
    BadRequestException,
    ConflictException,
    ResourceNotFound,
)

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

        self.delete_floating_ip = False
        self.floating_ip = self._get_existing_floating_ip()
        if self.floating_ip is None:
            self.floating_ip = self._create_and_attach_floating_id()
            self.delete_floating_ip = True

    def _get_existing_floating_ip(self):
        server_addresses = chain(*self.server.addresses.values())
        server_ips = [addr['addr'] for addr in server_addresses]
        for floating_ip in self.conn.network.ips():
            if floating_ip['floating_ip_address'] in server_ips:
                return floating_ip
        return None

    def _create_and_attach_floating_id(self):
        floating_ip = self.conn.create_floating_ip(wait=True)
        tries = 30
        for _ in range(tries):
            try:
                self.conn.compute.add_floating_ip_to_server(
                    self.server,
                    floating_ip.floating_ip_address
                )
                break
            except BadRequestException as e:
                if 'Instance network is not ready yet' in str(e):
                    time.sleep(1)
                    continue
                raise e
        return floating_ip

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
        start = time.time()
        while time.time() < start + 180:
            response = self.conn.compute.get_server_console_output(self.server)
            if response:
                return response
            self._log.debug("Console output not yet available; sleeping")
            time.sleep(5)
        return 'No console output'

    def delete(self, wait=True):
        """Delete the instance.

        Args:
            wait: wait for instance to be deleted
        """
        try:
            self.conn.compute.delete_server(self.server.id)
        finally:
            if self.delete_floating_ip:
                self.conn.delete_floating_ip(self.floating_ip.id)
        if wait:
            self.wait_for_delete()

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
            # We can get an exception here if the instance is already started
            if 'while it is in vm_state active' in str(e):
                return
        if wait:
            self.wait()

    def _wait_for_instance_start(self):
        """Wait for instance to be up."""
        self.conn.compute.wait_for_server(self.server, status='ACTIVE')

    def wait_for_delete(self):
        """Wait for instance to be deleted."""
        try:
            self.conn.compute.wait_for_server(self.server, status='DELETED')
        except ResourceNotFound:
            # We can 404 here is instance is already deleted
            pass

    def wait_for_stop(self):
        """Wait for instance stop."""
        self.conn.compute.wait_for_server(self.server, status='SHUTOFF')
