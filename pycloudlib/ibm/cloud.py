# This file is part of pycloudlib. See LICENSE file for license information.
"""Base class for all other clouds to provide consistent set of functions."""

from typing import Optional

from ibm_cloud_sdk_core import DetailedResponse
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from ibm_vpc import VpcV1

from pycloudlib.cloud import BaseCloud
from pycloudlib.config import ConfigFile
from pycloudlib.ibm.util import iter_pagination
from pycloudlib.instance import BaseInstance
from pycloudlib.util import UBUNTU_RELEASE_VERSION_MAP


class IBM_VPC(BaseCloud):
    """IBM Virtual Private Cloud Class."""

    _type = "ibm"

    def __init__(
        self,
        tag,
        timestamp_suffix=True,
        config_file: ConfigFile = None,
        *,
        api_key: Optional[str] = None,
    ):
        """Initialize the connection to IBM VPC.

        Args:
            tag: string used to name and tag resources with
            timestamp_suffix: Append a timestamped suffix to the tag string.
            config_file: path to pycloudlib configuration file
        """
        super().__init__(
            tag,
            timestamp_suffix,
            config_file,
            required_values=[api_key],
        )
        self._log.debug("logging into IBM")

        api_key = api_key or self.config.get("api_key")
        authenticator = IAMAuthenticator(api_key)
        self.vpc_service = VpcV1(authenticator=authenticator)

    def delete_image(self, image_id, **kwargs):
        """Delete an image.

        Args:
            image_id: string, id of the image to delete
            **kwargs: dictionary of other arguments to pass to delete_image
        """
        raise NotImplementedError("TODO")

    def released_image(self, release, *, arch: str = "amd64", **kwargs):
        """ID of the latest released image for a particular release.

        Args:
            release: The release to look for

        Returns:
            A single string with the latest released image ID for the
            specified release.

        """
        list_images_kwargs = {
            "start": None,
            "limit": None,
            "resource_group_id": None,
            "name": None,
            "visibility": None,
        }
        version = UBUNTU_RELEASE_VERSION_MAP[release].replace(".", "-")
        os_name = f"ubuntu-{version}-{arch}"
        # Images are sorted by (created_at, id), thus we return the first one matching the criteria
        for resp in iter_pagination(
            self.vpc_service.list_images, **list_images_kwargs
        ):
            images = resp.get_result().get("images", [])
            try:
                image = next(
                    filter(
                        lambda img: img["operating_system"]["name"] == os_name,
                        images,
                    )
                )
            except StopIteration:
                continue
            return image["id"]

    def daily_image(self, release, **kwargs) -> str:
        """ID of the latest daily image for a particular release.

        Args:
            release: The release to look for

        Returns:
            A single string with the latest daily image ID for the
            specified release.

        """
        return self.released_image(release, **kwargs)

    def image_serial(self, image_id):
        """Find the image serial of the latest daily image for a particular release.

        Args:
            image_id: string, Ubuntu image id

        Returns:
            string, serial of latest image

        """
        raise NotImplementedError("TODO")

    def get_instance(self, instance_id, **kwargs) -> BaseInstance:
        """Get an instance by id.

        Args:
            instance_id:

        Returns:
            An instance object to use to manipulate the instance further.

        """
        raise NotImplementedError("TODO")

    def launch(
        self, image_id, instance_type=None, user_data=None, wait=True, **kwargs
    ) -> BaseInstance:
        """Launch an instance.

        Args:
            image_id: string, image ID to use for the instance
            instance_type: string, type of instance to create
            user_data: used by cloud-init to run custom scripts/configuration
            wait: wait for instance to be live
            **kwargs: dictionary of other arguments to pass to launch

        Returns:
            An instance object to use to manipulate the instance further.

        """
        raise NotImplementedError("TODO")

    def snapshot(self, instance, clean=True, **kwargs):
        """Snapshot an instance and generate an image from it.

        Args:
            instance: Instance to snapshot
            clean: run instance clean method before taking snapshot

        Returns:
            An image id

        """
        raise NotImplementedError("TODO")

    def list_keys(self):
        """List ssh key names present on the cloud for accessing instances.

        Returns:
           A list of strings of key pair names accessible to the cloud.

        """
        raise NotImplementedError("TODO")
