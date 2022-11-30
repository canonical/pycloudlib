from typing import Optional

from ibm_vpc import VpcV1

from pycloudlib.ibm.util import get_all, get_first


class VPC:
    """Virtual Private Cloud class proxy for IBM VPC resource."""

    def __init__(
        self, client: VpcV1, vpc: dict, subnet: dict, resource_group_id: str
    ):
        self._client = client
        self._vpc = vpc
        self._subnet = subnet
        self._resource_group_id = resource_group_id

    @classmethod
    def create(cls, client: VpcV1, name: str) -> "VPC":
        raise NotImplementedError

    @classmethod
    def from_existing(cls, client: VpcV1, vpc_id: str) -> "VPC":
        raise NotImplementedError

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
        return self._subnet["id"]

    def delete(self) -> None:
        ...
