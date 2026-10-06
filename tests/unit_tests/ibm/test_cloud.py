# This file is part of pycloudlib. See LICENSE file for license information.
"""Module for IBM cloud tests."""

from typing import List
from unittest import mock

import pytest
from ibm_cloud_sdk_core import ApiException

from pycloudlib.errors import InvalidTagNameError, PycloudlibTimeoutError
from pycloudlib.ibm.cloud import (
    IBM,
)

M_PATH = "pycloudlib.ibm._util."

rule1 = "All letters must be lowercase"
rule2 = "Must be between 1 and 63 characters long"
rule3 = "Must not start or end with a hyphen"
rule4 = "Must be alphanumeric and hyphens only"
rule5 = "Must start with a letter"


@pytest.mark.parametrize(
    "tag, rules_failed",
    [
        ("tag123", []),
        ("123tag", [rule5]),
        ("TAG", [rule1]),
        ("TAG-", [rule1, rule3]),
        ("-tag_", [rule3, rule4]),
        ("-", [rule3]),
        ("x" * 64, [rule2]),
        ("", [rule2]),
        ("x" * 63, []),
        ("x", []),
        ("1t a_g-", [rule3, rule4, rule5]),
        ("t.a.g", [rule4]),
    ],
)
def test_validate_tag(tag: str, rules_failed: List[str]):
    if len(rules_failed) == 0:
        # test that no exception is raised
        IBM._validate_tag(tag)
    else:
        with pytest.raises(InvalidTagNameError) as exc_info:
            IBM._validate_tag(tag)
        assert tag in str(exc_info.value)
        for rule in rules_failed:
            assert rule in str(exc_info.value)


@pytest.mark.mock_ssh_keys
class TestIBM:
    @pytest.fixture
    def cloud(self):
        with mock.patch("pycloudlib.ibm.cloud.VpcV1"):
            cloud = IBM(
                tag="test-subnet-cleanup",
                api_key="api-key",
                resource_group="resource-group",
                region="us-south",
                vpc="custom-vpc",
            )
        cloud._resource_group_id = "resource-group-id"
        cloud._client.list_vpcs.return_value.get_result.return_value = {
            "vpcs": [{"id": "vpc-id", "name": "custom-vpc"}]
        }
        return cloud

    @pytest.mark.parametrize("lookup", ["vpc", "get_or_create_vpc"])
    @pytest.mark.parametrize("matching_subnet", [True, False])
    def test_clean_custom_vpc_subnets(self, cloud, lookup, matching_subnet):
        """clean() deletes only a subnet created in an existing VPC."""
        client = cloud._client
        client.list_subnets.return_value.get_result.return_value = {
            "subnets": [
                {
                    "id": "existing-subnet",
                    "vpc": {"id": "vpc-id"},
                    "zone": {"name": "us-south-1" if matching_subnet else "us-south-2"},
                }
            ]
        }
        client.create_subnet.return_value.get_result.return_value = {"id": "created-subnet"}
        client.get_subnet.side_effect = ApiException(404)

        vpc = cloud.vpc if lookup == "vpc" else cloud.get_or_create_vpc("custom-vpc")

        assert vpc.subnet_id == ("existing-subnet" if matching_subnet else "created-subnet")
        assert cloud.clean() == []
        assert len(cloud.created_subnets) == (0 if matching_subnet else 1)
        if matching_subnet:
            client.create_subnet.assert_not_called()
            client.delete_subnet.assert_not_called()
        else:
            client.delete_subnet.assert_called_once_with("created-subnet")
        client.delete_vpc.assert_not_called()

    def test_clean_continues_after_subnet_failure(self, cloud):
        """A failed subnet deletion is reported and the rest of cleanup still runs."""
        manager = mock.Mock()
        instance = mock.Mock()
        subnet = mock.Mock()
        vpc = mock.Mock()
        error = RuntimeError("subnet deletion failed")
        subnet.delete.side_effect = error
        cloud.created_instances.append(instance)
        cloud.created_subnets.append(subnet)
        cloud.created_vpcs.append(vpc)
        cloud.created_keys.append("key-id")
        manager.attach_mock(instance, "instance")
        manager.attach_mock(subnet, "subnet")
        manager.attach_mock(vpc, "vpc")
        manager.attach_mock(cloud._client, "client")

        assert cloud.clean() == [error]
        assert cloud.created_subnets == [subnet]
        assert manager.mock_calls == [
            mock.call.instance.delete(),
            mock.call.subnet.delete(),
            mock.call.vpc.delete(),
            mock.call.client.delete_key("key-id"),
        ]
