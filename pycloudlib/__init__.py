# This file is part of pycloudlib. See LICENSE file for license information.
"""Main pycloud module __init__."""

import logging

from pycloudlib.azure.cloud import Azure
from pycloudlib.ec2.cloud import EC2
from pycloudlib.gce.cloud import GCE
from pycloudlib.ibm.cloud import IBM
from pycloudlib.lxd.cloud import LXD, LXDContainer, LXDVirtualMachine
from pycloudlib.oci.cloud import OCI
from pycloudlib.openstack.cloud import Openstack
from pycloudlib.qemu.cloud import Qemu
from pycloudlib.vmware.cloud import VMWare

__all__ = [
    "Azure",
    "EC2",
    "GCE",
    "IBM",
    "LXD",
    "LXDContainer",
    "LXDVirtualMachine",
    "OCI",
    "Openstack",
    "Qemu",
    "VMWare",
]

logging.getLogger(__name__).addHandler(logging.NullHandler())
