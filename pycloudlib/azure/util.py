# This file is part of pycloudlib. See LICENSE file for license information.
"""Azure Util Functions."""
import logging

from azure.common.client_factory import (get_client_from_cli_profile,
                                         get_client_from_json_dict)
from knack.util import CLIError


logger = logging.getLogger(__name__)


def get_client(resource, config_dict):
    """Get azure client based on the give resource.

    This method will first verify if we can get the client
    by using the information provided on the login account
    of the user machine. If the user is not logged into Azure,
    we will try to get the client from the ids given by the
    user to this class.

    Args:
        resource: Azure Resource, An Azure resource that we want to get
                    a client for.
        config_dict: dict, Id parameters passed by the user to this class.

    Returns:
        The client for the resource passed as parameter.

    """
    try:
        return get_client_from_cli_profile(resource)
    except CLIError:
        logger.debug(
            "No valid azure-cli config found. Trying explicit config params"
        )

    required_keys = frozenset(
        {"clientId", "clientSecret", "tenantId", "subscriptionId"}
    )
    missing_keys = required_keys.difference(set(config_dict.keys()))
    if missing_keys:
        raise RuntimeError(
            "No AZ cli config found, missing required keys: {}".format(
                ", ".join(missing_keys)
            )
        )

    parameters = {
        "activeDirectoryEndpointUrl":
            "https://login.microsoftonline.com",
        "resourceManagerEndpointUrl": "https://management.azure.com/",
        "activeDirectoryGraphResourceId":
            "https://graph.windows.net/",
        "sqlManagementEndpointUrl":
            "https://management.core.windows.net:8443/",
        "galleryEndpointUrl": "https://gallery.azure.com/",
        "managementEndpointUrl":
            "https://management.core.windows.net/"
    }
    parameters.update(config_dict)

    client = get_client_from_json_dict(
        resource,
        parameters
    )

    return client


def get_offer_from_image_id(image_id):
    """Extract offer from an image_id string.

    The image_id is expected to be a string in the following
    format: Canonical:UbuntuServer:19.10-DAILY. The offer is
    the first name after the first ':' symbol.

    Args:
        image_id: string, The image id

    Returns
        A string representing the image offer

    """
    return image_id.split(":")[1]


def get_sku_from_image_id(image_id):
    """Extract sku from an image_id string.

    The image_id is expected to be a string in the following
    format: Canonical:UbuntuServer:19.10-DAILY. The sku is
    the name after the second ':' symbol.

    Args:
        image_id: string, The image id

    Returns
        A string representing the image offer

    """
    return image_id.split(":")[-1]


def get_resource_group_name_from_id(resource_id):
    """Retrive the resource group name of a resource.

    Args:
        resource_id: string, the resource id

    Returns:
        A string represeting the resource group

    """
    return resource_id.split('/')[4]


def get_resource_name_from_id(resource_id):
    """Retrive the name of a resource.

    Args:
        resource_id: string, the resource id

    Returns:
        A string represeting the resource name

    """
    return resource_id.split('/')[-1]


def get_image_reference_params(image_id):
    """Return the correct parameter for image reference based on image id.

    Verify if the image id is associated with a current image found
    on Azure Marketplace or a custom image, for example, created through
    a snapshot process. Depending on the image id format, we can
    differentiate if we should create image parameters for a
    Marketplace image or a custom image.

    Args:
        image_id: string, Represents a image to be used when provisioning
                    a virtual machine

    Returns:
        A dict representing the image referece parameters that will be
        used to provision a virtual machine

    """
    # If the image id starts with 'Canonical", we know that it is a
    # marketplace image, and to we must reference it using the
    # combination of publisher, offer, sku and version info
    if image_id.startswith('Canonical'):
        return {
            "publisher": 'Canonical',
            "offer": get_offer_from_image_id(image_id),
            "sku": get_sku_from_image_id(image_id),
            "version": "latest"
        }

    # Custom images can be directly referenced by their id
    return {
        "id": image_id
    }
