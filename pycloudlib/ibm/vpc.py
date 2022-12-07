from typing import Optional

from ibm_vpc import VpcV1

from pycloudlib.ibm.util import IBMException, get_first


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
    def from_existing(cls, client: VpcV1, name: str) -> "_Subnet":
        subnet = get_first(
            client.list_subnets,
            resource_name="subnets",
            filter_fn=lambda sn: sn["name"] == name,
        )
        return cls(client, subnet)

    @classmethod
    def from_default(cls, client: VpcV1, zone: str) -> "_Subnet":
        return cls.from_existing(client, f"{zone}-default-subnet")

    @property
    def id(self) -> str:
        return self._subnet["id"]

    def delete(self):
        self._client.delete_subnet(self.id)


class VPC:
    """Virtual Private Cloud class proxy for IBM VPC resource."""

    def __init__(
        self,
        client: VpcV1,
        vpc: dict,
        resource_group_id: str,
        subnet: Optional[dict] = None,
    ):
        self._client = client
        self._vpc = vpc
        self._subnet = subnet
        self._resource_group_id = resource_group_id

    @classmethod
    def create(
        cls,
        client: VpcV1,
        name: str,
        resource_group_id: str,
        zone: str,
    ) -> "VPC":
        resource_group = {"id": resource_group_id}
        vpc = client.create_vpc(
            name=name, resource_group=resource_group
        ).get_result()

        subnet = _Subnet.from_default(client, zone=zone)
        return cls(client, vpc, resource_group_id, subnet)

    @classmethod
    def from_existing(
        cls, client: VpcV1, name: str, resource_group_id: str, zone: str
    ) -> "VPC":
        vpc = get_first(
            client.list_vpcs,
            resource_name="vpcs",
            filter_fn=lambda vpc: vpc["name"] == name,
        )
        if vpc is None:
            raise IBMException(f"VPC not found: {name}")

        # TODO: try to discover an associated subnet
        subnet = _Subnet.create(
            client,
            name=f"{name}-subnet",
            zone=zone,
            resource_group_id=resource_group_id,
            vpc_id=vpc["id"],
        )
        return cls(client, vpc, resource_group_id, subnet)

    @classmethod
    def from_default(
        cls, client: VpcV1, resource_group_id: str, region: str, zone: str
    ) -> "VPC":
        default_name = f"{region}-default-vpc"
        vpc = get_first(
            client.list_vpcs,
            resource_name="vpcs",
            filter_fn=lambda vpc: vpc["name"] == default_name,
            resource_group_id=resource_group_id,
        )

        subnet_name = f"{zone}-default-subnet"
        subnet = get_first(
            client.list_subnets,
            resource_name="subnets",
            filter_fn=(
                lambda subnet: subnet["vpc"]["id"] == vpc["id"]
                and subnet["name"] == subnet_name
            ),
            resource_group_id=resource_group_id,
        )

        return cls(client, vpc, subnet, resource_group_id)

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
        self._client.delete_vpc(self.id)
