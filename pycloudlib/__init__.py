# This file is part of pycloudlib. See LICENSE file for license information.
"""Main pycloud module __init__."""

import logging

from pycloudlib.ec2.cloud import EC2
from pycloudlib.lxd.cloud import LXD

__all__ = [
    'EC2',
    'LXD',
]

logging.getLogger(__name__).addHandler(logging.NullHandler())
