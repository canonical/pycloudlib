# This file is part of pycloudlib. See LICENSE file for license information.
"""IBM Cloud type."""

import itertools
import re
from typing import List, Optional

from ibm_cloud_sdk_core import ApiException
from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from ibm_platform_services import ResourceManagerV2
from ibm_vpc import VpcV1
from ibm_vpc.vpc_v1 import Image, ListImagesEnums

from pycloudlib.cloud import BaseCloud
from pycloudlib.config import ConfigFile
from pycloudlib.errors import InvalidTagNameError
from pycloudlib.ibm._util import get_first as _get_first
from pycloudlib.ibm._util import iter_resources as _iter_resources
from pycloudlib.ibm._util import wait_until as _wait_until
from pycloudlib.ibm.errors import IBMException
from pycloudlib.ibm.instance import VPC, IBMInstance
from pycloudlib.instance import BaseInstance
from pycloudlib.util import UBUNTU_RELEASE_VERSION_MAP

DEFAULT_RESOURCE_GROUP: str = "Default"


class IBM(BaseCloud):
    """IBM Virtual Private Cloud Class."""

    _type = "ibm"

    def __init__(
        self,
        tag: str,
        timestamp_suffix: bool = True,
        config_file: Optional[ConfigFile] = None,
        *,
        resource_group: Optional[str] = None,
        vpc: Optional[str] = None,
        api_key: Optional[str] = None,
        region: Optional[str] = None,
        zone: Optional[str] = None,
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
            required_values=[resource_group, api_key, region],
        )
        self.created_vpcs: List[VPC] = []
        self.created_keys: List[str] = []

        self._resource_group = (
            resource_group
            or self.config.get("resource_group")
            or DEFAULT_RESOURCE_GROUP
        )
        self._resource_group_id: Optional[str] = None
        self.region = str(region or self.config.get("region")).lower()
        zone = zone or self.config.get("zone") or f"{self.region}-1"
        self.zone = str(zone).lower()

        self._vpc_name = vpc or self.config.get("vpc")
        self._vpc: Optional[VPC] = None

        self._log.debug("logging into IBM")

        api_key = api_key or self.config.get("api_key")
        authenticator = IAMAuthenticator(api_key)
        self.instance_counter = itertools.count(1)

        self._client = VpcV1(authenticator=authenticator)
        self._client.set_service_url(
            f"https://{self.region}.iaas.cloud.ibm.com/v1"
        )

        self._resource_manager_service = ResourceManagerV2(
            authenticator=authenticator
        )

        self._floating_ip_substring = self.config.get("floating_ip_substring")

    @property
    def resource_group_id(self) -> str:
        """Resource Group ID used to create new things under."""
        if self._resource_group_id is None:
            self._resource_group_id = self._get_resource_group_id(
                self._resource_group
            )
        if self._resource_group_id is None:
            raise IBMException(
                f"Resource Group not found: {self._resource_group}"
            )
        return self._resource_group_id

    @property
    def vpc(self) -> VPC:
        """Virtual Private Cloud."""
        if self._vpc is not None:
            return self._vpc

        kwargs = {
            "client": self._client,
            "resource_group_id": self.resource_group_id,
            "region": self.region,
            "zone": self.zone,
        }
        if self._vpc_name is not None:
            self._vpc = VPC.from_existing(
                self.key_pair, name=self._vpc_name, **kwargs
            )
        else:
            self._vpc = VPC.from_default(self.key_pair, **kwargs)

        return self._vpc

    def _get_resource_group_id(
        self, name: Optional[str] = None
    ) -> Optional[str]:
        name = name or f"{self.tag}-rg"

        result = self._resource_manager_service.list_resource_groups(
            name=name
        ).get_result()
        if result.get("resources"):
            return result["resources"][0]["id"]

        return None

    def delete_image(self, image_id: str, **kwargs):
        """Delete an image.

        Args:
            image_id: string, id of the image to delete
            **kwargs: dictionary of other arguments to pass to delete_image
        """
        try:
            self._client.delete_image(image_id).get_result()
        except ApiException as e:
            if "does not exist" not in str(e):
                raise

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
            "visibility": ListImagesEnums.Visibility.PUBLIC.value,
        }
        version = UBUNTU_RELEASE_VERSION_MAP[release].replace(".", "-")
        os_name = f"ubuntu-{version}-{arch}"

        # Images are sorted by (created_at, id), thus we return the first
        # one matching the criterion.
        image = _get_first(
            self._client.list_images,
            resource_name="images",
            filter_fn=lambda img: img["operating_system"]["name"] == os_name,
            **list_images_kwargs,
        )
        if image is None:
            raise ValueError(f"Image not found: {os_name}")
        return image["id"]

    def daily_image(self, release: str, **kwargs) -> str:
        """ID of the latest daily image for a particular release.

        Args:
            release: The release to look for

        Returns:
            A single string with the latest daily image ID for the
            specified release.

        """
        self._log.info(
            "There are no daily images in IBM Cloud."
            " Using released image instead"
        )
        return self.released_image(release, **kwargs)

    def image_serial(self, image_id):
        """Find the image serial of the latest daily image for a particular release.

        Args:
            image_id: string, Ubuntu image id

        Returns:
            string, serial of latest image

        """
        raise NotImplementedError(
            "IBM Cloud does not contain Ubuntu daily images"
        )

    def get_image_id_from_name(self, name: str) -> str:
        """
        Get the id of the first image whose name contains the given name.

        The name does not need to be an exact match, just a substring of
        the image name.

        Returns:
            string, image ID
        """
        image = _get_first(
            self._client.list_images,
            resource_name="images",
            filter_fn=lambda image: name in image["name"],
        )
        if image is None:
            raise IBMException(f"Image not found: {name}")
        return image["id"]

    def get_instance(
        self, instance_id: str, *, username: Optional[str] = None, **kwargs
    ) -> BaseInstance:
        """Get an instance by id.

        Args:
            instance_id: ID used identify the instance
            username: username to use when connecting via SSH

        Returns:
            An instance object to use to manipulate the instance further.

        """
        return IBMInstance.find_existing(
            self.key_pair,
            client=self._client,
            instance_id=instance_id,
            username=username,
        )

    def get_or_create_vpc(self, name: str) -> VPC:
        """Get a VPC by name or create it if not found."""
        args = (self.key_pair,)
        kwargs = {
            "client": self._client,
            "name": name,
            "resource_group_id": self.resource_group_id,
            "zone": self.zone,
        }
        try:
            return VPC.from_existing(*args, **kwargs)
        except IBMException:
            vpc = VPC.create(*args, **kwargs)
            self.created_vpcs.append(vpc)
            return vpc

    def launch(
        self,
        image_id: str,
        instance_type: str = "bx2-2x8",
        user_data=None,
        *,
        name: Optional[str] = None,
        vpc: Optional[VPC] = None,
        username: Optional[str] = None,
        floating_ip_substring: Optional[str] = None,
        **kwargs,
    ) -> BaseInstance:
        """Launch an instance.

        Args:
            image_id: string, image ID to use for the instance
            instance_type: string, type of instance to create
            user_data: used by cloud-init to run custom scripts/configuration
            name: instance name
            vpc: VPC to allocate the instance in. If not given, the instance
            username: username to use when connecting via SSH
            will be allocated in the zone's default VPC.
            floating_ip_substring: use existing floating IP whose name
            contains this substring. This floating IP will not be deleted
            when the instance is deleted.
            **kwargs: dictionary of other arguments to pass to launch

        Returns:
            An instance object to use to manipulate the instance further.

        """
        if not image_id:
            raise ValueError(
                f"{self._type} launch requires image_id param."
                f" Found: {image_id}"
            )

        vpc = vpc or self.vpc
        name = name or f"{self.tag}-vm{next(self.instance_counter)}"

        floating_ip_substring = (
            floating_ip_substring or self._floating_ip_substring
        )

        raw_instance = IBMInstance.create_raw_instance(
            client=self._client,
            name=name,
            image_id=image_id,
            vpc=vpc,
            instance_type=instance_type,
            resource_group_id=self.resource_group_id,
            zone=self.zone,
            user_data=user_data,
            key_id=self._get_or_create_key(),
            **kwargs,
        )

        instance: IBMInstance = IBMInstance.from_raw_instance(
            self.key_pair,
            client=self._client,
            instance=raw_instance,
            username=username,
        )

        # add instance to cleanup list before attaching floating ip in case of error during attach
        self.created_instances.append(instance)

        instance.attach_floating_ip(
            floating_ip_substring=floating_ip_substring
        )

        return instance

    def snapshot(
        self, instance: IBMInstance, clean: bool = True, **kwargs
    ) -> str:
        """Snapshot an instance and generate an image from it.

        Args:
            instance: Instance to snapshot
            clean: run instance clean method before taking snapshot

        Returns:
            An image id

        """
        if clean:
            instance.clean()

        instance.shutdown()

        self._log.debug("creating snapshot from instance %s", instance.id)

        image_prototype = {
            "name": f"{self.tag}-image",
            "resource_group": {"id": self.resource_group_id},
            "source_volume": {"id": instance.boot_volume_id},
        }

        snapshot_id = self._client.create_image(image_prototype).get_result()[
            "id"
        ]

        timeout_seconds = 300
        _wait_until(
            lambda: self._client.get_image(snapshot_id).get_result()["status"]
            == Image.StatusEnum.AVAILABLE.value,
            timeout_seconds=timeout_seconds,
            timeout_msg_fn=lambda: (
                f"Snapshot not available after {timeout_seconds} seconds. "
                "Check IBM VPC console."
            ),
        )
        self.created_images.append(snapshot_id)
        return snapshot_id

    def list_keys(self) -> List[str]:
        """List ssh key names present on the cloud for accessing instances.

        Returns:
           A list of strings of key pair names accessible to the cloud.

        """
        return list(
            _iter_resources(
                self._client.list_keys,
                resource_name="keys",
                map_fn=lambda key: key["name"],
            )
        )

    def delete_key(self, name: str):
        """Delete SSH key by name."""
        key = _get_first(
            self._client.list_keys,
            resource_name="keys",
            filter_fn=lambda key: key["name"] == name,
        )
        if not key:
            return
        self._log.debug("Deleting SSH key: %s", name)
        self._client.delete_key(key["id"])

    def _get_or_create_key(self) -> str:
        key = _get_first(
            self._client.list_keys,
            resource_name="keys",
            filter_fn=lambda key: key["name"] == self.key_pair.name,
        )
        if key is not None:
            return key["id"]

        self._log.info("Creating SSH key: %s", self.key_pair.name)
        key_id = self._client.create_key(
            public_key=self.key_pair.public_key_content,
            name=self.key_pair.name,
            resource_group={"id": self.resource_group_id},
        ).get_result()["id"]
        self.created_keys.append(key_id)
        return key_id

    # pylint: disable=broad-except
    def clean(self) -> List[Exception]:
        """Cleanup ALL artifacts associated with this Cloud instance.

        Cleanup any cloud artifacts created at any time during this class's
        existence. This includes all instances, snapshots, resources, etc.
        """
        # Not cleaning up floating ips here because they're 1:1
        # with an instance and get cleaned up by the instance
        exceptions = super().clean()
        for vpc in self.created_vpcs:
            try:
                vpc.delete()
            except Exception as e:
                exceptions.append(e)
        for key_id in self.created_keys:
            try:
                self._client.delete_key(key_id)
            except Exception as e:
                exceptions.append(e)
        return exceptions

    @staticmethod
    def _validate_tag(tag: str):
        """
        Ensure that this tag is a valid name for cloud resources.

        Rules:
        - All letters must be lowercase
        - Must be between 1 and 63 characters long
        - Must not start or end with a hyphen
        - Must be alphanumeric and hyphens only
        - Must start with a letter

        :param tag: tag to validate

        :return: tag if it is valid

        :raises InvalidTagNameError: if the tag is invalid
        """
        rules_failed = []
        # all letters must be lowercase
        if any(c.isupper() for c in tag):
            rules_failed.append("All letters must be lowercase")
        # must be between 1 and 63 characters long
        if len(tag) < 1 or len(tag) > 63:
            rules_failed.append("Must be between 1 and 63 characters long")
        # must not start or end with a hyphen
        if tag and (tag[0] in ("-") or tag[-1] in ("-")):
            rules_failed.append("Must not start or end with a hyphen")
        # must be alphanumeric and hyphens only
        if not re.match(r"^[a-z0-9-]*$", tag):
            rules_failed.append("Must be alphanumeric and hyphens only")
        # must start with a letter
        if tag and not tag[0].isalpha():
            rules_failed.append("Must start with a letter")

        if rules_failed:
            raise InvalidTagNameError(tag=tag, rules_failed=rules_failed)
