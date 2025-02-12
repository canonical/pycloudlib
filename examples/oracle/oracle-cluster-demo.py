#!/usr/bin/env python3
# This file is part of pycloudlib. See LICENSE file for license information.
"""Basic examples of various lifecycle with an OCI instance."""

import logging
import sys

import pycloudlib

def demo_cluster(
    availability_domain: str = None,
    compartment_id: str = None,
    vcn_name: str = None,
):
    """Show example of using the OCI library to launch a cluster instance and ping between them."""

    with pycloudlib.OCI(
        "pycl-oracle-cluster-demo",
        availability_domain=availability_domain,
        compartment_id=compartment_id,
        vcn_name=vcn_name,
    ) as client:
        instances = client.create_compute_cluster(
            image_id=client.released_image("noble"),
            instance_count=2,
        )
        # get the private ips of the instances
        private_ips = [instance.private_ip for instance in instances]
        # try to ping each instance from each other instance at their private ip
        for instance in instances:
            for private_ip in private_ips:
                if private_ip != instance.private_ip:
                    print(f"Pinging {private_ip} from {instance.private_ip}")
                    r = instance.execute(f"ping -c 1 -W 5 {private_ip}")
                    if not r.ok:
                        print(f"Failed to ping {private_ip} from {instance.private_ip}")
                    else:
                        print(f"Successfully pinged {private_ip} from {instance.private_ip}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    if len(sys.argv) != 3:
        print(
            "No arguments passed via command line. "
            "Assuming values are set in pycloudlib configuration file."
        )
        demo_cluster()
    else:
        passed_availability_domain = sys.argv[1]
        passed_compartment_id = sys.argv[2]
        passed_vcn_name = sys.argv[3] if len(sys.argv) == 4 else None
        demo_cluster(passed_availability_domain, passed_compartment_id, passed_vcn_name)
