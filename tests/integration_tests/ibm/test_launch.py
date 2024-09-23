import os
import pytest
from pycloudlib.ibm.cloud import IBM
from pycloudlib.ibm.instance import IBMInstance
from google.cloud import compute_v1
import time


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
    floating_ip_substring = (
        ibm_cloud._floating_ip_substring or "default-floating-ip"
    )
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
