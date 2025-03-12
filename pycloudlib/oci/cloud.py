# pylint: disable=E1101
# This file is part of pycloudlib. See LICENSE file for license information.
"""OCI Cloud type."""

import base64
import json
import os
import re
from typing import List, Optional, cast

import oci

from pycloudlib.cloud import BaseCloud
from pycloudlib.config import ConfigFile
from pycloudlib.errors import (
    CloudSetupError,
    InstanceNotFoundError,
    InvalidTagNameError,
    PycloudlibException,
)
from pycloudlib.oci.instance import OciInstance
from pycloudlib.oci.utils import (
    generate_create_vnic_details,
    get_subnet_id,
    get_subnet_id_by_name,
    parse_oci_config_from_env_vars,
    wait_till_ready,
)
from pycloudlib.types import NetworkingConfig
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
            required_values=[availability_domain, compartment_id, vcn_name],
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

        config_dict = config_dict or parse_oci_config_from_env_vars()
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

        self.vcn_name = vcn_name or self.config.get("vcn_name")
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
        self._record_image_deletion(image_id)

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
            vcn_name=self.vcn_name,
        )

    def launch(
        self,
        image_id,
        instance_type="VM.Standard2.1",
        user_data=None,
        *,
        retry_strategy=None,
        username: Optional[str] = None,
        cluster_id: Optional[str] = None,
        subnet_name: Optional[str] = None,
        primary_network_config: Optional[NetworkingConfig] = None,
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
            subnet_name: string, name of subnet to use for instance.
            primary_network_config: NetworkingConfig object to use for configuring the primary
                network interface
            **kwargs: dictionary of other arguments to pass as
                LaunchInstanceDetails

        Returns:
            An instance object to use to manipulate the instance further.
        Raises: ValueError on invalid image_id
        """
        if not image_id:
            raise ValueError(f"{self._type} launch requires image_id param. Found: {image_id}")

        if subnet_name:
            subnet_id = get_subnet_id_by_name(self.network_client, self.compartment_id, subnet_name)
        else:
            subnet_id = get_subnet_id(
                self.network_client,
                self.compartment_id,
                self.availability_domain,
                vcn_name=self.vcn_name,
                networking_config=primary_network_config,
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
            compute_cluster_id=cluster_id,
            create_vnic_details=generate_create_vnic_details(
                subnet_id=subnet_id,
                networking_config=primary_network_config,
            ),
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

    def find_compatible_subnet(self, networking_config: NetworkingConfig) -> str:
        """
        Automatically select a subnet that is compatible with the given networking_config.

        In this case, compatible means that the subnet can support the necessary networking type
        (ipv4 only, ipv6 only, or dual stack) and the private or public requirement.
        This method will select the first subnet that matches the criteria.

        Args:
            networking_config: NetworkingConfig object to use for finding a subnet

        Returns:
            id of the subnet selected

        Raises:
            `PycloudlibError` if unable to determine `subnet_id` for the given `networking_config`
        """
        subnet_id = get_subnet_id(
            network_client=self.network_client,
            compartment_id=self.compartment_id,
            availability_domain=self.availability_domain,
            vcn_name=self.vcn_name,
            networking_config=networking_config,
        )
        return subnet_id

    def snapshot(self, instance, *, clean=True, keep=False, name=None):
        """Snapshot an instance and generate an image from it.

        Args:
            instance: Instance to snapshot
            clean: run instance clean method before taking snapshot
            keep: Keep the image after the cloud instance is cleaned up
            name: Name of created image

        Returns:
            The image id of the snapshot
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

        self._store_snapshot_info(
            snapshot_name=image_data.display_name,
            snapshot_id=image_data.id,
            keep_snapshot=keep,
        )

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

    def create_compute_cluster(
        self,
        image_id: str,
        instance_count: int = 2,
        instance_type: str = "BM.Optimized3.36",
        optional_launch_kwargs: Optional[dict] = None,
        wait: bool = True,
    ) -> List[OciInstance]:
        """
        Create a compute cluster with a specified number of instances.

        Args:
            instance_count: Number of instances to create
            launch_kwargs: Additional arguments to pass to the launch method

        Returns:
            List of OciInstance objects that were created
        """
        cluster_id = self._init_empty_cluster()
        instances: List[OciInstance] = []
        if optional_launch_kwargs:
            image_id = optional_launch_kwargs.pop("image_id", image_id)
            instance_type = optional_launch_kwargs.pop("instance_type", instance_type)

        # launch instances and attach them to the cluster
        for _ in range(instance_count):
            instance = self.launch(
                image_id=image_id,
                instance_type=instance_type,
                **(optional_launch_kwargs or {}),
                cluster_id=cluster_id,
            )
            instances.append(instance)
        if wait:
            for instance in instances:
                instance.wait()
        return instances

    def _init_empty_cluster(self) -> str:
        """
        Create an empty cluster and return the cluster id.

        Returns:
            str: The id of the created compute cluster.
        """
        create_compute_cluster_response = self.compute_client.create_compute_cluster(
            create_compute_cluster_details=oci.core.models.CreateComputeClusterDetails(
                availability_domain=self.availability_domain,
                compartment_id=self.compartment_id,
                display_name=f"{self.tag}-compute-cluster",
            )
        )
        return create_compute_cluster_response.data.id
