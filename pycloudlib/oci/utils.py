# This file is part of pycloudlib. See LICENSE file for license information.
"""Utilities for OCI images and instances."""

import logging
import os
import time
from typing import TYPE_CHECKING, Dict, Optional

import toml
from oci.retry import DEFAULT_RETRY_STRATEGY  # pylint: disable=E0611,E0401

from pycloudlib.errors import PycloudlibError, PycloudlibTimeoutError

if TYPE_CHECKING:
    import oci


log = logging.getLogger(__name__)


def wait_till_ready(
    func,
    current_data,
    desired_state,
    sleep_seconds=1000,
    func_kwargs: Optional[Dict[str, str]] = None,
):
    """Wait until the results of function call reach a desired lifecycle state.

    Args:
        func: The function to call
        current_data: Structure containing the initial id and lifecycle state
        desired_state: Desired value of "lifecycle_state"
        sleep_seconds: How long to wait in seconds
        func_kwargs: Dictionary with keyword arguments to pass to the function
    Returns:
        The updated version of the current_data
    Raises:
        PycloudlibTimeoutError: If the desired state is not reached in time
    """
    if func_kwargs is None:
        func_kwargs = {}

    for _ in range(sleep_seconds):
        current_data = func(current_data.id, **func_kwargs).data
        if current_data.lifecycle_state == desired_state:
            return current_data
        time.sleep(1)
    raise PycloudlibTimeoutError(
        "Expected {} state, but found {} after waiting {} seconds. "
        "Check OCI console for more details".format(
            desired_state, current_data.lifecycle_state, sleep_seconds
        )
    )

def get_subnet_id_by_name(
    network_client: "oci.core.VirtualNetworkClient",
    compartment_id: str,
    subnet_name: str,
    *,
    retry_strategy=DEFAULT_RETRY_STRATEGY,
) -> str:
    """Get a subnet id by name.

    Args:
        network_client: Instance of VirtualNetworkClient.
        compartment_id: Compartment where the subnet has to belong
        subnet_name: Name of the subnet to find
        retry_strategy: A retry strategy to apply to the API calls
    Returns:
        id of the subnet selected
    Raises:
        `Exception` if unable to determine `subnet_id` for
        `availability_domain`
    """
    subnets = network_client.list_subnets(
        compartment_id, display_name=subnet_name, retry_strategy=retry_strategy
    ).data
    if len(subnets) == 0:
        raise PycloudlibError(f"Unable to determine subnet name: {subnet_name}")
    if len(subnets) > 1:
        raise PycloudlibError(f"Found multiple subnets with name: {subnet_name}")
    return subnets[0].id


def get_subnet_id(
    network_client: "oci.core.VirtualNetworkClient",
    compartment_id: str,
    availability_domain: str,
    vcn_name: Optional[str] = None,
    private: bool = False,
    *,
    retry_strategy=DEFAULT_RETRY_STRATEGY,
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
        retry_strategy: A retry strategy to apply to the API calls
    Returns:
        id of the subnet selected
    Raises:
        `Exception` if unable to determine `subnet_id` for
        `availability_domain`
    """
    if vcn_name is not None:  # if vcn_name specified, use that vcn
        vcns = network_client.list_vcns(
            compartment_id,
            display_name=vcn_name,
            retry_strategy=retry_strategy,
        ).data
        if len(vcns) == 0:
            raise PycloudlibError(f"Unable to determine vcn name: {vcn_name}")
        if len(vcns) > 1:
            raise PycloudlibError(f"Found multiple vcns with name: {vcn_name}")
    else:  # if no vcn_name specified, use most recently created vcn
        vcns = network_client.list_vcns(compartment_id, retry_strategy=retry_strategy).data
        if len(vcns) == 0:
            raise PycloudlibError("No VCNs found in compartment")
    vcn_id = vcns[0].id
    chosen_vcn_name = vcns[0].display_name

    subnets = network_client.list_subnets(
        compartment_id, vcn_id=vcn_id, retry_strategy=retry_strategy
    ).data
    subnet_id = None
    for subnet in subnets:
        if subnet.prohibit_internet_ingress and not private:  # skip subnet if it's private
            log.debug(
                "Ignoring private subnet: %s [id: %s]",
                subnet.display_name,
                subnet.id,
            )
            continue
        if not subnet.prohibit_internet_ingress and private:  # skip subnet if it's public
            log.debug(
                "Ignoring public subnet: %s [id: %s]",
                subnet.display_name,
                subnet.id,
            )
            continue
        if subnet.availability_domain and subnet.availability_domain != availability_domain:
            log.debug(
                "Ignoring subnet in different availability domain: %s [id: %s]",
                subnet.display_name,
                subnet.id,
            )
            continue
        if not private and not subnet.prohibit_internet_ingress:
            log.info("Using public subnet: %s [id: %s]", subnet.display_name, subnet.id)
            subnet_id = subnet.id
            break
        if private and subnet.prohibit_internet_ingress:
            log.info("Using private subnet: %s [id: %s]", subnet.display_name, subnet.id)
            subnet_id = subnet.id
            break
    if not subnet_id:
        raise PycloudlibError(f"Unable to find suitable subnet in VCN {chosen_vcn_name}")
    return subnet_id


def _load_and_preprocess_oci_toml_file(toml_file_contents: str) -> Dict[str, str]:
    """
    Read in the OCI config file from the given path and preprocess it.

    This includes removing the profile name if it exists, and ensuring all entries are quoted toml
    strings if they are not already quoted.

    Args:
        toml_file_contents (str): The contents of the OCI config file as a string.

    Returns:
        oci_config: A dictionary containing the OCI config file.

    Raises:
        toml.TomlDecodeError: If the OCI config file cannot be decoded as a TOML file.
        TypeError: If the OCI config file cannot be decoded as a TOML file.
    """
    toml_file_contents = toml_file_contents.strip()
    # if the file starts with "[", remove it so there is no profile name
    if toml_file_contents.startswith("["):
        toml_file_contents = toml_file_contents[toml_file_contents.find("\n") + 1 :]
    # make sure all entries are quoted toml strings if not already quoted
    for line in toml_file_contents.splitlines():
        if "=" in line:
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip()
            if not value.startswith('"') and not value.startswith("'"):
                toml_file_contents = toml_file_contents.replace(
                    f"{key}={value}", f'{key}="{value}"'
                )
    return toml.loads(toml_file_contents)


def parse_oci_config_from_env_vars() -> Optional[Dict[str, str]]:
    """Read in OCI config file from environment variables and return as a config dict.

    If $PYCLOUDLIB_OCI_CONFIG_FILE_PATH is set, reads in the OCI config file from this path.
    If $PYCLOUDLIB_OCI_KEY_FILE_PATH is set, replaces or adds the key_file path to the config dict.

    Returns:
        oci_config: A dictionary containing the OCI config file, or None if the environment
            variable $PYCLOUDLIB_OCI_CONFIG_FILE_PATH is not set.

    Raises:
        PycloudlibError: If the OCI config file cannot be loaded from the path given by the
            $PYCLOUDLIB_OCI_CONFIG_FILE_PATH environment variable.
    """
    config_path_from_env = os.getenv("PYCLOUDLIB_OCI_CONFIG_FILE_PATH")
    if not config_path_from_env:
        return None
    # Read in the OCI config file
    with open(config_path_from_env, encoding="utf-8") as f:
        try:
            oci_config = _load_and_preprocess_oci_toml_file(f.read())
        except (toml.TomlDecodeError, TypeError, ValueError, UnicodeDecodeError) as e:
            raise PycloudlibError(
                f"Failed to load OCI config dict from path '{config_path_from_env}' given by "
                f"$PYCLOUDLIB_OCI_CONFIG_FILE_PATH: {e}"
            ) from e
        log.info("Using OCI config file from environment variable $PYCLOUDLIB_OCI_CONFIG_FILE_PATH")

    # If OCI_KEY_FILE_PATH is set, replace or add the key_file path to the config dict
    key_file_path = os.getenv("PYCLOUDLIB_OCI_KEY_FILE_PATH")
    if key_file_path:
        log.info("Using OCI key file path from environment variable $PYCLOUDLIB_OCI_KEY_FILE_PATH")
        if "key_file" in oci_config:
            log.info("Replacing existing key_file path in OCI config")
        oci_config["key_file"] = key_file_path
    return oci_config
