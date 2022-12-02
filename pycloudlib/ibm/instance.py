# This file is part of pycloudlib. See LICENSE file for license information.
# pylint: disable=too-many-public-methods
"""Base class for all instances to provide consistent set of functions."""

from enum import Enum, unique
from time import sleep
from typing import Optional

from ibm_vpc import VpcV1

from pycloudlib.instance import BaseInstance


@unique
class _Status(Enum):
    DELETING = "deleting"
    FAILED = "failed"
    PENDING = "pending"
    RESTARTING = "restarting"
    RUNNING = "running"
    STARTING = "starting"
    STOPPED = "stopped"
    STOPPING = "stopping"


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
        resp = self._client.delete_instance(self.id)
        self._log.debug("deleting instance %s", self.id)
        if wait:
            _result = resp.get_result()
        # TODO floating_ip

        if wait:
            self.wait_for_delete()

    def _refresh_instance(self) -> dict:
        self._instance = self._client.get_instance(self.id).get_result()
        return self._instance

    def _wait_for_status(self, status: _Status, sleep_seconds: int = 300):
        instance: dict = {}
        for _ in range(sleep_seconds):
            instance = self._refresh_instance()
            if instance["status"] == status.value:
                return
            sleep(1)
        raise TimeoutError(
            f"Expected {status.value} state, but found {instance['status']} "
            f"after waiting {sleep_seconds} seconds. "
            "Check IBM VPC console for more details."
        )

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
        if wait:
            self.wait_for_stop()

    def start(self, wait=True):
        """Start the instance.

        Args:
            wait: wait for the instance to start.
        """
        self._execute_instance_action("start")
        if wait:
            self.wait()

    def _wait_for_instance_start(self):
        """Wait for the cloud instance to be up."""
        self._wait_for_status(_Status.RUNNING)

    def wait_for_delete(self):
        """Wait for instance to be deleted."""
        self._wait_for_status(_Status.DELETING)
        while True:  # TODO timeout
            self._refresh_instance()

    def wait_for_stop(self):
        """Wait for instance stop."""
        self._wait_for_status(_Status.STOPPED)

    def add_network_interface(self) -> str:
        """Add nic to running instance."""
        raise NotImplementedError

    def remove_network_interface(self, ip_address: str):
        """Remove nic from running instance."""
        raise NotImplementedError

