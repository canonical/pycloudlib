#!/usr/bin/env python3
# This file is part of pycloudlib. See LICENSE file for license information.
"""Basic examples of various lifecycle with an OCI instance."""

import logging
import sys
from base64 import b64encode

import pycloudlib


cloud_config = """#cloud-config
runcmd:
  - echo 'hello' > /home/ubuntu/example.txt
"""


def demo(availability_domain, compartment_id):
    """Show example of using the OCI library.

    Connects to OCI and launches released image. Then runs
    through a number of examples.
    """
    client = pycloudlib.OCI(
        "Oracle test",
        availability_domain=availability_domain,
        compartment_id=compartment_id,
    )

    instance = client.launch(
        image_id=client.released_image("focal"),
        user_data=b64encode(cloud_config.encode()).decode(),
    )

    print(instance.instance_data)
    print(instance.ip)
    instance.execute("cloud-init status --wait --long")
    print(instance.execute("cat /home/ubuntu/example.txt"))

    snapshotted_image_id = client.snapshot(instance)

    instance.delete()

    new_instance = client.launch(image_id=snapshotted_image_id)
    new_instance.delete()


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    if len(sys.argv) != 3:
        print("Usage: oci.py <availability_domain> <compartment_id>")
        sys.exit(1)
    passed_availability_domain = sys.argv[1]
    passed_compartment_id = sys.argv[2]
    demo(passed_availability_domain, passed_compartment_id)
