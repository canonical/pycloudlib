#!/usr/bin/env python3
# This file is part of pycloudlib. See LICENSE file for license information.
"""Basic examples of various lifecycle with an IBM instance."""

import logging
import os

import pycloudlib


def snapshot(ibm, daily):
    """Create a snapshot from a customized image and launch it."""
    with ibm.launch(daily) as instance:
        instance.wait()
        instance.execute("touch custom_config_file")

        image = ibm.snapshot(instance)
        with ibm.launch(image, name="example-snapshot") as new_instance:
            new_instance.execute("ls")

    ibm.delete_image(image)


def custom_vpc(ibm, daily):
    """Launch instances using a custom VPC."""
    vpc = ibm.get_or_create_vpc(name="test-vpc")
    with ibm.launch(daily, vpc=vpc) as instance:
        instance.wait()
        instance.execute("whoami")

    # vpc.delete will also delete any associated instances in that VPC
    vpc.delete()


def launch_basic(ibm, daily, instance_type):
    """Show basic functionality on instances.

    Simple launching of an instance, run a command, and delete.
    """
    with ibm.launch(daily, instance_type=instance_type) as instance:
        instance.wait()
        print(instance.execute("lsb_release -a"))

        instance.shutdown()
        instance.start()
        instance.restart()

        # Various Attributes
        print(instance.ip)
        print(instance.id)


def manage_ssh_key(ibm, key_name):
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


def demo():
    """Show example of using the IBM library.

    Connects to IBM and finds the latest daily image. Then runs
    through a number of examples.
    """
    with pycloudlib.IBM(tag="examples") as ibm:
        manage_ssh_key(ibm, "test-ibm")

        daily = ibm.daily_image(release="bionic")

        # "bx2-metal-96x384" for a bare-metal instance
        launch_basic(ibm, daily, "bx2-2x8")
        custom_vpc(ibm, daily)
        snapshot(ibm, daily)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    demo()
