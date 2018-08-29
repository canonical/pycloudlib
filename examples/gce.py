#!/usr/bin/env python3
# This file is part of pycloudlib. See LICENSE file for license information.
"""Basic examples of various lifecycle with an GCE instance."""

import logging

import pycloudlib


def demo():
    """Show example of using the GCE library.

    Connects to GCE and finds the latest daily image. Then runs
    through a number of examples.
    """
    gce = pycloudlib.GCE(
        tag='examples',
        project='my_project_name',
        region='us-west2',
        zone='a'
    )
    daily = gce.daily_image('bionic')
    gce.launch(daily)


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    demo()
