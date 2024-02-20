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


def demo(availability_domain: str, compartment_id: str):
    """Show example of using the OCI library.

    Connects to OCI and launches released image. Then runs
    through a number of examples.
    """
    with pycloudlib.OCI(
        "oracle-test",
        availability_domain=availability_domain,
        compartment_id=compartment_id,
    ) as client:
        with client.launch(
            image_id=client.released_image("focal"),
            user_data=b64encode(cloud_config.encode()).decode(),
        ) as instance:
            instance.wait()
            print(instance.instance_data)
            print(instance.ip)
            instance.execute("cloud-init status --wait --long")
            print(instance.execute("cat /home/ubuntu/example.txt"))

            snapshotted_image_id = client.snapshot(instance)

        with client.launch(image_id=snapshotted_image_id) as new_instance:
            new_instance.wait()
            new_instance.execute("whoami")


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    
    # fill in the  variables here if you'd rather not
    # pass availability domain and compartment id as arguments via cli
    AVAILABILITY_DOMAIN = ""
    COMPARTMENT_ID = ""

    if len(sys.argv) != 3 and not (AVAILABILITY_DOMAIN and COMPARTMENT_ID):
        # get the availability domain and compartment id from the user via input
        print("No arguments passed. Please enter the availability domain and compartment id.")
        ad = input("Enter the availability domain: ").strip()
        cid = input("Enter the compartment id: ").strip()
        demo(ad, cid)
    
    elif len(sys.argv) == 3 and AVAILABILITY_DOMAIN and COMPARTMENT_ID:
        print(
            "You've passed in availability domain and "
            "compartment id as arguments and set them as variables. "
            "Please choose one method."
        )
        sys.exit(1)
    
    elif len(sys.argv) == 3:
        demo(sys.argv[1], sys.argv[2])
    
    elif AVAILABILITY_DOMAIN and COMPARTMENT_ID:
        demo(AVAILABILITY_DOMAIN, COMPARTMENT_ID)

    else:
        print("Nothing to do. Exiting.")
        sys.exit(1)
