#!/usr/bin/env python3
# This file is part of pycloudlib. See LICENSE file for license information.
"""Basic examples of various lifecycle with an IBM instance."""

import logging
import os

import pycloudlib
from pycloudlib.cloud import ImageType


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


def custom_vpc(ec2, daily):
    """Launch instances using a custom VPC."""
    vpc = ec2.get_or_create_vpc(name="test-vpc")
    ec2.launch(daily, vpc=vpc)

    # vpc.delete will also delete any associated instances in that VPC
    vpc.delete()


def launch_basic(ec2, daily):
    """Show basic functionality on instances.

    Simple launching of an instance, run a command, and delete.
    """
    instance = ec2.launch(daily)
    instance.console_log()
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


def handle_ssh_key(ec2, key_name):
    """Manage ssh keys to be used in the instances."""
    if key_name in ec2.list_keys():
        ec2.delete_key(key_name)

    key_pair = ec2.client.create_key_pair(KeyName=key_name)
    private_key_path = "ec2-test.pem"
    with open(private_key_path, "w", encoding="utf-8") as stream:
        stream.write(key_pair["KeyMaterial"])
    os.chmod(private_key_path, 0o600)

    # Since we are using a pem file, we don't have distinct public and
    # private key paths
    ec2.use_key(
        public_key_path=private_key_path,
        private_key_path=private_key_path,
        name=key_name,
    )


def demo():
    """Show example of using the IBM library.

    Connects to IBM and finds the latest daily image. Then runs
    through a number of examples.
    """
    ibm = pycloudlib.IBM_VPC(tag="examples")
    key_name = "test-ibm"
    # handle_ssh_key(ibm, key_name)

    daily = ibm.daily_image(release="bionic")

    launch_basic(ibm, daily)
    custom_vpc(ibm, daily)
    snapshot(ibm, daily)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    demo()
