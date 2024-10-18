#!/usr/bin/env python3
# This file is part of pycloudlib. See LICENSE file for license information.
"""Basic examples of various lifecycle with an GCE instance."""

import argparse
import datetime
import logging
import os

import pycloudlib
from pycloudlib import GCE
from pycloudlib.cloud import ImageInfo, ImageType


def manage_ssh_key(gce: GCE):
    """Manage ssh keys for gce instances."""
    pub_key_path = "gce-pubkey"
    priv_key_path = "gce-privkey"
    pub_key, priv_key = gce.create_key_pair()

    with open(pub_key_path, "w", encoding="utf-8") as f:
        f.write(pub_key)

    with open(priv_key_path, "w", encoding="utf-8") as f:
        f.write(priv_key)

    os.chmod(pub_key_path, 0o600)
    os.chmod(priv_key_path, 0o600)

    gce.use_key(public_key_path=pub_key_path, private_key_path=priv_key_path)


def generic(gce: GCE):
    """Show example of using the GCE library.

    Connects to GCE and finds the latest daily image. Then runs
    through a number of examples.
    """
    daily = gce.daily_image("bionic", arch="x86_64")
    with gce.launch(daily) as inst:
        inst.wait()
        print(inst.execute("lsb_release -a"))


def pro(gce: GCE):
    """Show example of running a GCE PRO machine."""
    daily = gce.daily_image("bionic", image_type=ImageType.PRO)
    with gce.launch(daily) as inst:
        inst.wait()
        print(inst.execute("sudo ua status --wait"))


def pro_fips(gce: GCE):
    """Show example of running a GCE PRO FIPS machine."""
    daily = gce.daily_image("bionic", image_type=ImageType.PRO_FIPS)
    with gce.launch(daily) as inst:
        inst.wait()
        print(inst.execute("sudo ua status --wait"))


def custom_image(gce: GCE, image_name):
    """Show example of running a GCE custom image."""
    image_id = gce.get_image_id_from_name(image_name)
    print(image_id)
    with gce.launch(image_id=image_id) as instance:
        instance.wait()
        print(instance.execute("hostname"))
        input("Press Enter to teardown instance")


def upload_custom_image(gce: GCE, image_name, local_file_path, bucket_name):
    """Show example of uploading a custom image to GCE."""
    new_image: ImageInfo = gce.create_image_from_local_file(
        local_file_path=local_file_path,
        image_name=image_name,
        intermediary_storage_name=bucket_name,
    )
    print("created new image:", new_image)
    return new_image


def demo_image_creation(
    local_file_path: str,
    bucket_name: str,
    image_name_template: str = "gce-example-image-{}",
):
    """Show example of creating a custom image on GCE from a local image file."""
    # get short date and time for unique tag
    time_tag = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    tag = f"gce-example-{time_tag}"

    with pycloudlib.GCE(tag=tag) as gce:
        manage_ssh_key(gce)

        new_image: ImageInfo = upload_custom_image(
            gce,
            image_name=image_name_template.format(time_tag),
            local_file_path=local_file_path,
            bucket_name=bucket_name,
        )

        with gce.launch(new_image.id) as instance:
            instance.wait()
            print(instance.execute("hostname"))
            print(instance.execute("lsb_release -a"))
            input("Press Enter to teardown instance")


def demo_instances():
    """Show examples of launching GCP instances."""
    with pycloudlib.GCE(tag="examples") as gce:
        manage_ssh_key(gce)
        generic(gce)
        pro(gce)
        pro_fips(gce)


def main():
    """Take in cli args and run GCE demo scripts."""
    parser = argparse.ArgumentParser(description="GCE Demo Script")
    parser.add_argument(
        "demo_type",
        choices=["instance", "image"],
        help="Type of demo to run: 'instance' for basic instance launch demo, or "
        "'image' for image creation demo",
        nargs="?",
        default="instance",
    )
    parser.add_argument(
        "--local_file_path", type=str, help="Local file path for the image creation demo"
    )
    parser.add_argument("--bucket_name", type=str, help="Bucket name for the image creation demo")
    args = parser.parse_args()

    logging.basicConfig(level=logging.DEBUG)

    if args.demo_type == "instance":
        demo_instances()
    elif args.demo_type == "image":
        if not args.local_file_path or not args.bucket_name:
            parser.error("Image creation demo requires --local_file_path and --bucket_name")
        demo_image_creation(
            local_file_path=args.local_file_path,
            bucket_name=args.bucket_name,
        )


if __name__ == "__main__":
    main()
