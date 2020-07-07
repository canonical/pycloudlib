# This file is part of pycloudlib. See LICENSE file for license information.
"""Main pycloud module __init__."""

import logging

from pycloudlib.ec2.cloud import EC2
from pycloudlib.gce.cloud import GCE
from pycloudlib.lxd.cloud import LXD
from pycloudlib.kvm.cloud import KVM
from pycloudlib.oci.cloud import OCI

__all__ = [
    'EC2',
    'GCE',
    'LXD',
    'KVM',
    'OCI',
]

logging.getLogger(__name__).addHandler(logging.NullHandler())
