# This file is part of pycloudlib. See LICENSE file for license information.
"""Azure Util Functions."""
import logging
import re

from azure.core.exceptions import ClientAuthenticationError
from azure.identity import AzureCliCredential, ClientSecretCredential
from knack.util import CLIError

from pycloudlib import util

logger = logging.getLogger(__name__)

RE_AZURE_IMAGE_ID = (
    r"(?P<publisher>[^:]+):(?P<offer>[^:]+):(?P<sku>[^:]+)(:(?P<version>.*))?"
)


def get_client(resource, config_dict: dict):
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
    if not util.subp("command -v az", shell=True, rcs=[0, 1, 127]).ok:
        logger.debug(
            "No azure-cli 'az' command found. Trying explicit config params"
        )
    else:
        try:
            cli_credential = AzureCliCredential()
            subscription_id = config_dict.get("subscriptionId")
            client = resource(cli_credential, subscription_id=subscription_id)
            return client
        except CLIError:
            logger.debug(
                "No valid azure-cli config found."
                " Trying explicit config params"
            )
        except ClientAuthenticationError:
            logger.debug(
                "Authentication error: No valid azure-cli config found."
                " Trying explicit config params"
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
        "active_directory": "https://login.microsoftonline.com",
        "resource_manager": "https://management.azure.com/",
        "active_directory_graph_resource_id": "https://graph.windows.net/",
        "sql_management": "https://management.core.windows.net:8443/",
        "gallery": "https://gallery.azure.com/",
        "management": "https://management.core.windows.net/",
    }
    parameters.update(config_dict)
    credential = ClientSecretCredential(
        tenant_id=parameters["tenantId"],
        client_id=parameters["clientId"],
        client_secret=parameters["clientSecret"],
        authority=parameters["active_directory"],
    )

    return resource(
        credential, subscription_id=parameters["subscriptionId"], **parameters
    )


def parse_image_id(image_id):
    """Extract publisher, offer, sku and optional version from image_id.

    The image_id is expected to be a string in the following
    format: Canonical:UbuntuServer:19.10-DAILY[:latest]

    Args:
        image_id: string, The image id

    Returns
        Dict with publisher, offer and sku and optional version keys.

    """
    match = re.match(RE_AZURE_IMAGE_ID, image_id)
    if not match:
        # Snapshot image ids do not follow the publisher:offer:sku pattern
        return {}

    return match.groupdict()


def get_resource_group_name_from_id(resource_id):
    """Retrieve the resource group name of a resource.

    Args:
        resource_id: string, the resource id

    Returns:
        A string representing the resource group

    """
    return resource_id.split("/")[4]


def get_resource_name_from_id(resource_id):
    """Retrieve the name of a resource.

    Args:
        resource_id: string, the resource id

    Returns:
        A string representing the resource name

    """
    return resource_id.split("/")[-1]


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
        A dict representing the image reference parameters that will be
        used to provision a virtual machine

    """
    img_dict = parse_image_id(image_id)
    if img_dict.get("publisher") == "Canonical":
        # If the image id starts with 'Canonical", we know that it is a
        # marketplace image, and to we must reference it using the
        # combination of publisher, offer, sku and version info
        img_dict.update({"version": "latest"})
        return img_dict

    # Custom images can be directly referenced by their id
    return {"id": image_id}


def is_pro_image(image_id, registered_image):
    """Verify if the image id represents a pro image.

    Check the image id string for patterns found only on
    pro images. However, snapshot images do not have pro
    information on ther image id. We are enconding that
    information on the registed_image dict, which represents
    the base image that created the snapshot. Therefore,
    we fail at looking in the image id string, we look it up
    at the registered_image dict.

    Args:
        image_id: string, Represents a image to be used when provisioning
                  a virtual machine
        registered_image: dict, Represents the base image used for creating
                          the image referenced by image_id. This will only
                          happen for snapshot images.

    Returns:
        A boolean indicating if the image is pro image

    """
    offer = ""
    img_dict = parse_image_id(image_id)
    if img_dict.get("publisher") == "Canonical":
        offer = img_dict["offer"]
    elif registered_image is not None:
        offer = registered_image["offer"] or ""

    return bool("-pro-" in offer)


def get_plan_params(image_id, registered_image):
    """Return the correct parameter for plan based on pro image id.

    Args:
        image_id: string, Represents a image to be used when provisioning
                  a virtual machine
        registered_image: dict, Represents the base image used for creating
                          the image referenced by image_id. This will only
                          happen for snapshot images.

    Returns:
        A dict representing the plan parameters that will be
        used to provision a virtual machine

    """
    if registered_image is not None:
        return {
            "name": registered_image["sku"],
            "product": registered_image["offer"],
            "publisher": "canonical",
        }

    img_dict = parse_image_id(image_id)
    return {
        "name": img_dict.get("sku"),
        "product": img_dict.get("offer"),
        "publisher": img_dict.get("publisher", "").lower(),
    }
