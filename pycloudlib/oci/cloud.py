# pylint: disable=E1101
# This file is part of pycloudlib. See LICENSE file for license information.
"""OCI Cloud type."""

import base64
import json
import os
import re
from typing import Optional, cast

import oci

from pycloudlib.cloud import BaseCloud, ImageInfo
from pycloudlib.config import ConfigFile
from pycloudlib.errors import (
    CloudSetupError,
    InstanceNotFoundError,
    InvalidTagNameError,
    PycloudlibException,
)
from pycloudlib.oci.instance import OciInstance
from pycloudlib.oci.utils import get_subnet_id, wait_till_ready
from pycloudlib.util import UBUNTU_RELEASE_VERSION_MAP, subp


class OCI(BaseCloud):
    """OCI (Oracle) cloud class."""

    _type = "oci"

    def __init__(
        self,
        tag: str,
        timestamp_suffix: bool = True,
        config_file: Optional[ConfigFile] = None,
        *,
        availability_domain: Optional[str] = None,
        compartment_id: Optional[str] = None,
        config_path: Optional[str] = None,
        config_dict: Optional[dict] = None,
        vcn_name: Optional[str] = None,
        fault_domain: Optional[str] = None,
        profile: Optional[str] = None,
        region: Optional[str] = None,
    ):  # pylint: disable-msg=too-many-locals
        """
        Initialize the connection to OCI.

        OCI must be initialized on the CLI first:
        https://github.com/cloud-init/qa-scripts/blob/master/doc/launching-oracle.md

        Args:
            tag: Name of instance
            timestamp_suffix: bool set True to append a timestamp suffix to the
                tag
            config_file: path to pycloudlib configuration file
            compartment_id: A compartment found at
                https://console.us-phoenix-1.oraclecloud.com/a/identity/compartments
            availability_domain: One of the availability domains from:
                'oci iam availability-domain list'
            config_path: Path of OCI config file
            config_dict: A dictionary containing the OCI config.
                Overrides the values from config_path
            vcn_name: Exact name of the VCN to use. If not provided, the newest
                VCN in the given compartment will be used.
        """
        super().__init__(
            tag,
            timestamp_suffix,
            config_file,
            required_values=[availability_domain, compartment_id],
        )

        self.availability_domain = availability_domain or self.config["availability_domain"]

        compartment_id = compartment_id or self.config.get("compartment_id")
        if not compartment_id:
            command = ["oci", "iam", "compartment", "get"]
            exception_text = (
                "Could not obtain OCI compartment id. Has the CLI client been "
                "setup?\nCommand attempted: '{}'".format(" ".join(command))
            )
            try:
                result = subp(command, rcs=())
            except FileNotFoundError as e:
                raise CloudSetupError(exception_text) from e
            if not result.ok:
                exception_text += "\nstdout: {}\nstderr: {}".format(result.stdout, result.stderr)
                raise CloudSetupError(exception_text)
            compartment_id = cast(str, json.loads(result.stdout)["data"]["id"])
        self.compartment_id = compartment_id

        if config_dict:
            try:
                oci.config.validate_config(config_dict)
                self.oci_config = config_dict
                if profile:
                    self._log.warning("Profile name is ignored when using config_dict")
            except oci.exceptions.InvalidConfig as e:
                raise ValueError(f"Config dict is invalid. Pass a valid config dict. {e}") from e

        else:
            config_path = config_path or self.config.get("config_path") or "~/.oci/config"
            if not os.path.isfile(os.path.expanduser(config_path)):
                raise ValueError(
                    "{} is not a valid config file. Pass a valid config file.".format(config_path)
                )
            profile = profile or self.config.get("profile")
            if profile:
                self.oci_config = oci.config.from_file(config_path, profile_name=profile)
            else:
                self.oci_config = oci.config.from_file(config_path)

        self.oci_config["region"] = region or self.config.get("region") or self.oci_config["region"]
        self.region = self.oci_config["region"]

        self.vcn_name = vcn_name
        self.fault_domain = fault_domain
        self._log.debug("Logging into OCI")
        self.compute_client = oci.core.ComputeClient(self.oci_config)  # noqa: E501
        self.network_client = oci.core.VirtualNetworkClient(self.oci_config)  # noqa: E501

    def delete_image(self, image_id, **kwargs):
        """Delete an image.

        Args:
            image_id: string, id of the image to delete
        """
        self.compute_client.delete_image(image_id, **kwargs)

    def released_image(self, release, operating_system="Canonical Ubuntu"):
        """Get the released image.

        OCI just has periodic builds, so "released" and "daily" don't
        really make sense here. Just call the same code for both

        Args:
            release: string, Ubuntu release to look for
            operating_system: string, operating system to use
        Returns:
            string, id of latest image

        """
        return self.daily_image(release, operating_system)

    def daily_image(
        self,
        release: str,
        operating_system: str = "Canonical Ubuntu",
        **kwargs,
    ):
        """Get the daily image.

        OCI just has periodic builds, so "released" and "daily" don't
        really make sense here. Just call the same code for both.

        Should be equivalent to the cli call:
        oci compute image list \
          --operating-system="Canonical Ubuntu" \
          --operating-system-version="<xx.xx>" \
          --sort-by='TIMECREATED' \
          --sort-order='DESC'

        Args:
            release: string, Ubuntu release to look for
            operating_system: string, Operating system to use
            **kwargs: dictionary of other arguments to pass to list_images

        Returns:
            string, id of latest image

        """
        if operating_system == "Canonical Ubuntu":
            if not re.match(r"^\d{2}\.\d{2}$", release):  # 18.04, 20.04, etc
                try:
                    release = UBUNTU_RELEASE_VERSION_MAP[release]
                except KeyError as e:
                    raise ValueError("Invalid release") from e

        # OCI likes to keep a few of each image around, so sort by
        # timestamp descending and grab the first (most recent) one
        image_response = self.compute_client.list_images(
            self.compartment_id,
            operating_system=operating_system,
            operating_system_version=release,
            sort_by="TIMECREATED",
            sort_order="DESC",
            **kwargs,
        )
        matching_image = [
            i
            for i in image_response.data
            if "aarch64" not in i.display_name and "GPU" not in i.display_name
        ]
        image_id = matching_image[0].id
        return image_id

    def image_serial(self, image_id):
        """Find the image serial of the latest daily image for a particular release.

        Args:
            image_id: string, Ubuntu image id

        Returns:
            string, serial of latest image

        """
        raise NotImplementedError

    def get_image_id_from_name(self, name: str) -> str:
        """Get the image id from the name.

        Args:
            name: string, name of the image to get the id for

        Returns:
            string, id of the image

        """
        image_response = self.compute_client.list_images(self.compartment_id, display_name=name)
        if not image_response.data:
            raise PycloudlibException(f"Image with name {name} not found")
        return image_response.data[0].id

    def get_instance(self, instance_id, *, username: Optional[str] = None, **kwargs) -> OciInstance:
        """Get an instance by id.

        Args:
            instance_id: ocid of the instance
            username: username to use when connecting via SSH
            **kwargs: dictionary of other arguments to pass to get_instance
        Returns:
            An instance object to use to manipulate the instance further.
        """
        # verifies that instance id exists in oracle
        try:
            self.compute_client.get_instance(instance_id, **kwargs)
        except oci.exceptions.ServiceError as e:
            raise InstanceNotFoundError(resource_id=instance_id) from e

        return OciInstance(
            key_pair=self.key_pair,
            instance_id=instance_id,
            compartment_id=self.compartment_id,
            availability_domain=self.availability_domain,
            oci_config=self.oci_config,
            username=username,
        )

    def launch(
        self,
        image_id,
        instance_type="VM.Standard2.1",
        user_data=None,
        *,
        retry_strategy=None,
        username: Optional[str] = None,
        **kwargs,
    ) -> OciInstance:
        """Launch an instance.

        Args:
            image_id: string, image ID to use for the instance
            instance_type: string, type of instance to create.
                https://docs.cloud.oracle.com/en-us/iaas/Content/Compute/References/computeshapes.htm
            user_data: used by Cloud-Init to run custom scripts or
                provide custom Cloud-Init configuration
            retry_strategy: a retry strategy from oci.retry module
                to apply for this operation
            username: username to use when connecting via SSH
            vcn_name: Name of the VCN to use. If not provided, the first VCN
                found will be used
            **kwargs: dictionary of other arguments to pass as
                LaunchInstanceDetails

        Returns:
            An instance object to use to manipulate the instance further.
        Raises: ValueError on invalid image_id
        """
        if not image_id:
            raise ValueError(f"{self._type} launch requires image_id param. Found: {image_id}")
        subnet_id = get_subnet_id(
            self.network_client,
            self.compartment_id,
            self.availability_domain,
            vcn_name=self.vcn_name,
        )
        metadata = {
            "ssh_authorized_keys": self.key_pair.public_key_content,
        }
        if user_data:
            metadata["user_data"] = base64.b64encode(user_data.encode("utf8")).decode("ascii")

        instance_details = oci.core.models.LaunchInstanceDetails(  # noqa: E501
            display_name=self.tag,
            availability_domain=self.availability_domain,
            compartment_id=self.compartment_id,
            fault_domain=self.fault_domain,
            shape=instance_type,
            subnet_id=subnet_id,
            image_id=image_id,
            metadata=metadata,
            **kwargs,
        )

        instance_data = self.compute_client.launch_instance(
            instance_details, retry_strategy=retry_strategy
        ).data
        instance = self.get_instance(
            instance_data.id,
            retry_strategy=retry_strategy,
            username=username,
        )
        self.created_instances.append(instance)
        return instance

    def snapshot(self, instance, clean=True, name=None):
        """Snapshot an instance and generate an image from it.

        Args:
            instance: Instance to snapshot
            clean: run instance clean method before taking snapshot
            name: (Optional) Name of created image
        Returns:
            An image object
        """
        if clean:
            instance.clean()
        image_details = {
            "compartment_id": self.compartment_id,
            "instance_id": instance.instance_id,
        }
        if name:
            image_details["display_name"] = name
        image_data = self.compute_client.create_image(
            oci.core.models.CreateImageDetails(**image_details)
        ).data
        image_data = wait_till_ready(
            func=self.compute_client.get_image,
            current_data=image_data,
            desired_state="AVAILABLE",
        )

        self.created_images.append(image_data.id)

        return image_data.id

    @staticmethod
    def _validate_tag(tag: str):
        """
        Ensure that this tag is a valid name for cloud resources.

        Rules:
        - Must be between 1 and 255 characters long
        - Must not have leading or trailing whitespace

        :param tag: tag to validate

        :raises InvalidTagNameError: if the tag is invalid
        """
        rules_failed = []
        # must be between 1 and 255 characters long
        if len(tag) < 1 or len(tag) > 255:
            rules_failed.append("Must be between 1 and 255 characters long")
        if tag != tag.strip():
            rules_failed.append("Must not have leading or trailing whitespace")

        if rules_failed:
            raise InvalidTagNameError(tag=tag, rules_failed=rules_failed)

    # all actual "Clouds" and not just substrates like LXD and QEMU should support this method
    def upload_local_file_to_cloud_storage(
        self,
        *,
        local_file_path: str,
        storage_name: str,
        remote_file_name: Optional[str] = None,
        overwrite_existing: bool = False,
    ) -> str:
        """
        Upload a file to a storage destination on the Cloud.

        Args:
            local_file_path: The local file path of the image to upload.
            storage_name: The name of the storage destination on the Cloud to upload the file to.
            remote_file_name: The name of the file in the storage destination. If not provided,
            the base name of the local file path will be used.

        Returns:
            str: URL of the uploaded file in the storage destination.
        """
        object_storage_client = oci.object_storage.ObjectStorageClient(self.oci_config)
        namespace = object_storage_client.get_namespace().data
        bucket_name = storage_name
        remote_file_name = remote_file_name or os.path.basename(local_file_path)

        # if remote file name is missing the extension, add it from the local file path
        if not remote_file_name.endswith(ext:="."+local_file_path.split('.')[-1]):
            remote_file_name += ext

        # check if object already exists in the bucket
        try:
            object_storage_client.get_object(
                namespace,
                bucket_name,
                remote_file_name
            )
            if overwrite_existing:
                self._log.warning(
                    f"Object {remote_file_name} already exists in the bucket {bucket_name}. "
                    "Overwriting it."
                )
            else:
                self._log.info(
                    "Skipping upload as the object already exists in the bucket."
                )
                return f"https://objectstorage.{self.region}.oraclecloud.com/n/{namespace}/b/{bucket_name}/o/{remote_file_name}"
        except oci.exceptions.ServiceError as e:
            if e.status != 404:
                raise e

        with open(local_file_path, 'rb') as file:
            object_storage_client.put_object(
                namespace,
                bucket_name,
                remote_file_name,
                file
            )

        return f"https://objectstorage.{self.region}.oraclecloud.com/n/{namespace}/b/{bucket_name}/o/{remote_file_name}"

    def create_image_from_local_file(
        self,
        *,
        local_file_path: str,
        image_name: str,
        intermediary_storage_name: str,
        suite: str,
    ) -> ImageInfo:
        """
        Upload local image file to storage on the Cloud and then create a custom image from it.

        Args:
            local_file_path: The local file path of the image to upload.
            image_name: The name to upload the image as and to register.
            intermediary_storage_name: The intermediary storage destination on the Cloud to upload
            the file to before creating the image.
            suite: The suite of the image to create. I.e. "noble", "jammy", or "focal".

        Returns:
            ImageInfo: Information about the created image.
        """
        remote_file_url = self.upload_local_file_to_cloud_storage(
            local_file_path=local_file_path,
            storage_name=intermediary_storage_name,
            remote_file_name=image_name,
        )
        return self._create_image_from_cloud_storage(
            image_name=image_name,
            remote_image_file_url=remote_file_url,
            suite=suite,
        )
    
    def parse_remote_object_url(self, remote_object_url: str) -> tuple[str, str, str]:
        """
        Parse the remote object URL to extract the namespace, bucket name, and object name.

        Args:
            remote_object_url: The URL of the object in the Cloud storage.

        Returns:
            tuple[str, str, str]: The namespace, bucket name, and object name.
        """
        if not remote_object_url.startswith("https://objectstorage"):
            raise ValueError("Invalid URL. Expected a URL from the Oracle Cloud object storage.")
        parts = remote_object_url.split("/")
        # find the "n/", "b/", and "o/" parts of the URL
        namespace_index = parts.index("n") + 1
        bucket_index = parts.index("b") + 1
        object_index = parts.index("o") + 1
        return parts[namespace_index], parts[bucket_index], parts[object_index]

    def _create_image_from_cloud_storage(
        self,
        *,
        image_name: str,
        remote_image_file_url: str,
        suite: str,
        image_description: Optional[str] = None,
    ) -> ImageInfo:
        """
        Register a custom image in the Cloud from a file in Cloud storage using its url.

        Ideally, this url would be returned from the upload_local_file_to_cloud_storage method.

        Args:
            image_name: The name the image will be created with.
            remote_image_file_url: The URL of the image file in the Cloud storage.
            image_description: (Optional) A description of the image.
        """
        suites = {
            "plucky": "25.10",
            "oracular": "24.10",
            "noble": "24.04",
            "jammy": "22.04",
            "focal": "20.04",
        }
        if suite not in suites:
            raise ValueError(f"Invalid suite. Expected one of {list(suites.keys())}. Found: {suite}")
        # parse object name and bucket name from the url
        object_namespace, bucket_name, object_name = self.parse_remote_object_url(remote_image_file_url)
        self._log.debug(f"Bucket name: {bucket_name}, Object name: {object_name}, Object namespace: {object_namespace}")
        image_details = oci.core.models.CreateImageDetails(
            compartment_id=self.compartment_id,
            display_name=image_name,
            image_source_details=oci.core.models.ImageSourceViaObjectStorageTupleDetails(
                source_type="objectStorageTuple",
                bucket_name=bucket_name,
                object_name=object_name,
                namespace_name=object_namespace,
                operating_system="Canonical Ubuntu",
                operating_system_version=suites[suite],
            ),
            launch_mode="PARAVIRTUALIZED",
            freeform_tags={"Description": image_description} if image_description else None
        )

        image_data = self.compute_client.create_image(image_details).data
        image_data = wait_till_ready(
            func=self.compute_client.get_image,
            current_data=image_data,
            desired_state="AVAILABLE",
            sleep_seconds=30*60, # 30 minutes since image creation can take a while
        )

        return ImageInfo(id=image_data.id, name=image_data.display_name)

