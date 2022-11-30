# This file is part of pycloudlib. See LICENSE file for license information.
# pylint: disable=too-many-public-methods
"""Base class for all instances to provide consistent set of functions."""

from typing import Optional

from ibm_vpc import VpcV1

from pycloudlib.instance import BaseInstance


class IBMInstance(BaseInstance):
    """Base instance object."""

    _type = "ibm"

    def __init__(
        self,
        key_pair,
        *,
        client: VpcV1,
        instance: dict,
        floating_ip: Optional[dict] = None,
    ):
        """Set up instance."""
        super().__init__(key_pair)

        self._client = client
        self._instance = instance
        self._floating_ip = floating_ip

    @property
    def name(self) -> str:
        """Return instance name."""
        return str(self._instance["name"])

    @property
    def ip(self):
        """Return IP address of instance."""
        if self._floating_ip is not None:
            return self._floating_ip["address"]
        # TODO look for floating_ip
        raise NotImplementedError

    @property
    def id(self) -> str:
        return str(self._instance["id"])

    def delete(self, wait=True):
        """Delete the instance.

        Args:
            wait: wait for instance to be deleted
        """
        self._log.debug("deleting instance %s", self.id)
        resp = self._client.delete_instance(self.id)
        if wait:
            _result = resp.get_result()
        # TODO floating_ip

    def _execute_instance_action(self, action: str, force: bool = False):
        # Note: This endpoint returns a resource that it is not query-able.
        # Thus, at the moment we cannot directly know the status of an action.
        self._client.create_instance_action(self.id, action, force=force)

    def _do_restart(self, **kwargs):
        self._log.debug("restarting instance %s", self.id)
        self._execute_instance_action("reboot")

    def shutdown(self, wait=True, **kwargs):
        """Shutdown the instance.

        Args:
            wait: wait for the instance to shutdown
        """
        self._log.debug("shutting down instance %s", self.id)
        self._execute_instance_action("stop")
        self._client

        # TODO wait

    def start(self, wait=True):
        """Start the instance.

        Args:
            wait: wait for the instance to start.
        """
        self._execute_instance_action("start")

        # TODO wait

    def _wait_for_instance_start(self):
        """Wait for the cloud instance to be up.

        Subclasses should implement this if their cloud provides a way of
        detecting when an instance has started through their API.
        """
        # TODO

    def wait_for_delete(self):
        """Wait for instance to be deleted."""
        raise NotImplementedError

    def wait_for_stop(self):
        """Wait for instance stop."""
        raise NotImplementedError

    def add_network_interface(self) -> str:
        """Add nic to running instance."""
        raise NotImplementedError

    def remove_network_interface(self, ip_address: str):
        """Remove nic from running instance."""
        raise NotImplementedError

    @classmethod
    def with_floating_ip(
        cls, *args, client: VpcV1, instance: dict, floating_ip: dict, **kwargs
    ) -> "IBMInstance":
        primary_network_interface_id = instance["primary_network_interface"][
            "id"
        ]

        client.add_instance_network_interface_floating_ip(
            id=floating_ip["id"],
            instance_id=instance["id"],
            network_interface_id=primary_network_interface_id,
        ).get_result()

        return cls(
            *args,
            client=client,
            instance=instance,
            floating_ip=floating_ip,
            **kwargs,
        )
