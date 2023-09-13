# This file is part of pycloudlib. See LICENSE file for license information.
"""Utilities for OCI images and instances."""
import time
from typing import TYPE_CHECKING, Optional

from pycloudlib.errors import PycloudlibError

if TYPE_CHECKING:
    import oci


def wait_till_ready(func, current_data, desired_state, sleep_seconds=1000):
    """Wait until the results of function call reach a desired lifecycle state.

    Args:
        func: The function to call
        current_data: Structure containing the initial id and lifecycle state
        desired_state: Desired value of "lifecycle_state"
        sleep_seconds: How long to wait in seconds
    Returns:
        The updated version of the current_data
    """
    for _ in range(sleep_seconds):
        current_data = func(current_data.id).data
        if current_data.lifecycle_state == desired_state:
            return current_data
        time.sleep(1)
    raise PycloudlibError(
        "Expected {} state, but found {} after waiting {} seconds. "
        "Check OCI console for more details".format(
            desired_state, current_data.lifecycle_state, sleep_seconds
        )
    )


def get_subnet_id(
    network_client: "oci.core.VirtualNetworkClient",  # type: ignore
    compartment_id: str,
    availability_domain: str,
    vcn_name: Optional[str] = None,
) -> str:
    """Get a subnet id linked to `availability_domain`.

    From specified compartment select the first subnet linked to
    `availability_domain` or the first one.

    Args:
        network_client: Instance of VirtualNetworkClient.
        compartment_id: Compartment where the subnet has to belong
        availability_domain: Domain to look for subnet id in.
        vcn_name: Exact name of the VCN to use. If not provided, the newest
            VCN in the given compartment will be used.
    Returns:
        id of the subnet selected
    Raises:
        `Exception` if unable to determine `subnet_id` for
        `availability_domain`
    """
    if vcn_name is not None:  # if vcn_name specified, use that vcn
        vcns = network_client.list_vcns(
            compartment_id, display_name=vcn_name
        ).data
        if len(vcns) == 0:
            raise PycloudlibError(f"Unable to determine vcn name: {vcn_name}")
        if len(vcns) > 1:
            raise PycloudlibError(f"Found multiple vcns with name: {vcn_name}")
        vcn_id = vcns[0].id
    else:  # if no vcn_name specified, use most recently created vcn
        vcn_id = network_client.list_vcns(compartment_id).data[0].id

    subnets = network_client.list_subnets(compartment_id, vcn_id=vcn_id).data
    subnet_id = None
    for subnet in subnets:
        if subnet.prohibit_internet_ingress:  # skip subnet if it's private
            print("Ignoring private subnet: " + subnet.id)
            continue
        print("Using public subnet: " + subnet.id)
        if subnet.availability_domain == availability_domain:
            subnet_id = subnet.id
            break
    else:
        subnet_id = subnets[0].id
    if not subnet_id:
        raise PycloudlibError(
            f"Unable to determine subnet id for domain: {availability_domain}"
        )
    return subnet_id
