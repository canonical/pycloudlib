#!/usr/bin/env python3
# This file is part of pycloudlib. See LICENSE file for license information.
"""Basic examples of various lifecycle with an IBM instance."""

import logging
import os

import pycloudlib


def snapshot(ec2, daily):
    """Create a snapshot from a customized image and launch it."""
    instance = ec2.launch(daily)
    instance.execute("touch custom_config_file")

    image = ec2.snapshot(instance)
    new_instance = ec2.launch(image)
    new_instance.execute("ls")

    new_instance.delete()
    ec2.delete_image(image)
    instance.delete()


def custom_vpc(ibm, daily):
    """Launch instances using a custom VPC."""
    vpc = ibm.get_or_create_vpc(name="test-vpc")
    ibm.launch(daily, vpc=vpc)

    # vpc.delete will also delete any associated instances in that VPC
    vpc.delete()


def launch_basic(ibm, daily):
    """Show basic functionality on instances.

    Simple launching of an instance, run a command, and delete.
    """
    instance = ibm.launch(daily)
    print(instance.execute("lsb_release -a"))

    instance.shutdown()
    instance.start()
    instance.restart()

    # Various Attributes
    print(instance.ip)
    print(instance.id)
    print(instance.image_id)
    print(instance.availability_zone)

    instance.delete()


def manage_ssh_key(ibm, key_name):
    """Manage ssh keys for ibm instances."""
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
    ibm = pycloudlib.IBM(tag="examples")
    manage_ssh_key(ibm, "test-ibm")

    daily = ibm.daily_image(release="bionic")

    launch_basic(ibm, daily)
    # custom_vpc(ibm, daily)
    # snapshot(ibm, daily)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    demo()
