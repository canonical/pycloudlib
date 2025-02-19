#!/usr/bin/env python3
# This file is part of pycloudlib. See LICENSE file for license information.
"""Basic examples of various lifecycle with an GCE instance."""

import logging
import os

import pycloudlib
from pycloudlib.types import ImageType


def manage_ssh_key(gce):
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


def generic(gce):
    """Show example of using the GCE library.

    Connects to GCE and finds the latest daily image. Then runs
    through a number of examples.
    """
    daily = gce.daily_image("bionic", arch="x86_64")
    with gce.launch(daily) as inst:
        inst.wait()
        print(inst.execute("lsb_release -a"))


def pro(gce):
    """Show example of running a GCE PRO machine."""
    daily = gce.daily_image("bionic", image_type=ImageType.PRO)
    with gce.launch(daily) as inst:
        inst.wait()
        print(inst.execute("sudo ua status --wait"))


def pro_fips(gce):
    """Show example of running a GCE PRO FIPS machine."""
    daily = gce.daily_image("bionic", image_type=ImageType.PRO_FIPS)
    with gce.launch(daily) as inst:
        inst.wait()
        print(inst.execute("sudo ua status --wait"))


def demo():
    """Show examples of launching GCP instances."""
    logging.basicConfig(level=logging.DEBUG)
    with pycloudlib.GCE(tag="examples") as gce:
        manage_ssh_key(gce)

        generic(gce)
        pro(gce)
        pro_fips(gce)


if __name__ == "__main__":
    demo()
