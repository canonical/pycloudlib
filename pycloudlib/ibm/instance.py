# This file is part of pycloudlib. See LICENSE file for license information.
# pylint: disable=too-many-public-methods
"""Base class for all instances to provide consistent set of functions."""

import logging
from enum import Enum, auto
from functools import partial
from itertools import chain
from typing import TYPE_CHECKING, Callable, List, Optional

from ibm_cloud_sdk_core import ApiException, DetailedResponse
from ibm_vpc import VpcV1
from ibm_vpc.vpc_v1 import Instance as _Instance
from ibm_vpc.vpc_v1 import InstanceAction as _InstanceAction

from pycloudlib.ibm._util import get_first as _get_first
from pycloudlib.ibm._util import iter_resources as _iter_resources
from pycloudlib.ibm._util import wait_until as _wait_until
from pycloudlib.ibm.errors import IBMException
from pycloudlib.instance import BaseInstance

if TYPE_CHECKING:
    from typing_extensions import TypeAlias

    _Action: TypeAlias = _InstanceAction.TypeEnum
    _Status: TypeAlias = _Instance.StatusEnum
else:
    _Action = _InstanceAction.TypeEnum
    _Status = _Instance.StatusEnum

logger = logging.getLogger(__name__)
VpcV1Fn = Callable[..., DetailedResponse]


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
        """Create Subnet."""
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
        """Instantiate Subnet by name."""
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
        """Find the default Subnet."""
        return cls.from_existing(client, f"{zone}-default-subnet", vpc_id)

    @classmethod
    def discover(cls, client: VpcV1, vpc_id: str) -> "_Subnet":
        """Discover a Subnet within a VPC."""
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
        """Subnet ID."""
        return self._subnet["id"]

    def _refresh(self) -> dict:
        self._subnet = self._client.get_subnet(self.id).get_result()
        return self._subnet

    def _wait_for_delete(self, sleep_seconds: int = 30):
        def _check_fn():
            try:
                self._refresh()
            except ApiException as e:
                if e.code == 404:
                    return True  # Instance deleted
                raise
            return False

        msg = (
            f"Subnet not terminated after {sleep_seconds} seconds. "
            "Check IBM VPC console."
        )

        _wait_until(
            _check_fn,
            timeout_seconds=sleep_seconds,
            timeout_msg_fn=lambda: msg,
        )

    def delete(self):
        """Delete Subnet."""
        self._client.delete_subnet(self.id)
        self._wait_for_delete()


class VPC:
    """Virtual Private Cloud class proxy for IBM VPC resource."""

    def __init__(
        self,
        key_pair,
        *,
        client: VpcV1,
        vpc: dict,
        resource_group_id: str,
        subnet: Optional[_Subnet] = None,
        **_kwargs,
    ):
        """Init a `VPC`."""
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
        """Create a VPC.

        Creates a Subnet and adds inbound rule to accept SSH connections to the
        default Security Group.
        """
        resource_group = {"id": resource_group_id}
        vpc = client.create_vpc(
            name=name, resource_group=resource_group
        ).get_result()

        # Allow SSH access
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
        """Find a VPC by name.

        Try to discover a Subnet within it or create it if not found.
        """
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
        """Find the `default` VPC and Subnet."""
        default_name = f"{region}-default-vpc"
        vpc = _get_first(
            client.list_vpcs,
            resource_name="vpcs",
            filter_fn=lambda vpc: vpc["name"] == default_name,
            resource_group_id=resource_group_id,
        )
        if vpc is None:
            raise IBMException(f"VPC not found: {default_name}")
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
        """VPC ID."""
        return self._vpc["id"]

    @property
    def name(self) -> str:
        """VPC name."""
        return self._vpc["name"]

    @property
    def subnet_id(self) -> str:
        """Subnet ID."""
        if self._subnet is None:
            raise IBMException("No subnet available")
        return self._subnet.id

    def delete(self) -> None:
        """Delete VPC.

        Note: This will delete all instances and subnets living in the VPC.
        """
        logger.info("Deleting VPC: %s", self.id)

        # Delete all instances of types contained in `_IBMInstanceType`
        instances_in_vpc = chain.from_iterable(
            map(
                lambda iit: _iter_resources(
                    partial(iit.list_instances, self._client),
                    resource_name="instances",
                    map_fn=lambda inst: IBMInstance.from_existing(
                        self._key_pair, client=self._client, instance=inst
                    ),
                    vpc_id=self.id,
                ),
                iter(_IBMInstanceType),
            )
        )

        for instance in instances_in_vpc:
            instance.delete(wait=True)

        if self._subnet is not None:
            self._subnet.delete()
        self._client.delete_vpc(self.id)


class _IBMInstanceType(Enum):
    """Abstracts the different instance types present in IBM VPC."""

    VSI = auto()
    BARE_METAL_SERVER = auto()

    @classmethod
    def from_instance_type(cls, instance_type: str) -> "_IBMInstanceType":
        """Translate from `instance_type` to `_IBMInstanceType`.

        Note: In IBM VPC terms, `instance_type`s are `profile`s.
        """
        if "metal" in instance_type:
            return cls.BARE_METAL_SERVER
        if "host" in instance_type:
            logger.warning(
                "%s instance_type looks like a Dedicated Host,"
                " which is not supported.",
                instance_type,
            )
        return cls.VSI

    @classmethod
    def from_raw_instance(cls, instance: dict) -> "_IBMInstanceType":
        """Determine `self` from a raw instance."""
        instance_type = instance["profile"]["name"]
        return cls.from_instance_type(instance_type)

    def create_instance(
        self, client: VpcV1, *args, **kwargs
    ) -> DetailedResponse:
        """Create instance."""
        if self == self.VSI:
            return client.create_instance(*args, **kwargs)
        if self == self.BARE_METAL_SERVER:
            return client.create_bare_metal_server(*args, **kwargs)
        raise NotImplementedError(f"Implement me for: {self}")

    def list_instances(self, client: VpcV1, **kwargs) -> DetailedResponse:
        """List instances."""
        if self == self.VSI:
            return client.list_instances(**kwargs)
        if self == self.BARE_METAL_SERVER:
            return client.list_bare_metal_servers(**kwargs)
        raise NotImplementedError(f"Implement me for: {self}")

    def delete_instance(
        self, client: VpcV1, *args, **kwargs
    ) -> DetailedResponse:
        """Delete instance."""
        if self == self.VSI:
            return client.delete_instance(*args, **kwargs)
        if self == self.BARE_METAL_SERVER:
            return client.delete_bare_metal_server(*args, **kwargs)
        raise NotImplementedError(f"Implement me for: {self}")

    def get_instance(
        self, client: VpcV1, instance_id: str, **kwargs
    ) -> DetailedResponse:
        """Get instance."""
        if self == self.VSI:
            return client.get_instance(instance_id, **kwargs)
        if self == self.BARE_METAL_SERVER:
            return client.get_bare_metal_server(instance_id, **kwargs)
        raise NotImplementedError(f"Implement me for: {self}")

    def execute_instance_action(
        self,
        client: VpcV1,
        *,
        id: str,  # pylint: disable=redefined-builtin
        action: _Action,
        force: Optional[bool] = False,
    ) -> DetailedResponse:
        """Execute instance action."""
        # Note: None of the these endpoints returns a query-able resource.
        # Thus, the only way to check if the action has been completed is
        # to directly retrieve the raw instance data.
        if self == self.VSI:
            return client.create_instance_action(id, action.value, force=force)
        if self == self.BARE_METAL_SERVER:
            if action == _Action.STOP:
                return client.stop_bare_metal_server(id)
            if action == _Action.START:
                return client.start_bare_metal_server(id)
            if action == _Action.REBOOT:
                return client.restart_bare_metal_server(id)
            raise NotImplementedError(f"Implement me for: {action}")
        raise NotImplementedError(f"Implement me for: {self}")

    def list_instance_network_interface_floating_ips(
        self, client: VpcV1, *args, **kwargs
    ) -> DetailedResponse:
        """List Floating IPs associated to a nic."""
        if self == self.VSI:
            return client.list_instance_network_interface_floating_ips(
                *args, **kwargs
            )
        if self == self.BARE_METAL_SERVER:
            return (
                client.list_bare_metal_server_network_interface_floating_ips(
                    *args, *kwargs
                )
            )
        raise NotImplementedError(f"Implement me for: {self}")

    def add_instance_network_interface_floating_ip(
        self, client: VpcV1, *, instance_id: str, **kwargs
    ) -> DetailedResponse:
        """Add Floating IP to an instance."""
        if self == self.VSI:
            return client.add_instance_network_interface_floating_ip(
                instance_id=instance_id, **kwargs
            )
        if self == self.BARE_METAL_SERVER:
            return client.add_bare_metal_server_network_interface_floating_ip(
                bare_metal_server_id=instance_id,
                **kwargs,
            )
        raise NotImplementedError(f"Implement me for: {self}")


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
        username: Optional[str] = None,
    ):
        """Set up instance."""
        super().__init__(key_pair, username=username)

        self._client = client
        self._instance = instance
        self._floating_ip = floating_ip

        # mount methods that depend on `_IBMInstanceType`:
        self._ibm_instance_type = _IBMInstanceType.from_raw_instance(instance)
        self._delete_instance = partial(
            self._ibm_instance_type.delete_instance, self._client
        )
        self._get_instance = partial(
            self._ibm_instance_type.get_instance, self._client
        )
        self._execute_instance_action = partial(
            self._ibm_instance_type.execute_instance_action,
            self._client,
            id=self.id,
        )

    @classmethod
    def with_floating_ip(
        cls,
        *args,
        client: VpcV1,
        instance: dict,
        floating_ip: dict,
        username: Optional[str] = None,
        **kwargs,
    ) -> "IBMInstance":
        """Instantiate `self` from `instance` associated to `floating_ip`."""
        nic_id = instance["primary_network_interface"]["id"]

        ibm_instance_type = _IBMInstanceType.from_raw_instance(instance)
        ibm_instance_type.add_instance_network_interface_floating_ip(
            client,
            id=floating_ip["id"],
            instance_id=instance["id"],
            network_interface_id=nic_id,
        ).get_result()

        return cls(
            *args,
            client=client,
            instance=instance,
            floating_ip=floating_ip,
            username=username,
            **kwargs,
        )

    @classmethod
    def from_existing(
        cls,
        *args,
        client: VpcV1,
        instance: dict,
        username: Optional[str] = None,
        **kwargs,
    ) -> "IBMInstance":
        """Instantiate `self` from `instance`.

        If `floating_ip` is not given, it will try to discover an associated
        Floating Ip.
        """
        floating_ip = kwargs.pop(
            "floating_ip", None
        ) or cls._discover_floating_ip(client, instance)
        return cls(
            *args,
            client=client,
            instance=instance,
            floating_ip=floating_ip,
            username=username,
            **kwargs,
        )

    @classmethod
    def find_existing(
        cls,
        *args,
        client: VpcV1,
        instance_id: str,
        username: Optional[str] = None,
        **kwargs,
    ) -> "IBMInstance":
        """Find an instance by ID."""
        instance = _IBMInstanceType.VSI.get_instance(client, instance_id)
        if not instance:
            instance = _IBMInstanceType.BARE_METAL_SERVER.get_instance(
                client, instance_id
            )

        if not instance:
            raise IBMException(f"Instance not found: {instance_id}")

        return cls.from_existing(
            *args,
            client=client,
            instance=instance,
            username=username,
            **kwargs,
        )

    @staticmethod
    def create_raw_instance(
        client: VpcV1,
        *,
        name: str,
        image_id: str,
        vpc: VPC,
        instance_type: str,
        resource_group_id: str,
        zone: str,
        user_data=None,
        key_id: str,
    ) -> dict:
        """Create and return a raw IBM instance."""
        ibm_instance_type = _IBMInstanceType.from_instance_type(instance_type)

        initialization = {
            "image": {"id": image_id},
            "keys": [{"id": key_id}],
        }

        base_proto = {
            "name": name,
            "primary_network_interface": {
                "name": "eth0",
                "subnet": {"id": vpc.subnet_id},
            },
            "zone": {"name": zone},
            "profile": {"name": instance_type},
            "resource_group": {"id": resource_group_id},
            "vpc": {"id": vpc.id},
        }

        kwargs: dict
        if ibm_instance_type == _IBMInstanceType.VSI:
            instance_prototype: dict = {
                **base_proto,
                **initialization,
                "metadata_service": {"enabled": True},
            }
            if user_data:
                instance_prototype["user_data"] = user_data

            kwargs = {"instance_prototype": instance_prototype}

        elif ibm_instance_type == _IBMInstanceType.BARE_METAL_SERVER:
            kwargs = {
                **base_proto,
                "initialization": initialization,
            }

            if user_data:
                kwargs["initialization"]["user_data"] = user_data

        else:
            raise NotImplementedError(f"Implement me for: {ibm_instance_type}")

        raw_instance = ibm_instance_type.create_instance(
            client, **kwargs
        ).get_result()
        return raw_instance

    @staticmethod
    def _discover_floating_ip(client: VpcV1, instance: dict) -> Optional[dict]:
        """Discover a floating ip associated to instance."""
        nic_id = instance["primary_network_interface"]["id"]

        ibm_instance_type = _IBMInstanceType.from_raw_instance(instance)
        floating_ips = (
            ibm_instance_type.list_instance_network_interface_floating_ips(
                client,
                instance["id"],
                network_interface_id=nic_id,
            ).get_result()["floating_ips"]
        )

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
        """Instance ID."""
        return str(self._instance["id"])

    @property
    def _floating_ip_id(self):
        return self._floating_ip["id"]

    @property
    def boot_volume_id(self) -> str:
        """Boot volume ID."""
        return self._instance["boot_volume_attachment"]["volume"]["id"]

    @property
    def _nic_id(self):
        return self._instance["primary_network_interface"]["id"]

    # pylint: disable=broad-except
    def delete(self, wait=True) -> List[Exception]:
        """Delete the instance.

        Args:
            wait: wait for instance to be deleted
        """
        exceptions = []
        try:
            self._delete_instance(self.id)
        except ApiException as e:
            if "Instance not found" not in str(e):
                exceptions.append(e)

        self._log.debug("deleting instance %s", self.id)
        if wait:
            try:
                self.wait_for_delete()
            except Exception as e:
                exceptions.append(e)

        try:
            self._client.delete_floating_ip(self._floating_ip_id)
        except ApiException as e:
            if "not found" not in str(e):
                exceptions.append(e)
        return exceptions

    def _refresh_instance(self) -> dict:
        self._instance = self._get_instance(self.id).get_result()
        return self._instance

    def _wait_for_status(self, status: _Status, sleep_seconds: int = 300):
        _wait_until(
            lambda: self._refresh_instance()["status"] == status.value,
            timeout_seconds=sleep_seconds,
            timeout_msg_fn=lambda: (
                "Expected {status.value} state, but found"
                f" {self._instance['status']} "
                f"after waiting {sleep_seconds} seconds. "
                "Check IBM VPC console for more details."
            ),
        )

    def _do_restart(self, **kwargs):
        self._log.debug("restarting instance %s", self.id)
        self._execute_instance_action(action=_Action.REBOOT)

    def shutdown(self, wait=True, **kwargs):
        """Shutdown the instance.

        Args:
            wait: wait for the instance to shutdown
        """
        self._log.debug("shutting down instance %s", self.id)
        self._execute_instance_action(action=_Action.STOP)
        if wait:
            self.wait_for_stop()

    def start(self, wait=True):
        """Start the instance.

        Args:
            wait: wait for the instance to start.
        """
        self._execute_instance_action(action=_Action.START)
        if wait:
            self.wait()

    def _wait_for_instance_start(self, **kwargs):
        """Wait for the cloud instance to be up."""
        self._wait_for_status(_Status.RUNNING)

    def wait_for_delete(self, sleep_seconds=30, raise_on_fail=False):
        """Wait for instance to be deleted."""

        def _check_fn():
            try:
                self._refresh_instance()
            except ApiException as e:
                if e.code == 404:
                    return True  # Instance deleted
                raise
            return False

        msg = (
            f"Instance not terminated after {sleep_seconds} seconds. "
            "Check IBM VPC console."
        )

        terminated = _wait_until(
            _check_fn,
            timeout_seconds=sleep_seconds,
            timeout_msg_fn=lambda: msg,
            raise_on_fail=raise_on_fail,
        )
        if not terminated:
            self._log.warning(msg)

    def wait_for_stop(self, **kwargs):
        """Wait for instance stop."""
        self._wait_for_status(_Status.STOPPED)
