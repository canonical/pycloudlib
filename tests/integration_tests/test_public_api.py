import ipaddress
import logging
import random
from contextlib import suppress
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

import pycloudlib
from pycloudlib.cloud import BaseCloud, ImageType
from pycloudlib.instance import BaseInstance
from pycloudlib.util import LTS_RELEASES, UBUNTU_RELEASE_VERSION_MAP

cloud_config = """\
#cloud-config
runcmd:
  - echo 'hello' >> /var/tmp/example.txt
"""

logger = logging.getLogger(__name__)

# prevent boto libraries from spamming the console
logging.getLogger("botocore").setLevel(logging.INFO)
logging.getLogger("boto3").setLevel(logging.INFO)


def _random_tag():
    """
    Create tag for cloud instance with 10 random characters in the end.

    This is needed when running tests in parallel to avoid tag conflicts.

    Returns:
        str: tag for cloud instance
    """
    return f"pycl-test-{"".join(random.choices('abcdefghijklmnopqrstuvwxyz', k=10))}"


@pytest.fixture
def cloud(request):
    cloud_instance: BaseCloud
    with request.param(
        tag=_random_tag(),  # add random tag to avoid conflicts when running tests in parallel
        timestamp_suffix=True,
    ) as cloud_instance:
        logger.info("Cloud tag: %s", cloud_instance.tag)
        yield cloud_instance


def assert_example_output(instance: BaseInstance):
    example_output = instance.execute("cat /var/tmp/example.txt").stdout
    assert example_output == "hello"


def exercise_push_pull(instance: BaseInstance):
    with TemporaryDirectory() as tmpdir:
        push_path = Path(tmpdir).joinpath("pushed")
        push_path.write_text("pushed", encoding="utf-8")
        instance.push_file(str(push_path), "/var/tmp/pushed")
        assert "pushed" == instance.execute("cat /var/tmp/pushed").stdout.strip()

        instance.execute("echo 'pulled' > /var/tmp/pulled")
        pull_path = Path(tmpdir).joinpath("pulled")
        instance.pull_file("/var/tmp/pulled", str(pull_path))
        assert pull_path.read_text(encoding="utf-8").strip() == "pulled"


def exercise_instance(instance: BaseInstance):
    assert instance.name is not None
    assert ipaddress.ip_address(instance.ip)

    with suppress(NotImplementedError):
        ip_address = instance.add_network_interface()
        try:
            assert ipaddress.ip_address(ip_address)
        finally:
            instance.remove_network_interface(ip_address)

    exercise_push_pull(instance)

    assert_example_output(instance)
    boot_id = instance.get_boot_id()
    instance.restart()
    assert boot_id != instance.get_boot_id()

    assert_example_output(instance)
    instance.shutdown()

    instance.start()
    assert_example_output(instance)


@pytest.mark.parametrize(
    "cloud",
    [
        pytest.param(pycloudlib.Azure, id="azure", marks=pytest.mark.main_check),
        pytest.param(pycloudlib.EC2, id="ec2", marks=pytest.mark.main_check),
        pytest.param(pycloudlib.GCE, id="gce", marks=pytest.mark.main_check),
        pytest.param(pycloudlib.IBM, id="ibm"),
        pytest.param(pycloudlib.LXDContainer, id="lxd_container", marks=pytest.mark.ci),
        pytest.param(pycloudlib.LXDVirtualMachine, id="lxd_vm"),
        pytest.param(pycloudlib.OCI, id="oci"),
        pytest.param(pycloudlib.Qemu, id="qemu"),
        pytest.param(pycloudlib.VMWare, id="vmware"),
        # For openstack we first need a reliable way of obtaining the
        # image id
        # pytest.param(pycloudlib.Openstack, id="openstack"),
    ],
    indirect=True,
)
def test_public_api(cloud: BaseCloud):
    """Shallow test of (most) public functions in the base API."""
    latest_lts = LTS_RELEASES[-1]
    print(f"Using Ubuntu {latest_lts} release")
    try:
        image_id = cloud.released_image(release=latest_lts)
    except NotImplementedError:
        image_id = cloud.daily_image(release=latest_lts)
    with suppress(NotImplementedError):
        # Not sure there's a great way to test this other than not raising
        cloud.image_serial(image_id)

    with cloud.launch(image_id=image_id, user_data=cloud_config) as instance:
        instance.wait()
        exercise_instance(instance)
        instance.clean()
        instance.execute("sudo rm /var/tmp/example.txt")
        snapshot_id = cloud.snapshot(instance)

    instance_from_snapshot = cloud.launch(image_id=snapshot_id, user_data=cloud_config)
    instance_from_snapshot.wait()
    exercise_instance(instance_from_snapshot)

    latest_devel_release = sorted(
        UBUNTU_RELEASE_VERSION_MAP.items(),
        key=lambda items: items[1],
    )[-1][0]
    print(f"Checking latest daily devel release image: {latest_devel_release}")
    daily_devel_image_id = cloud.daily_image(release=latest_devel_release)
    assert daily_devel_image_id, (
        "Unable to find daily development image for " f"{cloud._type}:{latest_devel_release}"
    )
    print(f"Checking latest minimal daily devel image: {latest_devel_release}")

    if isinstance(cloud, pycloudlib.LXDContainer):
        print(f"Checking latest daily minimal image: {latest_devel_release}")


@pytest.mark.parametrize(
    "cloud",
    [
        pytest.param(pycloudlib.EC2, id="ec2", marks=pytest.mark.main_check),
        pytest.param(pycloudlib.GCE, id="gce", marks=pytest.mark.main_check),
        pytest.param(pycloudlib.LXDContainer, id="lxd_container", marks=pytest.mark.ci),
        pytest.param(pycloudlib.LXDVirtualMachine, id="lxd_vm"),
    ],
    indirect=True,
)
def test_public_api_minimal_images(cloud: BaseCloud):
    latest_lts = LTS_RELEASES[-1]
    print(f"Checking latest {cloud.__class__.__name__} daily minimal image: {latest_lts}")
    released_minimal_image_id = cloud.daily_image(release=latest_lts, image_type=ImageType.MINIMAL)
    with cloud.launch(image_id=released_minimal_image_id) as instance:
        instance.wait()
        assert "status: done" == instance.execute("cloud-init status").stdout
        assert "minimal" in instance.execute("grep build_name /etc/cloud/build.info").stdout
        instance.delete()
