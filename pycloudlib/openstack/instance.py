"""Openstack instance type."""

import time
from itertools import chain
from typing import List, Optional

import openstack
from openstack.exceptions import (
    BadRequestException,
    ConflictException,
    ResourceNotFound,
)

from pycloudlib.errors import PycloudlibError
from pycloudlib.instance import BaseInstance


class OpenstackInstance(BaseInstance):
    """Openstack instance object."""

    _type = "openstack"

    def __init__(
        self,
        key_pair,
        instance_id,
        network_id,
        connection=None,
        *,
        username: Optional[str] = None,
    ):
        """Set up the instance.

        Args:
            key_pair: A KeyPair for SSH interactions
            instance_id: The instance id representing the cloud instance
            network_id: if of the network this instance was created on
            connection: The connection used to create this instance.
                If None, connection will be created.
            username: username to use when connecting via SSH
        """
        super().__init__(key_pair, username=username)
        self.instance_id = instance_id

        if not connection:
            connection = openstack.connect()
        self.network_id = network_id
        self.conn = connection

        self.server = self.conn.compute.get_server(instance_id)

        self.delete_floating_ip = False
        self.floating_ip = self._get_existing_floating_ip()
        if self.floating_ip is None:
            self.floating_ip = self._create_and_attach_floating_ip()
            self.delete_floating_ip = True
        self.added_local_ports: List = []

    def _get_existing_floating_ip(self):
        server_addresses = chain(*self.server.addresses.values())
        server_ips = [addr["addr"] for addr in server_addresses]
        for floating_ip in self.conn.network.ips():
            if floating_ip["floating_ip_address"] in server_ips:
                return floating_ip
        return None

    def _create_and_attach_floating_ip(self):
        floating_ip = self.conn.create_floating_ip(wait=True)
        tries = 30
        for _ in range(tries):
            try:
                self.conn.compute.add_floating_ip_to_server(
                    self.server, floating_ip.floating_ip_address
                )
                break
            except BadRequestException as e:
                if "Instance network is not ready yet" in str(e):
                    time.sleep(1)
                    continue
                raise e
        return floating_ip

    def __repr__(self):
        """Create string representation of class."""
        return "{}(instance_id={})".format(
            self.__class__.__name__, self.server.id
        )

    @property
    def id(self) -> str:
        """Return instance id."""
        return self.instance_id

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
                return response["output"]
            self._log.debug("Console output not yet available; sleeping")
            time.sleep(5)
        return "No console output"

    # pylint: disable=broad-except
    def delete(self, wait=True) -> List[Exception]:
        """Delete the instance.

        Args:
            wait: wait for instance to be deleted
        """
        exceptions = []
        try:
            self.conn.compute.delete_server(self.server.id)
        except Exception as e:
            exceptions.append(e)

        if self.delete_floating_ip:
            try:
                self.conn.delete_floating_ip(self.floating_ip.id)
            except Exception as e:
                exceptions.append(e)
        for port_id in self.added_local_ports:
            try:
                self.conn.network.delete_port(
                    port=port_id, ignore_missing=True
                )
            except Exception as e:
                exceptions.append(e)
        if wait:
            self.wait_for_delete()
        return exceptions

    def _do_restart(self, **kwargs):
        """Restart the instance."""
        self.shutdown(wait=True)
        self.start(wait=False)

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
            if "while it is in vm_state active" in str(e):
                return
        if wait:
            self.wait()

    def _wait_for_instance_start(self, **kwargs):
        """Wait for instance to be up."""
        self.conn.compute.wait_for_server(self.server, status="ACTIVE")

    def wait_for_delete(self):
        """Wait for instance to be deleted."""
        try:
            self.conn.compute.wait_for_server(self.server, status="DELETED")
        except ResourceNotFound:
            # We can 404 here is instance is already deleted
            pass

    def wait_for_stop(self, **kwargs):
        """Wait for instance stop."""
        self.conn.compute.wait_for_server(self.server, status="SHUTOFF")

    def add_network_interface(self, **kwargs) -> str:
        """Add nic to running instance.

        Returns IP address in string form
        """
        port = self.conn.network.create_port(
            network_id=self.network_id,
        )
        self.added_local_ports.append(port.id)
        interface = self.conn.compute.create_server_interface(
            server=self.server.id, port_id=port.id
        )
        return interface["fixed_ips"][0]["ip_address"]

    def _get_port_id_by_ip(self, ip_address: str):
        ports = self.conn.network.ports()
        for port in ports:
            for ip in port["fixed_ips"]:
                if ip["ip_address"] == ip_address:
                    return port
        raise PycloudlibError(
            "Could not find port with IP: {}".format(ip_address)
        )

    def remove_network_interface(self, ip_address: str):
        """Remove nic from running instance."""
        port = self._get_port_id_by_ip(ip_address)
        self.conn.network.delete_port(
            port=port.id,
        )
        try:
            self.added_local_ports.remove(port.id)
        except ValueError:
            self._log.warning(
                "Expected port to be in added_local_ports list "
                "but was not: %s",
                port.id,
            )
