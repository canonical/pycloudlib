import ipaddress
from contextlib import contextmanager, suppress
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Generator, Type

import pytest

import pycloudlib
from pycloudlib.cloud import BaseCloud
from pycloudlib.instance import BaseInstance
from pycloudlib.util import LTS_RELEASES

cloud_config = """\
#cloud-config
runcmd:
  - echo 'hello' > /var/tmp/example.txt
"""


@contextmanager
def launch_instance(
    cloud: BaseCloud, **kwargs
) -> Generator[BaseInstance, None, None]:
    instance = cloud.launch(**kwargs)
    try:
        yield instance
    finally:
        instance.delete()


def assert_example_output(instance: BaseInstance):
    example_output = instance.execute("cat /var/tmp/example.txt").stdout
    assert example_output == "hello"


def exercise_push_pull(instance: BaseInstance):
    with TemporaryDirectory() as tmpdir:
        push_path = Path(tmpdir).joinpath("pushed")
        push_path.write_text("pushed", encoding="utf-8")
        instance.push_file(str(push_path), "/var/tmp/pushed")
        assert (
            "pushed" == instance.execute("cat /var/tmp/pushed").stdout.strip()
        )

        instance.execute("echo 'pulled' > /var/tmp/pulled")
        pull_path = Path(tmpdir).joinpath("pulled")
        instance.pull_file("/var/tmp/pulled", str(pull_path))
        assert pull_path.read_text(encoding="utf-8").strip() == "pulled"


def exercise_instance(instance: BaseInstance):
    with suppress(NotImplementedError):
        assert instance.name is not None

    with suppress(NotImplementedError):
        assert ipaddress.ip_address(instance.ip)

    with suppress(NotImplementedError):
        ip_address = instance.add_network_interface()
        try:
            assert ipaddress.ip_address(ip_address)
        finally:
            instance.remove_network_interface(ip_address)

    exercise_push_pull(instance)

    assert_example_output(instance)
    instance.execute("sync")
    boot_id = instance.get_boot_id()
    instance.restart()
    assert boot_id != instance.get_boot_id()

    assert_example_output(instance)
    instance.shutdown()

    instance.start()
    assert_example_output(instance)


@pytest.mark.parametrize(
    "CloudType",
    [
        pytest.param(pycloudlib.Azure, id="azure"),
        pytest.param(pycloudlib.EC2, id="ec2"),
        pytest.param(pycloudlib.GCE, id="gce"),
        pytest.param(pycloudlib.IBM, id="ibm"),
        pytest.param(pycloudlib.LXDContainer, id="lxd_container"),
        pytest.param(pycloudlib.LXDVirtualMachine, id="lxd_vm"),
        pytest.param(pycloudlib.OCI, id="oci"),
        pytest.param(pycloudlib.Openstack, id="openstack"),
    ],
)
def test_public_api(CloudType: Type[BaseCloud]):
    """Shallow test of all public functions in the base API.

    get_instance() isn't tested as it is implementation dependent
    """
    cloud = CloudType(tag="pycloudlib-integration")

    latest_lts = LTS_RELEASES[-1]
    try:
        image_id = cloud.released_image(release=latest_lts)
    except NotImplementedError:
        image_id = cloud.daily_image(release=latest_lts)
    with suppress(NotImplementedError):
        # Not sure there's a great way to test this other than not raising
        cloud.image_serial(image_id)

    with launch_instance(
        cloud, image_id=image_id, user_data=cloud_config, wait=False
    ) as instance:
        instance.wait()
        exercise_instance(instance)

        instance.clean()
        snapshot_id = cloud.snapshot(instance)

    try:
        with launch_instance(
            cloud, image_id=snapshot_id, user_data=cloud_config, wait=False
        ) as instance_from_snapshot:
            instance_from_snapshot.wait()
            exercise_instance(instance_from_snapshot)
    finally:
        cloud.delete_image(snapshot_id)
