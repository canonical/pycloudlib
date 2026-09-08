# This file is part of pycloudlib. See LICENSE file for license information.
"""Module for IBM cloud tests."""

from io import StringIO
from typing import List
from unittest import mock

import pytest

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


def _mocked_ibm(**kwargs):
    with mock.patch("pycloudlib.cloud.BaseCloud._get_ssh_keys"), mock.patch.multiple(
        "pycloudlib.ibm.cloud",
        IAMAuthenticator=mock.DEFAULT,
        ResourceManagerV2=mock.DEFAULT,
        VpcV1=mock.DEFAULT,
    ):
        return IBM(tag="test", timestamp_suffix=False, **kwargs)


@pytest.mark.parametrize(
    "zone, expected_zone, expected_selection",
    (
        (None, "us-south-1", False),
        ("US-SOUTH-2", "us-south-2", True),
    ),
)
def test_custom_vpc_preserves_constructor_zone_intent(
    zone: str, expected_zone: str, expected_selection: bool
):
    """Distinguish an omitted zone from a constructor-supplied zone."""
    cloud = _mocked_ibm(
        resource_group="Default",
        vpc="custom-vpc",
        api_key="api-key",
        region="US-SOUTH",
        zone=zone,
    )
    cloud._resource_group_id = "resource-group-id"

    with mock.patch(
        "pycloudlib.ibm.cloud.VPC.from_existing",
        return_value=mock.sentinel.vpc,
    ) as from_existing:
        assert cloud.vpc is mock.sentinel.vpc

    assert cloud.zone == expected_zone
    assert from_existing.call_args.kwargs["select_subnet_by_zone"] is expected_selection


def test_custom_vpc_treats_configured_zone_as_supplied():
    """Use zone-aware subnet selection for a configured zone."""
    config = StringIO(
        """[ibm]
resource_group = "Default"
vpc = "custom-vpc"
api_key = "api-key"
region = "us-south"
zone = "US-SOUTH-2"
"""
    )
    cloud = _mocked_ibm(config_file=config)
    cloud._resource_group_id = "resource-group-id"

    with mock.patch(
        "pycloudlib.ibm.cloud.VPC.from_existing",
        return_value=mock.sentinel.vpc,
    ) as from_existing:
        assert cloud.vpc is mock.sentinel.vpc

    assert cloud.zone == "us-south-2"
    assert from_existing.call_args.kwargs["select_subnet_by_zone"] is True


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
