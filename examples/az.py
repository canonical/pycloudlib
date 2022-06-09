#!/usr/bin/env python3
# This file is part of pycloudlib. See LICENSE file for license information.
"""Basic examples of various lifecycle with an Azure instance."""

import logging

import pycloudlib
from pycloudlib.cloud import ImageType

cloud_config = """#cloud-config
runcmd:
  - echo 'hello' > /home/ubuntu/example.txt
"""


def save_keys(key_name: str, pub_key: str, priv_key: str):
    """Save keys generated through Azure."""
    pub_path = "pub_{}.pem".format(key_name)
    priv_path = "priv_{}.pem".format(key_name)

    with open(pub_path, "w", encoding="utf-8") as f:
        f.write(pub_key)

    with open(priv_path, "w", encoding="utf-8") as f:
        f.write(priv_key)

    return pub_path, priv_path


def demo():
    """Show example of using the Azure library.

    Connects to Azure and launches released image. Then runs
    through a number of examples.

    PS: we assume in this example that you are logged into
    you Azure account
    """
    client = pycloudlib.Azure(tag="azure")
    image_id = client.daily_image(release="focal")

    pub_key, priv_key = client.create_key_pair(key_name="test_integration")
    pub_path, priv_path = save_keys(
        key_name="test",
        pub_key=pub_key,
        priv_key=priv_key,
    )
    client.use_key(pub_path, priv_path)

    instance = client.launch(
        image_id=image_id,
        instance_type="Standard_DS2_v2",  # default is Standard_DS1_v2
        user_data=cloud_config,
    )

    print(instance.ip)
    instance.wait()
    print(instance.execute("cat /home/ubuntu/example.txt"))

    snapshotted_image_id = client.snapshot(instance)
    instance.delete()

    new_instance = client.launch(image_id=snapshotted_image_id)
    new_instance.delete()


def demo_pro():
    """Show example of launchig a Ubuntu PRO image through Azure."""
    client = pycloudlib.Azure(tag="azure")
    image_id = client.daily_image(release="focal", image_type=ImageType.PRO)

    pub_key, priv_key = client.create_key_pair(key_name="test_pro")
    pub_path, priv_path = save_keys(
        key_name="test_pro",
        pub_key=pub_key,
        priv_key=priv_key,
    )
    client.use_key(pub_path, priv_path)

    print("Launching Focal PRO instance.")
    instance = client.launch(
        image_id=image_id,
        instance_type="Standard_DS2_v2",  # default is Standard_DS1_v2
    )

    print(instance.ip)
    instance.wait()
    print(instance.execute("sudo ua status --wait"))
    instance.delete()


def demo_pro_fips():
    """Show example of launchig a Ubuntu PRO FIPS image through Azure."""
    client = pycloudlib.Azure(tag="azure")
    image_id = client.daily_image(
        release="focal", image_type=ImageType.FIPS_PRO
    )

    pub_key, priv_key = client.create_key_pair(key_name="test_pro_fips")
    pub_path, priv_path = save_keys(
        key_name="test_pro_fips",
        pub_key=pub_key,
        priv_key=priv_key,
    )
    client.use_key(pub_path, priv_path)

    print("Launching Focal PRO instance.")
    instance = client.launch(
        image_id=image_id,
        instance_type="Standard_DS2_v2",  # default is Standard_DS1_v2
    )

    print(instance.ip)
    instance.wait()
    print(instance.execute("sudo ua status --wait"))
    instance.delete()


if __name__ == "__main__":
    # Avoid polluting the log with azure info
    logging.getLogger("adal-python").setLevel(logging.WARNING)
    logging.getLogger("cli.azure.cli.core").setLevel(logging.WARNING)
    logging.basicConfig(level=logging.DEBUG)

    demo()
    demo_pro()
    demo_pro_fips()
