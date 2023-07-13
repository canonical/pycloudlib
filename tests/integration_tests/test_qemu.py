from pycloudlib import Qemu

SNAPSHOT_CONFIG = """\
#cloud-config
bootcmd:
 - echo '%s' >> /var/tmp/message
"""


def test_snapshots():
    """Test that snapshots work as expected."""
    # Since we're managing everything with directories, and qcow images
    # are copy-on-wrtie, ensure multiple snapshots don't step on each other
    with Qemu(tag="test", timestamp_suffix=True) as cloud:
        image = cloud.released_image("jammy")
        instance = cloud.launch(
            image_id=image,
            user_data=SNAPSHOT_CONFIG % "1",
        )
        instance.wait()
        snapshot1 = cloud.snapshot(instance)
        snapshot2 = cloud.snapshot(instance)
        instance2 = cloud.launch(
            image_id=snapshot1,
            user_data=SNAPSHOT_CONFIG % "2",
        )
        instance3 = cloud.launch(
            image_id=snapshot2,
            user_data=SNAPSHOT_CONFIG % "3",
        )
        instance.start()
        instance2.wait()
        instance3.wait()
        assert "1\n1" == instance.execute("cat /var/tmp/message")
        assert "1\n2" == instance2.execute("cat /var/tmp/message")
        assert "1\n3" == instance3.execute("cat /var/tmp/message")

        # Since snapshots are a slightly different code path from an
        # initial launch, also verify snapshots of snapshots
        snapshot3 = cloud.snapshot(instance3)
        instance4 = cloud.launch(
            image_id=snapshot3,
            user_data=SNAPSHOT_CONFIG % "4",
        )

        instance.restart(wait=False)
        instance2.restart(wait=False)
        instance3.start(wait=True)

        instance.wait()
        instance2.wait()
        instance3.wait()
        instance4.wait()

        assert "1\n1\n1" == instance.execute("cat /var/tmp/message")
        assert "1\n2\n2" == instance2.execute("cat /var/tmp/message")
        assert "1\n3\n3" == instance3.execute("cat /var/tmp/message")
        assert "1\n3\n4" == instance4.execute("cat /var/tmp/message")

        # Ensure that deletions have no effect on other instances
        instance2.delete()
        assert not instance2.instance_dir.exists()
        assert "1\n1\n1" == instance.execute("cat /var/tmp/message")
        assert "1\n3\n3" == instance3.execute("cat /var/tmp/message")
        assert "1\n3\n4" == instance4.execute("cat /var/tmp/message")

        instance.delete()
        assert not instance.instance_dir.exists()
        assert "1\n3\n3" == instance3.execute("cat /var/tmp/message")
        assert "1\n3\n4" == instance4.execute("cat /var/tmp/message")

    # Ensure we've cleaned up everything
    assert not cloud.parent_dir.exists()


def test_kernel_cli():
    """Test that kernel command line arguments are passed through."""
    with Qemu(tag="test", timestamp_suffix=True) as cloud:
        image = cloud.released_image("jammy")
        instance = cloud.launch(
            image_id=image,
            kernel_cmdline="ds=nocloud;h=testhostname;i=myinstanceid",
        )
        instance.wait()
        assert "testhostname" == instance.execute("hostname")
        assert "myinstanceid" == instance.execute(
            "cloud-init query instance-id"
        )


def test_console_log():
    with Qemu(tag="test", timestamp_suffix=True) as cloud:
        image = cloud.released_image("jammy")
        instance = cloud.launch(image_id=image)
        instance.wait()
        console_log = instance.console_log()
        assert "Booting from Hard Disk..." in console_log
        assert "ubuntu login: " in console_log
