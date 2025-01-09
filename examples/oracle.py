#!/usr/bin/env python3
# This file is part of pycloudlib. See LICENSE file for license information.
"""Basic examples of various lifecycle with an OCI instance."""

import argparse
import logging
from base64 import b64encode

import pycloudlib

cloud_config = """#cloud-config
runcmd:
  - echo 'hello' > /home/ubuntu/example.txt
"""


def demo(
    availability_domain: str = None,
    compartment_id: str = None,
    vcn_name: str = None,
):
    """Show example of using the OCI library.

    Connects to OCI and launches released image. Then runs
    through a number of examples.
    """
    with pycloudlib.OCI(
        "oracle-test",
        availability_domain=availability_domain,
        compartment_id=compartment_id,
        vcn_name=vcn_name,
    ) as client:
        with client.launch(
            image_id=client.released_image("jammy"),
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

def upload_and_create_image(
    local_file_path: str,
    image_name: str,
    suite: str,
    intermediary_storage_name: str,
    availability_domain: str = None,
    compartment_id: str = None,
):
    """Upload a local .img file and create an image from it on OCI."""
    with pycloudlib.OCI(
        "oracle-test",
        availability_domain=availability_domain,
        compartment_id=compartment_id,
    ) as client:
        image_info = client.create_image_from_local_file(
            local_file_path=local_file_path,
            image_name=image_name,
            intermediary_storage_name=intermediary_storage_name,
            suite=suite,
        )
        print(f"Created image: {image_info}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="OCI example script")
    subparsers = parser.add_subparsers(dest="command")

    demo_parser = subparsers.add_parser("demo", help="Run the demo")
    demo_parser.add_argument("--availability-domain", type=str, help="Availability domain", required=False)
    demo_parser.add_argument("--compartment-id", type=str, help="Compartment ID", required=False)
    demo_parser.add_argument("--vcn-name", type=str, help="VCN name", required=False)

    create_image_parser = subparsers.add_parser("create_image", help="Create an image from a local file")
    create_image_parser.add_argument("--local-file-path", type=str, required=True, help="Local file path")
    create_image_parser.add_argument("--image-name", type=str, required=True, help="Image name")
    create_image_parser.add_argument("--intermediary-storage-name", type=str, required=True, help="Intermediary storage name")
    create_image_parser.add_argument("--suite", type=str, help="Suite of the image. I.e. 'jammy'", required=True)
    create_image_parser.add_argument("--availability-domain", type=str, help="Availability domain")
    create_image_parser.add_argument("--compartment-id", type=str, help="Compartment ID")

    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)

    if args.command == "demo":
        demo(
            availability_domain=args.availability_domain,
            compartment_id=args.compartment_id,
            vcn_name=args.vcn_name,
        )
    elif args.command == "create_image":
        upload_and_create_image(
            local_file_path=args.local_file_path,
            image_name=args.image_name,
            suite=args.suite,
            intermediary_storage_name=args.intermediary_storage_name,
            availability_domain=args.availability_domain,
            compartment_id=args.compartment_id,
        )
    else:
        parser.print_help()
