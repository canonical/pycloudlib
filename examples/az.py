#!/usr/bin/env python3
# This file is part of pycloudlib. See LICENSE file for license information.
"""Basic examples of various lifecycle with an Azure instance."""

import logging

import pycloudlib


cloud_config = """#cloud-config
runcmd:
  - echo 'hello' > /home/ubuntu/example.txt
"""


def demo():
    """Show example of using the Azure library.

    Connects to Azure and launches released image. Then runs
    through a number of examples.

    PS: we assume in this example that you are logged into
    you Azure account
    """
    client = pycloudlib.Azure(tag='azure')

    image_id = client.daily_image(release="focal")
    pub_key, priv_key = client.create_key_pair(
        key_name="test_integration")

    pub_path = "pub_test.pem"
    priv_path = "priv_test.pem"

    with open(pub_path, "w") as f:
        f.write(pub_key)

    with open(priv_path, "w") as f:
        f.write(priv_key)
    client.use_key(pub_path, priv_path)

    instance = client.launch(
        image_id=image_id,
        user_data=cloud_config
    )

    print(instance.ip)
    instance.wait()
    print(instance.execute('cat /home/ubuntu/example.txt'))

    snapshotted_image_id = client.snapshot(instance)
    instance.delete()

    new_instance = client.launch(image_id=snapshotted_image_id)
    new_instance.delete()


if __name__ == '__main__':
    # Avoid polluting the log with azure info
    logging.getLogger("adal-python").setLevel(logging.WARNING)
    logging.basicConfig(level=logging.DEBUG)
    demo()
