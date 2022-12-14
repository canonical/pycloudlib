# This file is part of pycloudlib. See LICENSE file for license information.
"""IBM Cloud type."""

from typing import List, Optional

from ibm_cloud_sdk_core.authenticators import IAMAuthenticator
from ibm_platform_services import ResourceManagerV2
from ibm_vpc import VpcV1
from ibm_vpc.vpc_v1 import Image, ListImagesEnums

from pycloudlib.cloud import BaseCloud
from pycloudlib.config import ConfigFile
from pycloudlib.ibm._util import IBMException
from pycloudlib.ibm._util import get_all as _get_all
from pycloudlib.ibm._util import get_first as _get_first
from pycloudlib.ibm._util import wait_until as _wait_until
from pycloudlib.ibm.instance import VPC, IBMInstance
from pycloudlib.instance import BaseInstance
from pycloudlib.util import UBUNTU_RELEASE_VERSION_MAP

DEFAULT_RESOURCE_GROUP: str = "Default"


class IBM(BaseCloud):
    """IBM Virtual Private Cloud Class."""

    _type = "ibm"

    def __init__(
        self,
        tag,
        timestamp_suffix=True,
        config_file: ConfigFile = None,
        *,
        resource_group: Optional[str] = None,
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

        self._resource_group = (
            resource_group
            or self.config.get("resource_group")
            or DEFAULT_RESOURCE_GROUP
        )
        self._resource_group_id = None
        self.region = str(region or self.config.get("region")).lower()
        self.zone = str(zone or self.config.get("zone")).lower()

        self._log.debug("logging into IBM")

        api_key = api_key or self.config.get("api_key")
        authenticator = IAMAuthenticator(api_key)

        self._client = VpcV1(authenticator=authenticator)
        self._client.set_service_url(
            f"https://{self.region}.iaas.cloud.ibm.com/v1"
        )

        self._resource_manager_service = ResourceManagerV2(
            authenticator=authenticator
        )

    @property
    def resource_group_id(self) -> str:
        """Resource Group ID used to create new things under."""
        if self._resource_group_id is None:
            self._resource_group_id = self._get_resource_group_id(
                self._resource_group
            )
            if self._resource_group_id is None:
                raise ValueError(
                    f"Resource Group not found: {self._resouce_group}"
                )
        return self._resource_group_id

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
        self._client.delete_image(image_id).get_result()

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

    def daily_image(self, release, **kwargs) -> str:
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

    def get_instance(self, instance_id: str, **kwargs) -> BaseInstance:
        """Get an instance by id.

        Args:
            instance_id:

        Returns:
            An instance object to use to manipulate the instance further.

        """
        return IBMInstance.find_existing(
            self.key_pair,
            client=self._client,
            instance_id=instance_id,
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
            return VPC.create(*args, **kwargs)

    def _create_floating_ip(self, name: Optional[str] = None) -> dict:
        # XXX: move this method to instance.py ?
        name = name or f"{self.tag}-fi"
        proto = {
            "name": name,
            "resource_group": {"id": self.resource_group_id},
            "zone": {"name": self.zone},
        }
        floating_ip = self._client.create_floating_ip(proto).get_result()
        self._log.info(f"Floating ip created: {floating_ip['name']}")
        return floating_ip

    def launch(
        self,
        image_id: str,
        instance_type: Optional[str] = "bx2-2x8",
        user_data=None,
        wait: bool = True,
        *,
        name: Optional[str] = None,
        vpc: Optional[VPC] = None,
        **kwargs,
    ) -> BaseInstance:
        """Launch an instance.

        TODO

        Args:
            image_id: string, image ID to use for the instance
            instance_type: string, type of instance to create
            user_data: used by cloud-init to run custom scripts/configuration
            wait: wait for instance to be live
            **kwargs: dictionary of other arguments to pass to launch

        Returns:
            An instance object to use to manipulate the instance further.

        """
        if not image_id:
            raise ValueError(
                f"{self._type} launch requires image_id param."
                f" Found: {image_id}"
            )

        if not vpc:
            vpc = VPC.from_default(
                self.key_pair,
                client=self._client,
                resource_group_id=self.resource_group_id,
                region=self.region,
                zone=self.zone,
            )

        floating_ip_name = f"{name}-fi" if name else None
        name = name or f"{self.tag}-vm"

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
        )

        floating_ip = self._create_floating_ip(name=floating_ip_name)
        instance = IBMInstance.with_floating_ip(
            self.key_pair,
            client=self._client,
            instance=raw_instance,
            floating_ip=floating_ip,
        )

        if wait:
            instance.wait()

        return instance

    def snapshot(
        self, instance: BaseInstance, clean: bool = True, **kwargs
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

        # XXX: move to instance
        source_volume = instance._instance["boot_volume_attachment"]["volume"][
            "id"
        ]

        image_prototype = {
            "name": f"{self.tag}-image",
            "resource_group": {"id": self.resource_group_id},
            "source_volume": {"id": source_volume},
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
        return snapshot_id

    def list_keys(self) -> List[str]:
        """List ssh key names present on the cloud for accessing instances.

        Returns:
           A list of strings of key pair names accessible to the cloud.

        """
        return _get_all(
            self._client.list_keys,
            resource_name="keys",
            map_fn=lambda key: key["name"],
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
        return self._client.create_key(
            public_key=self.key_pair.public_key_content,
            name=self.key_pair.name,
            resource_group={"id": self.resource_group_id},
        ).get_result()["id"]
