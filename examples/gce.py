#!/usr/bin/env python3
# This file is part of pycloudlib. See LICENSE file for license information.
"""Basic examples of various lifecycle with an GCE instance."""

import logging
import os

import pycloudlib


def demo():
    """Show example of using the GCE library.

    Connects to GCE and finds the latest daily image. Then runs
    through a number of examples.
    """
    gce = pycloudlib.GCE(
        tag="examples",
        credentials_path="MY-GCE-CREDENTIALS-PATH",
        project="PROJECT-ID",
        region="us-west2",
        zone="a",
    )
    daily = gce.daily_image("bionic")

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

    inst = gce.launch(daily)
    print(inst.execute("lsb_release -a"))


if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    demo()
