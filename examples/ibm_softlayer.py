#!/usr/bin/env python3
# This file is part of pycloudlib. See LICENSE file for license information.
"""Basic example for launching IBM Softlayer/Classic instance."""

import logging
import os

import pycloudlib
import pycloudlib.ibm_softlayer


def manage_ssh_key(softlayer: pycloudlib.IBMSoftlayer):
    """Manage ssh keys for ibm instances."""
    # creates a key pair and uses it for the instance
    # the key pair is stored in the current directory
    # the key pair is named after the VM
    # the key pair is removed after the instance is cleaned up
    tag = softlayer.tag
    key_name = f"{tag}-ssh-key"
    pub_key_path = f"{tag}-pubkey"
    priv_key_path = f"{tag}-privkey"

    pub_key, priv_key = softlayer.create_key_pair()

    with open(pub_key_path, "w", encoding="utf-8") as f:
        f.write(pub_key)

    with open(priv_key_path, "w", encoding="utf-8") as f:
        f.write(priv_key)

    os.chmod(pub_key_path, 0o600)
    os.chmod(priv_key_path, 0o600)

    softlayer.use_key(
        public_key_path=pub_key_path,
        private_key_path=priv_key_path,
        name=key_name,
    )


def launch_basic(
    softlayer: pycloudlib.IBMSoftlayer, disk_size="25G", datacenter: str = None
):
    """Launch a basic instance and demo basic functionality."""
    image_gid = softlayer.released_image("22.04", disk_size=disk_size)

    with softlayer.launch(
        image_gid,
        instance_type="B1_2x4",
        disk_size=disk_size,
        datacenter_region="dal",
        datacenter=datacenter,  # if provided, will override datacenter_region
    ) as instance:
        try:
            print("Waiting for instance to be ready!")
            instance.wait()
            print(instance.execute("lsb_release -a"))
            print("Shutting down instance!")
            instance.shutdown()
            print("Starting instance!")
            instance.start()
            print("Restarting instance!")
            instance.restart()
            # Various Attributes
            print(f"Instance IP Address: {instance.ip}")
            print(f"Instance ID: {instance.id}")
            # Create a file that will exist after snapshot
            instance.execute("echo 'Hello World!' > /tmp/hello.txt")
            # Create a snapshot
            snapshot_id = softlayer.snapshot(
                instance,
                note="Example snapshot created by pycloudlib",
            )
            print(
                f"Succesfully created snapshot {softlayer.tag}-snapshot with ID: {snapshot_id}"
            )
            print("Example Completed!")

        except Exception as e:
            logging.error("Something went wrong: %s", e)
            raise e


def demo():
    """Demo the basic functionality of pycloudlib with IBM Softlayer."""
    with pycloudlib.IBMSoftlayer(tag="pycloudlib-example") as softlayer:
        manage_ssh_key(softlayer)
        launch_basic(softlayer)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    demo()
