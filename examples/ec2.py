#!/usr/bin/env python3
# This file is part of pycloudlib. See LICENSE file for license information.
"""Basic examples of various lifecycle with an EC2 instance."""

import logging
import os

import pycloudlib
from pycloudlib.types import ImageType


def hot_add(ec2, daily):
    """Hot add to an instance.

    Give an example of hot adding a pair of network interfaces and a
    couple storage volumes of various sizes.
    """
    with ec2.launch(daily, instance_type="m4.xlarge") as instance:
        instance.wait()
        # Add NIC with 2 private ips
        instance.add_network_interface(ipv4_address_count=2)
        instance.add_network_interface()

        instance.add_volume(size=9)
        instance.add_volume(size=10, drive_type="gp2")


def launch_multiple(ec2, daily):
    """Launch multiple instances.

    How to quickly launch multiple instances with EC2. This prevents
    waiting for the instance to start each time.
    """
    instances = []
    for _ in range(3):
        instances.append(ec2.launch(daily))

    for instance in instances:
        instance.wait()

    for instance in instances:
        instance.delete(wait=False)

    for instance in instances:
        instance.wait_for_delete()


def snapshot(ec2, daily):
    """Create a snapshot from a customized image and launch it."""
    with ec2.launch(daily) as instance:
        instance.wait()
        instance.execute("touch custom_config_file")

        image = ec2.snapshot(instance)
        new_instance = ec2.launch(image)
        new_instance.wait()
        new_instance.execute("ls")

        new_instance.delete()
        ec2.delete_image(image)


def custom_vpc(ec2, daily):
    """Launch instances using a custom VPC."""
    vpc = ec2.get_or_create_vpc(name="test-vpc")
    with ec2.launch(daily, vpc=vpc) as instance:
        instance.wait()
        instance.execute("whoami")

    # vpc.delete will also delete any associated instances in that VPC
    vpc.delete()


def launch_basic(ec2, daily):
    """Show basic functionality on instances.

    Simple launching of an instance, run a command, and delete.
    """
    with ec2.launch(daily) as instance:
        instance.wait()
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


def launch_pro(ec2, daily):
    """Show basic functionality on PRO instances."""
    print("Launching Pro instance...")
    with ec2.launch(daily) as instance:
        instance.wait()
        print(instance.execute("sudo ua status --wait"))
        print("Deleting Pro instance...")


def launch_pro_fips(ec2, daily):
    """Show basic functionality on PRO instances."""
    print("Launching Pro FIPS instance...")
    with ec2.launch(daily) as instance:
        instance.wait()
        print(instance.execute("sudo ua status --wait"))
        print("Deleting Pro FIPS instance...")


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
    """Show example of using the EC2 library.

    Connects to EC2 and finds the latest daily image. Then runs
    through a number of examples.
    """
    with pycloudlib.EC2(tag="examples") as ec2:
        key_name = "test-ec2"
        handle_ssh_key(ec2, key_name)

        daily = ec2.daily_image(release="bionic")
        daily_pro = ec2.daily_image(release="bionic", image_type=ImageType.PRO)
        daily_pro_fips = ec2.daily_image(release="bionic", image_type=ImageType.PRO_FIPS)

        launch_basic(ec2, daily)
        launch_pro(ec2, daily_pro)
        launch_pro_fips(ec2, daily_pro_fips)
        custom_vpc(ec2, daily)
        snapshot(ec2, daily)
        launch_multiple(ec2, daily)
        hot_add(ec2, daily)


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    demo()
