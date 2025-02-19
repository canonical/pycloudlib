"""Integration tests for Oracle's utility functions."""

import logging

import pytest

from pycloudlib.oci.cloud import OCI
from pycloudlib.types import NetworkingConfig, NetworkingType

logger = logging.getLogger(__name__)


@pytest.fixture
def oci_cloud():
    """Fixture to create an OCI cloud instance."""
    with OCI(
        tag="oracle-integrations-test-utils",
        vcn_name="ipv6-vcn",
        region="us-ashburn-1",
        compartment_id="ocid1.compartment.oc1..aaaaaaaayyvhlkxdjkhzu56is7qenv35h4jfh26oconxsro4qr2qx6ezgbpq",
        availability_domain="qIZq:US-ASHBURN-AD-2",
    ) as oracle_cloud:
        yield oracle_cloud


# These are pre-existing subnets that I have created in my Oracle Cloud account.
# this is not immediately reproducible by others, but all they need to do is create 3 subnets
# that match the below configurations and update the following variables with the new subnet ids.
# This is the only way I could feel confident that my subnet selection logic is working with the
# new networking configuration options as expected.
IPV6_PUBLIC_SUBNET_ID = (
    "ocid1.subnet.oc1.iad.FILL_THIS_IN"
)
DUAL_STACK_PUBLIC_SUBNET_ID = (
    "ocid1.subnet.oc1.iad.FILL_THIS_IN"
)
DUAL_STACK_PRIVATE_SUBNET_ID = (
    "ocid1.subnet.oc1.iad.FILL_THIS_IN"
)


@pytest.mark.parametrize(
    ["networking_type", "private", "expected_subnet_id"],
    [
        pytest.param(
            NetworkingType.IPV6,
            False,
            IPV6_PUBLIC_SUBNET_ID,
            id="ipv6_public",
        ),
        pytest.param(
            NetworkingType.DUAL_STACK,
            True,
            DUAL_STACK_PRIVATE_SUBNET_ID,
            id="dual_stack_private",
        ),
        pytest.param(
            NetworkingType.DUAL_STACK,
            False,
            DUAL_STACK_PUBLIC_SUBNET_ID,
            id="dual_stack_public",
        ),
        pytest.param(
            NetworkingType.IPV4,
            False,
            DUAL_STACK_PUBLIC_SUBNET_ID,
            id="ipv4_public",
        ),
        pytest.param(
            NetworkingType.IPV4,
            True,
            DUAL_STACK_PRIVATE_SUBNET_ID,
            id="ipv4_private",
        ),
    ],
)
def test_oci_subnet_finding(oci_cloud: OCI, networking_type, private, expected_subnet_id):
    """
    Test finding a subnet in OCI.

    We are validating that the correct subnet is found based on the type of networking and whether
    the instance should be publicly accessible or not.
    """
    network_config: NetworkingConfig = NetworkingConfig(
        networking_type=networking_type,
        private=private,
    )
    subnet_id = oci_cloud.find_compatible_subnet(
        networking_config=network_config,
    )

    logger.info(
        f"Found subnet ID: {subnet_id} for networking type: {networking_type} "
        f"and privacy: {private}"
    )
    assert subnet_id == expected_subnet_id, (
        f"Expected subnet ID: {expected_subnet_id} but got: {subnet_id}",
    )
