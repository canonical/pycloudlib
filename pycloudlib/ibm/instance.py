# This file is part of pycloudlib. See LICENSE file for license information.
# pylint: disable=too-many-public-methods
"""Base class for all instances to provide consistent set of functions."""

import logging
from enum import Enum, auto, unique
from time import sleep
from typing import Optional

from ibm_cloud_sdk_core import ApiException
from ibm_vpc import VpcV1
from six import Iterator

from pycloudlib.ibm._util import IBMException
from pycloudlib.ibm._util import get_all as _get_all
from pycloudlib.ibm._util import get_first as _get_first
from pycloudlib.instance import BaseInstance

logger = logging.getLogger(__name__)


class _Subnet:
    def __init__(self, client: VpcV1, subnet: dict):
        self._client = client
        self._subnet = subnet

    @classmethod
    def create(
        cls,
        client: VpcV1,
        *,
        name: str,
        zone: str,
        resource_group_id: str,
        vpc_id: str,
    ):
        subnet_proto = {
            "name": name,
            "resource_group": {"id": resource_group_id},
            "vpc": {"id": vpc_id},
            "total_ipv4_address_count": 256,
            "zone": {"name": zone},
        }
        subnet = client.create_subnet(subnet_proto).get_result()
        return cls(client, subnet)

    @classmethod
    def from_existing(cls, client: VpcV1, name: str, vpc_id: str) -> "_Subnet":
        subnet = _get_first(
            client.list_subnets,
            resource_name="subnets",
            filter_fn=(
                lambda subnet: subnet["vpc"]["id"] == vpc_id
                and subnet["name"] == name
            ),
        )
        if subnet is None:
            raise IBMException(f"Subnet not found: {name}")
        return cls(client, subnet)

    @classmethod
    def from_default(cls, client: VpcV1, zone: str, vpc_id: str) -> "_Subnet":
        return cls.from_existing(client, f"{zone}-default-subnet", vpc_id)

    @classmethod
    def discover(cls, client: VpcV1, vpc_id: str) -> "_Subnet":
        subnet = _get_first(
            client.list_subnets,
            resource_name="subnets",
            filter_fn=(lambda subnet: subnet["vpc"]["id"] == vpc_id),
        )
        if subnet is None:
            raise IBMException(f"No subnet associated to vpc found: {vpc_id}")
        return cls(client, subnet)

    @property
    def id(self) -> str:
        return self._subnet["id"]

    def delete(self):
        self._client.delete_subnet(self.id)
        sleep(2)  # TODO


class VPC:
    """Virtual Private Cloud class proxy for IBM VPC resource."""

    def __init__(
        self,
        key_pair,
        client: VpcV1,
        vpc: dict,
        resource_group_id: str,
        subnet: Optional[dict] = None,
    ):
        self._key_pair = key_pair
        self._client = client
        self._vpc = vpc
        self._subnet = subnet
        self._resource_group_id = resource_group_id

    @classmethod
    def create(
        cls,
        *args,
        client: VpcV1,
        name: str,
        resource_group_id: str,
        zone: str,
        **kwargs,
    ) -> "VPC":
        resource_group = {"id": resource_group_id}
        vpc = client.create_vpc(
            name=name, resource_group=resource_group
        ).get_result()

        # Allow ssh access
        default_sg = client.get_vpc_default_security_group(
            vpc["id"]
        ).get_result()
        rule_proto = {
            "direction": "inbound",
            "ip_version": "ipv4",
            "remote": {"cidr_block": "0.0.0.0/0"},
            "port_max": 22,
            "port_min": 22,
            "protocol": "tcp",
        }
        client.create_security_group_rule(
            default_sg["id"], rule_proto
        ).get_result()

        subnet = _Subnet.create(
            client,
            name=f"{name}-subnet",
            zone=zone,
            resource_group_id=resource_group_id,
            vpc_id=vpc["id"],
        )
        return cls(
            *args,
            client=client,
            vpc=vpc,
            resource_group_id=resource_group_id,
            subnet=subnet,
            **kwargs,
        )

    @classmethod
    def from_existing(
        cls,
        *args,
        client: VpcV1,
        name: str,
        resource_group_id: str,
        zone: str,
        **kwargs,
    ) -> "VPC":
        vpc = _get_first(
            client.list_vpcs,
            resource_name="vpcs",
            filter_fn=lambda vpc: vpc["name"] == name,
        )
        if vpc is None:
            raise IBMException(f"VPC not found: {name}")

        try:
            subnet = _Subnet.discover(client, vpc_id=vpc["id"])
        except IBMException:
            subnet = _Subnet.create(
                client,
                name=f"{name}-subnet",
                zone=zone,
                resource_group_id=resource_group_id,
                vpc_id=vpc["id"],
            )

        return cls(
            *args,
            client=client,
            vpc=vpc,
            resource_group_id=resource_group_id,
            subnet=subnet,
            **kwargs,
        )

    @classmethod
    def from_default(
        cls,
        *args,
        client: VpcV1,
        resource_group_id: str,
        region: str,
        zone: str,
        **kwargs,
    ) -> "VPC":
        default_name = f"{region}-default-vpc"
        vpc = _get_first(
            client.list_vpcs,
            resource_name="vpcs",
            filter_fn=lambda vpc: vpc["name"] == default_name,
            resource_group_id=resource_group_id,
        )
        subnet = _Subnet.from_default(client, zone=zone, vpc_id=vpc["id"])
        return cls(
            *args,
            client=client,
            vpc=vpc,
            subnet=subnet,
            resource_group_id=resource_group_id,
            **kwargs,
        )

    @property
    def id(self) -> str:
        return self._vpc["id"]

    @property
    def name(self) -> str:
        return self._vpc["name"]

    @property
    def subnet_id(self) -> str:
        if self._subnet is None:
            raise IBMException("No subnet available")
        return self._subnet.id

    def delete(self) -> None:
        logger.info("Deleting VPC: %s", self.id)

        # TODO: delete baremetal and dedicated types
        instances_in_vpc = _get_all(
            self._client.list_instances,
            resource_name="instances",
            map_fn=lambda inst: IBMInstance.from_existent(
                self._key_pair, client=self._client, instance=inst
            ),
            vpc_id=self.id,
        )
        for instance in instances_in_vpc:
            instance.delete(wait=True)

        self._subnet.delete()
        self._client.delete_vpc(self.id)


def _wait(timeout_seconds: int) -> Iterator:
    for _ in range(timeout_seconds):
        yield
        sleep(1)


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


class InstanceType(Enum):
    # TODO: Add indirection to `IBMInstance` to handle types
    VSI = auto()  # Normal instances
    BARE_METAL_SERVER = auto()
    DEDICATED_HOST = auto()


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
        nic_id = instance["primary_network_interface"]["id"]

        client.add_instance_network_interface_floating_ip(
            id=floating_ip["id"],
            instance_id=instance["id"],
            network_interface_id=nic_id,
        ).get_result()

        return cls(
            *args,
            client=client,
            instance=instance,
            floating_ip=floating_ip,
            **kwargs,
        )

    @classmethod
    def from_existent(
        cls, *args, client: VpcV1, instance: dict, **kwargs
    ) -> "IBMInstance":
        floating_ip = kwargs.pop(
            "floating_ip", None
        ) or cls._discover_floating_ip(client, instance)
        return cls(
            *args,
            client=client,
            instance=instance,
            floating_ip=floating_ip,
            **kwargs,
        )

    @staticmethod
    def _discover_floating_ip(client: VpcV1, instance: dict) -> Optional[dict]:
        nic_id = instance["primary_network_interface"]["id"]

        floating_ips = client.list_instance_network_interface_floating_ips(
            instance_id=instance["id"],
            network_interface_id=nic_id,
        ).get_result()["floating_ips"]

        return floating_ips[0] if floating_ips else None

    @property
    def name(self) -> str:
        """Return instance name."""
        return str(self._instance["name"])

    @property
    def ip(self):
        """Return IP address of instance."""
        if self._floating_ip is None:
            self._floating_ip = self._discover_floating_ip(
                self._client, self._refresh_instance()
            )
        if self._floating_ip is not None:
            return self._floating_ip["address"]

        self._log.warning(
            "The instance Instance %s has no IP available", self.id
        )
        return None

    @property
    def id(self) -> str:
        return str(self._instance["id"])

    @property
    def _floating_ip_id(self):
        return self._floating_ip["id"]

    @property
    def _nic_id(self):
        return self._instance["primary_network_interface"]["id"]

    def delete(self, wait=True):
        """Delete the instance.

        Args:
            wait: wait for instance to be deleted
        """
        self._client.delete_instance(self.id)
        self._log.debug("deleting instance %s", self.id)
        if wait:
            self.wait_for_delete()

        self._client.delete_floating_ip(self._floating_ip_id)

    def _refresh_instance(self) -> dict:
        self._instance = self._client.get_instance(self.id).get_result()
        return self._instance

    def _wait_for_status(self, status: _Status, sleep_seconds: int = 300):
        instance: dict = {}
        for _ in _wait(sleep_seconds):
            instance = self._refresh_instance()
            if instance["status"] == status.value:
                return
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

    def wait_for_delete(self, sleep_seconds=30, raise_on_fail=False):
        """Wait for instance to be deleted."""
        for _ in _wait(sleep_seconds):
            try:
                self._refresh_instance()
            except ApiException as e:
                if e.code == 404:
                    return  # Instance deleted
                raise
        msg = (
            f"Instance not terminated after {sleep_seconds} seconds. "
            "Check IBM VPC console."
        )
        if raise_on_fail:
            raise TimeoutError(msg)
        self._log.warning(msg)

    def wait_for_stop(self):
        """Wait for instance stop."""
        self._wait_for_status(_Status.STOPPED)

    def add_network_interface(self) -> str:
        """Add nic to running instance."""
        raise NotImplementedError

    def remove_network_interface(self, ip_address: str):
        """Remove nic from running instance."""
        raise NotImplementedError
