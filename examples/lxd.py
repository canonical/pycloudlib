#!/usr/bin/env python3
# This file is part of pycloudlib. See LICENSE file for license information.
"""Basic examples of various lifecycle with a LXD instance."""

import logging
import textwrap

import pycloudlib
from pycloudlib.types import ImageType

RELEASE = "noble"


def snapshot_instance():
    """Demonstrate snapshot functionality.

    This shows the lifecycle of booting an instance and cleaning it
    before creating a snapshot.

    Next, both create the snapshot and immediately restore the original
    instance to the snapshot level.
    Finally, launch another instance from the snapshot of the instance.
    """
    with pycloudlib.LXDContainer("example-snapshot") as lxd:
        with lxd.launch(name="pycloudlib-snapshot-base", image_id=RELEASE) as inst:
            inst.wait()
            snapshot_name = "snapshot"
            inst.local_snapshot(snapshot_name)
            inst.restore(snapshot_name)

            child = lxd.clone(
                "%s/%s" % (inst.name, snapshot_name),
                "pycloudlib-snapshot-child",
            )

            child.delete()
            inst.delete_snapshot(snapshot_name)
            inst.delete(wait=False)


def image_snapshot_instance(ephemeral_instance=False):
    """Demonstrate image snapshot functionality.

    Create an snapshot image from a running instance an show
    how to launch a new instance based of this image snapshot
    """
    with pycloudlib.LXDContainer("example-image-snapshot") as lxd:
        with lxd.launch(
            name="pycloudlib-snapshot-base",
            image_id=RELEASE,
            ephemeral=ephemeral_instance,
        ) as inst:
            inst.wait()
            inst.execute("touch snapshot-test.txt")
            print("Base instance output: {}".format(inst.execute("ls")))
            snapshot_image = lxd.snapshot(instance=inst)

            with lxd.launch(
                name="pycloudlib-snapshot-image",
                image_id=snapshot_image,
                ephemeral=ephemeral_instance,
            ) as snapshot_inst:
                print("Snapshot instance output: {}".format(snapshot_inst.execute("ls")))


def modify_instance():
    """Demonstrate how to modify and interact with an instance.

    The inits an instance and before starting it, edits the the
    container configuration.

    Once started the instance demonstrates some interactions with the
    instance.
    """
    with pycloudlib.LXDContainer("example-modify") as lxd:
        with lxd.init("pycloudlib-modify-inst", RELEASE) as inst:
            inst.edit("limits.memory", "3GB")
            inst.start()

            inst.execute("uptime > /tmp/uptime")
            inst.pull_file("/tmp/uptime", "/tmp/pulled_file")
            inst.push_file("/tmp/pulled_file", "/tmp/uptime_2")
            inst.execute("cat /tmp/uptime_2")


def launch_multiple():
    """Launch multiple instances.

    How to quickly launch multiple instances with LXD. This prevents
    waiting for the instance to start each time. Note that the
    wait_for_delete method is not used, as LXD does not do any waiting.
    """
    lxd = pycloudlib.LXDContainer("example-multiple")

    instances = []
    for num in range(2):
        inst = lxd.launch(name="pycloudlib-%s" % num, image_id=RELEASE)
        instances.append(inst)

    for instance in instances:
        instance.wait()

    # Launch daily minimal images
    image_id = lxd.daily_image(release=RELEASE, image_type=ImageType.MINIMAL)
    inst = lxd.launch(name="pycloudlib-minimal", image_id=image_id)
    instances.append(inst)

    for instance in instances:
        instance.delete()


def launch_options():
    """Demonstrate various launching scenarios.

    First up is launching with a different profile, in this case with
    two profiles.

    Next, is launching an ephemeral instance with a different image
    remote server.

    Then, an instance with custom network, storage, and type settings.
    This is an example of booting an instance without cloud-init so
    wait is set to False.

    Finally, an instance with custom configurations options.
    """
    lxd = pycloudlib.LXDContainer("example-launch")
    kvm_profile = textwrap.dedent(
        """\
        devices:
          kvm:
            path: /dev/kvm
            type: unix-char
        """
    )

    lxd.create_profile(profile_name="kvm", profile_config=kvm_profile)

    lxd.launch(
        name="pycloudlib-kvm",
        image_id=RELEASE,
        profile_list=["default", "kvm"],
    )
    lxd.delete_instance("pycloudlib-kvm")

    lxd.launch(
        name="pycloudlib-ephemeral",
        image_id="ubuntu:%s" % RELEASE,
        ephemeral=True,
    )
    lxd.delete_instance("pycloudlib-ephemeral")

    lxd.launch(
        name="pycloudlib-custom-hw",
        image_id="images:ubuntu/xenial",
        network="lxdbr0",
        storage="default",
        inst_type="t2.micro",
        wait=False,
    )
    lxd.delete_instance("pycloudlib-custom-hw")

    lxd.launch(
        name="pycloudlib-privileged",
        image_id=RELEASE,
        config_dict={
            "security.nesting": "true",
            "security.privileged": "true",
        },
    )
    lxd.delete_instance("pycloudlib-privileged")


def basic_lifecycle():
    """Demonstrate basic set of lifecycle operations with LXD."""
    with pycloudlib.LXDContainer("example-basic") as lxd:
        with lxd.launch(image_id=RELEASE) as inst:
            inst.wait()

        name = "pycloudlib-daily"
        with lxd.launch(name=name, image_id=RELEASE) as inst:
            inst.wait()
            inst.console_log()

            result = inst.execute("uptime")
            print(result)
            print(result.return_code)
            print(result.ok)
            print(result.failed)
            print(bool(result))

            inst.shutdown()
            inst.start()
            inst.restart()

            # Custom attributes
            print(inst.ephemeral)
            print(inst.state)

            inst = lxd.get_instance(name)
            inst.delete()


def launch_virtual_machine():
    """Demonstrate launching virtual machine scenario."""
    with pycloudlib.LXDVirtualMachine("example-vm") as lxd:
        pub_key_path = "lxd-pubkey"
        priv_key_path = "lxd-privkey"
        pub_key, priv_key = lxd.create_key_pair()

        with open(pub_key_path, "w", encoding="utf-8") as f:
            f.write(pub_key)

        with open(priv_key_path, "w", encoding="utf-8") as f:
            f.write(priv_key)

        lxd.use_key(public_key_path=pub_key_path, private_key_path=priv_key_path)

        image_id = lxd.released_image(release=RELEASE)
        image_serial = lxd.image_serial(image_id)
        print("Image serial: {}".format(image_serial))
        name = "pycloudlib-vm"
        with lxd.launch(name=name, image_id=image_id) as inst:
            inst.wait()
            print("Is vm: {}".format(inst.is_vm))
            result = inst.execute("lsb_release -a")
            print(result)
            print(result.return_code)
            print(result.ok)
            print(result.failed)
            print(bool(result))

            inst_2 = lxd.get_instance(name)
            print(inst_2.execute("lsb_release -a"))

            inst.shutdown()
            inst.start()
            inst.restart()


def demo():
    """Show examples of using the LXD library."""
    basic_lifecycle()
    launch_options()
    launch_multiple()
    modify_instance()
    snapshot_instance()
    image_snapshot_instance(ephemeral_instance=False)
    launch_virtual_machine()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    demo()
