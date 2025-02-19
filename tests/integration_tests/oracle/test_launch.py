"""
Integration test that exercise functionality specific to Oracle's launch function.

The basic lifecycle stuff is already tested in `tests/integration_tests/test_public_api.py`, but
these tests go beyond the standard tests that exercise the base cloud agnostic functionality.
"""

import json
import logging

import pytest

from pycloudlib.oci.cloud import OCI
from pycloudlib.types import NetworkingConfig, NetworkingType

logger = logging.getLogger(__name__)


# create fixture that provides the oracle cloud object
@pytest.fixture(scope="module")
def oracle_cloud():
    """Provide an OCI cloud instance for tests with automatic cleanup.

    Returns:
        An OCI cloud instance configured for testing.
    """
    # make sure region, AD, and compartment_id are set in your pycloudlib.toml config file
    # use context manager - instances will be deleted automatically after the test
    with OCI(
        tag="oracle-integrations-test-launch",
    ) as oracle_cloud:
        yield oracle_cloud


class TestOracleLaunch:
    """
    Test Oracle Cloud Infrastructure instance launch functionality.

    This class contains tests specific to the OCI launch method,
    including various network configurations.
    """

    @pytest.mark.parametrize(
        ("instance_type",),
        [
            pytest.param(
                "VM.Standard2.1",
                id="VM",
            ),
            pytest.param(
                "BM.Optimized3.36",
                id="BM",
            ),
        ],
    )
    @pytest.mark.parametrize(
        (
            "primary_private",
            "primary_networking_type",
            "secondary_private",
            "secondary_networking_type",
        ),
        [
            # both public ipv4
            pytest.param(
                False,
                NetworkingType.IPV4,
                True,
                NetworkingType.IPV4,
                id="both_public_ipv4",
            ),
            # both public ipv6
            pytest.param(
                False,
                NetworkingType.IPV6,
                True,
                NetworkingType.IPV6,
                id="both_public_ipv6",
            ),
            # primary public dual stack, secondary private ipv4
            pytest.param(
                False,
                NetworkingType.DUAL_STACK,
                True,
                NetworkingType.DUAL_STACK,
                id="public_dual_stack_private_dual_stack",
            ),
        ],
    )
    def test_launch_with_networking_configs(
        self,
        oracle_cloud: OCI,
        primary_private: bool,
        primary_networking_type: NetworkingType,
        secondary_private: bool,
        secondary_networking_type: NetworkingType,
        instance_type: str,
    ):
        """Test OCI instance launch with various networking configurations.

        This test verifies that instances can be launched with different
        combinations of networking configurations (IPv4, IPv6, dual-stack)
        for both primary and secondary network interfaces.

        Args:
            oracle_cloud (OCI): The OCI cloud fixture.
            primary_private (bool): Whether primary NIC should be private.
            primary_networking_type (NetworkingType): Network type for primary NIC.
            secondary_private (bool): Whether secondary NIC should be private.
            secondary_networking_type (NetworkingType): Network type for secondary NIC.
            instance_type (str): OCI instance type to launch.

        Test Steps:
            1. Launch an instance with the specified primary networking configuration and
                instance type
            2. Add a secondary network interface with the specified secondary networking
                configuration
            3. Restart the instance to apply the changes (As of 20250226 cloud-init does not support
                hotplugging nics on Oracle)
            4. Verify that the instance has the expected number of VNICs in IMDS
        """
        primary_networking_config = NetworkingConfig(
            private=primary_private,
            networking_type=primary_networking_type,
        )

        logger.info("Launching instance...")
        instance = oracle_cloud.launch(
            image_id="ocid1.image.oc1.iad.aaaaaaaasukfowgzghuwrljl4ohlpv3uadhm5sn5dderkhhyymelebrzoima",
            primary_network_config=primary_networking_config,
            instance_type=instance_type,
        )
        logger.info("Instance launched. Waiting for instance to be ready...")
        instance.wait()
        logger.info("Instance is ready!")
        assert instance.execute("true").ok

        if primary_networking_config.networking_type == NetworkingType.IPV6:
            imds_vnics_url = "curl http://[fd00:c1::a9fe:a9fe]/opc/v1/vnics"
        else:
            imds_vnics_url = "curl http://169.254.169.254/opc/v1/vnics"

        secondary_networking_config = NetworkingConfig(
            private=secondary_private,
            networking_type=secondary_networking_type,
        )
        instance.add_network_interface(
            nic_index=(1 if instance_type == "BM.Optimized3.36" else 0),
            networking_config=secondary_networking_config,
        )

        # run cloud-init clean and restart instance now that secondary NIC has been added
        logger.info("Running cloud-init clean and restarting instance...")
        instance.execute("cloud-init clean", use_sudo=True)
        instance.restart(wait=True)

        logger.info("Getting VNIC data from IMDS at '%s'...", imds_vnics_url)
        imds_response_2 = instance.execute(f"curl -s {imds_vnics_url}").stdout
        vnic_data_2 = json.loads(imds_response_2)
        logger.info("VNIC data from IMDS after adding secondary NIC: %s", imds_response_2)
        assert len(vnic_data_2) == 2, "Expected IMDS to return 2 VNICs after adding secondary NIC"
