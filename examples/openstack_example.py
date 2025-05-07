#!/usr/bin/env python3
# This file is part of pycloudlib. See LICENSE file for license information.
"""Basic examples of various lifecycles with a Openstack instance."""

import logging
import os
import sys

import pycloudlib

REQUIRED_ENV_VARS = ("OS_AUTH_URL", "OS_PASSWORD", "OS_USERNAME")


def basic_lifecycle(image_id: str):
    """Demonstrate basic set of lifecycle operations with OpenStack."""
    with pycloudlib.Openstack("pycloudlib-test") as os_cloud:
        with os_cloud.launch(image_id=image_id) as inst:
            inst.wait()

            result = inst.execute("uptime")
            print(result)
            inst.console_log()
            inst.delete(wait=False)


def demo(image_id: str):
    """Show examples of using the Openstack module."""
    basic_lifecycle(image_id)


def assert_openstack_config():
    """Assert any required OpenStack env variables and args needed for demo."""
    if len(sys.argv) != 2:
        sys.stderr.write(
            f"Usage: {sys.argv[0]} <openstack_image_id>\n"
            "Must provide an image id from openstack image list\n\n"
        )
        sys.exit(1)
    for env_name in REQUIRED_ENV_VARS:
        assert os.environ.get(
            env_name
        ), f"Missing required Openstack environment variable: {env_name}"


if __name__ == "__main__":
    assert_openstack_config()
    logging.basicConfig(level=logging.DEBUG)
    image_id = sys.argv[1]
    demo(image_id=sys.argv[1])
