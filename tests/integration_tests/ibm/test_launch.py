import os
import pytest
from pycloudlib.ibm.cloud import IBM
from pycloudlib.ibm.instance import IBMInstance
from google.cloud import compute_v1
import time

from pycloudlib.ibm._util import iter_resources


@pytest.fixture
def ibm_cloud():
    with IBM(tag="integration-test-launch") as ibm:
        yield ibm


def manage_ssh_key(ibm: IBM, key_name):
    """Manage ssh keys for ibm instances."""
    if key_name in ibm.list_keys():
        ibm.delete_key(key_name)

    pub_key_path = "ibm-pubkey"
    priv_key_path = "ibm-privkey"
    pub_key, priv_key = ibm.create_key_pair()

    with open(pub_key_path, "w", encoding="utf-8") as f:
        f.write(pub_key)

    with open(priv_key_path, "w", encoding="utf-8") as f:
        f.write(priv_key)

    os.chmod(pub_key_path, 0o600)
    os.chmod(priv_key_path, 0o600)

    ibm.use_key(
        public_key_path=pub_key_path,
        private_key_path=priv_key_path,
        name=key_name,
    )


def configured_vpc_subnets(ibm_cloud: IBM):
    """Return subnets for the configured custom VPC."""
    vpc_name = ibm_cloud.config.get("vpc")
    if not vpc_name:
        pytest.skip("requires a custom VPC in the IBM test config")

    vpc = next(
        (
            candidate
            for candidate in iter_resources(
                ibm_cloud._client.list_vpcs,
                resource_name="vpcs",
            )
            if candidate["name"] == vpc_name
        ),
        None,
    )
    assert vpc is not None, f"Configured VPC not found: {vpc_name}"
    return list(
        iter_resources(
            ibm_cloud._client.list_subnets,
            resource_name="subnets",
            filter_fn=lambda subnet: subnet["vpc"]["id"] == vpc["id"],
        )
    )


def test_ibm_custom_vpc_implicit_zone_selects_first_subnet(ibm_cloud: IBM):
    """Preserve first-subnet selection when IBM config omits zone."""
    if ibm_cloud.config.get("zone"):
        pytest.skip("requires zone to be omitted from the IBM test config")

    subnets = configured_vpc_subnets(ibm_cloud)
    expected_zone = f"{ibm_cloud.region}-1"
    if not subnets:
        pytest.skip("requires an existing subnet to avoid creating resources")

    selected_subnet = ibm_cloud._client.get_subnet(ibm_cloud.vpc.subnet_id).get_result()

    assert ibm_cloud.zone == expected_zone
    assert selected_subnet["id"] == subnets[0]["id"]


def test_ibm_custom_vpc_configured_zone_selects_matching_subnet(ibm_cloud: IBM):
    """Select a matching subnet when IBM config supplies zone."""
    configured_zone = ibm_cloud.config.get("zone")
    if not configured_zone:
        pytest.skip("requires zone in the IBM test config")
    configured_zone = str(configured_zone).lower()

    subnets = configured_vpc_subnets(ibm_cloud)
    matching_subnet = next(
        (subnet for subnet in subnets if subnet["zone"]["name"] == configured_zone),
        None,
    )
    if matching_subnet is None:
        pytest.skip("requires an existing matching subnet to avoid creating resources")
    if subnets[0]["id"] == matching_subnet["id"]:
        pytest.skip("first listed subnet must be in another zone to reproduce the bug")

    selected_subnet = ibm_cloud._client.get_subnet(ibm_cloud.vpc.subnet_id).get_result()

    assert selected_subnet["id"] == matching_subnet["id"]


def test_ibm_launch(ibm_cloud: IBM):
    """
    Test launching an IBM instance.

    This tests the following:
    - The instance is launched successfully
    - The instance is reachable via SSH
    - The instance has a floating IP as expected
    - The instance name was set correctly
    """
    time_id = time.time_ns()
    image_id = ibm_cloud.released_image("noble")
    floating_ip_substring = ibm_cloud._floating_ip_substring or "default-floating-ip"
    unique_instance_name = f"integration-test-launch-instance-{time_id}"
    # create ssh_keys for use
    manage_ssh_key(ibm_cloud, f"integration-test-key-{time_id}")
    with ibm_cloud.launch(
        image_id=image_id,
        floating_ip_substring=floating_ip_substring,
        name=unique_instance_name,
    ) as inst:
        inst: IBMInstance  # type hint for IDE
        # wait for instance to come online
        inst.wait()
        # assert hostname is the same as the instance name
        assert inst.execute("hostname").strip() == unique_instance_name
        # assert that the instance has a floating IP as expected
        assert inst._floating_ip is not None
        assert floating_ip_substring in inst._floating_ip["name"]
