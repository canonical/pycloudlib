# This file is part of pycloudlib. See LICENSE file for license information.
"""IBM Cloud type."""

import re
from typing import List, Literal, Optional, Tuple

import SoftLayer  # type: ignore

from pycloudlib.cloud import BaseCloud
from pycloudlib.config import ConfigFile
from pycloudlib.errors import InvalidTagNameError
from pycloudlib.ibm_classic.errors import IBMClassicException
from pycloudlib.ibm_classic.instance import IBMClassicInstance
from pycloudlib.instance import BaseInstance


class IBMClassic(BaseCloud):
    """IBM Classic Class."""

    _type = "ibm_classic"

    def __init__(
        self,
        tag: str,
        timestamp_suffix: bool = True,
        config_file: Optional[ConfigFile] = None,
        *,
        username: Optional[str] = None,
        api_key: Optional[str] = None,
        domain_name: Optional[str] = None,
    ):
        """Initialize base cloud class.

        Args:
            tag: string used to name and tag resources with
            timestamp_suffix: Append a timestamped suffix to the tag string.
            config_file: path to pycloudlib configuration file
            username: IBM Classic specific username for API
            api_key: IBM Classic specific API key
            domain_name: Domain name to use for creating instance FQDNs
        """
        super().__init__(
            tag,
            timestamp_suffix,
            config_file,
            required_values=[username, api_key, domain_name],
        )
        self.created_keys: List[str] = []
        self.created_security_groups: list = []

        self._username = username or self.config.get("username")
        self._api_key = api_key or self.config.get("api_key")
        self._domain_name = domain_name or self.config.get("domain_name")

        self._log.debug("logging into IBM")

        if not self._username or not self._api_key:
            raise IBMClassicException(
                "IBM Classic requires a username and API key"
            )

        self._client = SoftLayer.create_client_from_env(
            username=self._username,
            api_key=self._api_key,
        )
        self._virtual_server_manager = SoftLayer.VSManager(client=self._client)
        self._image_manager = SoftLayer.ImageManager(client=self._client)
        self._ssh_key_manager = SoftLayer.SshKeyManager(client=self._client)
        self._network_manager = SoftLayer.NetworkManager(client=self._client)

    def delete_image(self, image_id: str, **kwargs):
        """Delete an image.

        Args:
            image_id: string, ID (not GID) of the image to delete.
        """
        try:
            self._image_manager.delete_image(int(image_id))
        except ValueError as e:
            raise IBMClassicException(
                "Invalid image ID provided. Image ID must be an integer. "
                "Please provide the image ID, not the global identifier."
            ) from e
        except SoftLayer.SoftLayerAPIError as e:
            raise IBMClassicException(
                f"Error deleting image {image_id}"
            ) from e

    def released_image(self, release, *, disk_size: str = "25G", **kwargs):
        """ID (globalIdentifier) of the latest released image for a particular release.

        Args:
            release: The release to look for

        Returns:
            A single string with the latest released image ID for the
            specified release.

        """
        public_images_gen = self._image_manager.list_public_images(
            name=f"*{release}*"
        )
        public_images = list(public_images_gen)
        if not public_images:
            raise IBMClassicException(f"No public images found for {release}")
        # filter by disk size
        public_images = [
            image
            for image in public_images
            if str(image["name"]).startswith(disk_size)
        ]
        # sort by "createDate" so newest image is first
        public_images.sort(key=lambda x: x["createDate"], reverse=True)
        return public_images[0]["globalIdentifier"]

    def daily_image(self, release: str, **kwargs):
        """ID of the latest daily image for a particular release.

        Args:
            release: The release to look for

        Returns:
            A single string with the latest daily image ID for the
            specified release.

        """
        self._log.info(
            "There are no daily images in IBM Cloud."
            " Using released image instead."
        )
        return self.released_image(release, **kwargs)

    def image_serial(self, image_id):
        """Find the image serial of the latest daily image for a particular release.

        Args:
            image_id: string, Ubuntu image id

        Returns:
            string, serial of latest image

        """
        raise IBMClassicException("This is not a valid method for IBM Classic")

    def get_image_id_from_name(self, name: str) -> str:
        """
        Get the id of the first image whose name contains the given name.

        The name does not need to be an exact match, just a substring of
        the image name.

        Args:
            name: string, name of the image to search for

        Returns:
            string, image ID
        """
        private_images_gen = self._image_manager.list_private_images(
            name=f"*{name}*"
        )
        private_images = list(private_images_gen)
        if not private_images:
            raise IBMClassicException(f"No private images found for {name}")
        return private_images[0]["globalIdentifier"]

    def get_instance(self, instance_id, **kwargs) -> BaseInstance:
        """Get an instance by id.

        Args:
            instance_id: ID identifying the instance

        Returns:
            An instance object to use to manipulate the instance further.

        """
        instances = set(self._virtual_server_manager.list_instances())
        matches = [i for i in instances if str(i["id"]) == str(instance_id)]
        if not matches:
            raise IBMClassicException(
                f"Error getting IBM Classic instance by id. "
                f"Instance {instance_id} not found"
            )
        if len(matches) > 1:
            raise IBMClassicException(
                f"Error getting IBM Classic instance by id. "
                f"Multiple instances found for {instance_id}"
            )
        return matches[0]

    def _get_datacenter(self, region: str) -> str:
        """Get a datacenter via the specified region prefix."""
        # select one of the datacenters in the region
        datacenters = self._network_manager.get_list_datacenter()
        for datacenter in datacenters:
            if datacenter["name"].startswith(region):
                return datacenter["name"]
        raise IBMClassicException(
            f"Invalid datacenter region provided: {region}"
        )

    # pylint: disable=too-many-locals
    def launch(
        self,
        image_id,
        instance_type: str = "B1_2X4",
        user_data=None,
        *,
        name: Optional[str] = None,
        disk_size: Literal["25G", "100G"] = "25G",
        datacenter_region: str = "dal",
        datacenter: Optional[str] = None,
        **kwargs,
    ) -> BaseInstance:
        """Launch an instance.

        Args:
            name: name of the instance
            image_id: image ID to use for the instance. Can accept
              either an ID or a GID.
            instance_type: type of instance to create. This value is
            combined with the disk_size to create the instance flavor. For
            example, B1_2X4 with disk_size of 25G would result in "B1_2X4X25".
            user_data: cloud-init user data to pass to the instance
            datacenter_region: region to launch the instance in.
              This will automatically select a datacenter in the region if
              "datacenter" is not provided.
            datacenter: datacenter to launch the instance in. If not
              provided, "datacenter_region" will be used. If both are provided,
              "datacenter" will be used.
            **kwargs: dictionary of other arguments to pass to launch

        Returns:
            An instance object to use to manipulate the instance further.

        """
        self._log.info("Preparing to launch instance")
        if disk_size not in ["25G", "100G"]:
            raise IBMClassicException(
                "Invalid disk_size given. "
                "disk_size must be either '25G' or '100G'"
            )

        # check if image_id is a GID by checking if it contains hyphens
        if "-" in image_id:
            image_gid = image_id
        else:
            image_gid = self._image_manager.get_image(image_id)[
                "globalIdentifier"
            ]

        (
            public_security_group_id,
            private_security_group_id,
        ) = self.create_default_security_groups()

        if not (
            instance_type.endswith("X25") or instance_type.endswith("X100")
        ):
            flavor = (
                instance_type.replace("-", "_")
                + "X"
                + disk_size.replace("G", "")
            ).upper()
        else:
            flavor = instance_type.replace("-", "_")

        raw_instance = IBMClassicInstance.create_raw_instance(
            self._virtual_server_manager,
            target_image_global_identifier=image_gid,
            hostname=name or f"{self.tag}-vm",
            flavor=flavor,
            datacenter=datacenter or self._get_datacenter(datacenter_region),
            public_security_group_ids=[public_security_group_id],
            private_security_group_ids=[private_security_group_id],
            ssh_key_ids=[self._get_or_create_key()],
            domain_name=self._domain_name or "pycloudlib.cloud",
            userdata=user_data,
            **kwargs,
        )

        instance = IBMClassicInstance(
            key_pair=self.key_pair,
            softlayer_client=self._client,
            vs_manager=self._virtual_server_manager,
            instance=raw_instance,
        )

        self.created_instances.append(instance)

        return instance

    def snapshot(
        self,
        instance,
        clean=True,
        note: Optional[str] = None,
        **kwargs,
    ):
        """Snapshot an instance and generate an image from it.

        Args:
            instance: Instance to snapshot
            clean: run instance clean method before taking snapshot
            note: optional note to add to the snapshot

        Returns:
            An image id

        """
        if clean:
            instance.clean()

        snapshot_result = self._virtual_server_manager.capture(
            instance_id=instance.id,
            name=f"{self.tag}-snapshot",
            notes=note,
        )
        self._log.info(
            "Successfully created snapshot '%s' with ID: %s",
            snapshot_result["name"],
            snapshot_result["id"],
        )
        return snapshot_result["id"]

    def list_keys(self):
        """List ssh key names present on the cloud for accessing instances.

        Returns:
           A list of strings of key pair names accessible to the cloud.

        """
        return [key["label"] for key in self._ssh_key_manager.list_keys()]

    def _get_or_create_key(self) -> int:
        """Get or create an SSH key."""
        key_pairs = self._ssh_key_manager.list_keys()
        for key_pair in key_pairs:
            if key_pair["label"] == self.key_pair.name:
                self._log.debug(
                    "Key pair with name %s already exists: %s",
                    key_pair["label"],
                    key_pair["id"],
                )
                return key_pair["id"]

        self._log.info("Creating SSH key: %s", self.key_pair.name)
        new_ssh_key = self._ssh_key_manager.add_key(
            key=self.key_pair.public_key_content,
            label=self.key_pair.name,
            notes="Added by pycloudlib",
        )
        key_id = new_ssh_key["id"]
        self._log.debug("Created SSH key with id: %s", key_id)
        self.created_keys.append(key_id)
        return key_id

    def delete_key(self, name: str):
        """Delete SSH key by name."""
        target_key = None
        for key in self._ssh_key_manager.list_keys():
            if key["label"] == name:
                target_key = key
                break
        if target_key is None:
            raise IBMClassicException(f"Key with name {name} not found")
        self._log.debug("Deleting SSH key: %s", name)
        self._ssh_key_manager.delete_key(target_key["id"])

    def create_default_security_groups(self) -> Tuple[int, int]:
        """
        Create default security groups.

        To make this extensible for all users, security groups and rules are
        created on the fly. A unique security group is created for each
        instance so that it can be torn down later without affecting other
        instances. The security group is named after the instance tag. The
        public security group allows inbound ssh traffic and all outbound
        traffic. The private security group allows all inbound and outbound
        traffic.

        Returns:
            A Tuple containing the IDs of the two created security groups
            in the order (public, private).
        """
        self._log.info("Creating default security groups")
        public_security_group_id = self._create_security_group(
            self.tag + "-public-security-group",
            "Allows ssh inbound and all outbound traffic",
        )
        private_security_group_id = self._create_security_group(
            self.tag + "-private-security-group",
            "Allows all inbound and outbound traffic",
        )
        # allow inbound ssh for public security group
        self._add_rules_to_security_group(
            public_security_group_id,
            ["ingress"],
            port=22,
            protocol="tcp",
            ipv6=True,
        )
        # allow all outbound traffic for public security group
        self._add_rules_to_security_group(
            public_security_group_id,
            ["egress"],
            port=None,
            protocol=None,
            ipv6=True,
        )
        # allow all inbound and outbound traffic for private security group
        self._add_rules_to_security_group(
            private_security_group_id,
            ["ingress", "egress"],
            port=None,
            protocol=None,
            ipv6=True,
        )
        self._log.debug("Added rules to security groups.")
        return public_security_group_id, private_security_group_id

    def _create_security_group(self, name: str, description: str) -> int:
        """
        Create a security group.

        Args:
            name: The name of the security group.
            description: The description of the security group.

        Returns:
            int: The ID of the created security group.
        """
        new_group = self._network_manager.create_securitygroup(
            name, description
        )
        self.created_security_groups.append(new_group["id"])
        self._log.debug(
            "Created new security group %s: %s", name, new_group["id"]
        )
        return new_group["id"]

    def _add_rules_to_security_group(
        self,
        group_id: int,
        directions: List[str],
        ipv6: bool = False,
        port: Optional[int] = None,
        protocol: Optional[str] = None,
    ):
        """
        Add rules to a security group.

        Args:
            group_id: The ID of the security group.
            directions: Allow ingress or egress traffic.
            ipv6: Flag indicating whether to add rules for IPv6.
            Defaults to False.
            port: The port number for the rule. Defaults to
            None.
            protocol: The protocol for the rule. Defaults to
            None.
        """
        ethertypes = ["IPv4", "IPv6"] if ipv6 else ["IPv4"]

        for direction in directions:
            if direction not in ["ingress", "egress"]:
                raise ValueError(
                    f"Invalid direction: {direction}. "
                    "Must be 'ingress' or 'egress'."
                )
            for ethertype in ethertypes:
                self._network_manager.add_securitygroup_rule(
                    group_id=group_id,
                    ethertype=ethertype,
                    direction=direction,
                    protocol=protocol,
                    port_min=port,
                    port_max=port,
                )
                self._log.debug(
                    "Added rule allowing %s %s traffic on port %s"
                    "to security group %s",
                    ethertype,
                    direction,
                    port,
                    group_id,
                )

    # pylint: disable=broad-except
    def clean(self) -> List[Exception]:
        """Cleanup ALL artifacts associated with this Cloud instance.

        Cleanup any cloud artifacts created at any time during this class's
        existence. This includes all instances, snapshots, resources, etc.

        Returns:
            A list of exceptions that occurred during cleanup.
        """
        self._log.info("Cleaning up IBM Classic and all associated resources")
        exceptions = super().clean()
        self._log.info("Cleaning up SSH keys")
        for key_id in self.created_keys:
            try:
                self._ssh_key_manager.delete_key(key_id)
            except Exception as e:
                exceptions.append(e)
        self._log.info("Cleaning up security groups")
        for security_group_id in self.created_security_groups:
            try:
                self._network_manager.delete_securitygroup(security_group_id)
            except Exception as e:
                exceptions.append(e)
        return exceptions

    @staticmethod
    def _validate_tag(tag: str):
        """
        Ensure that this tag is a valid name for IBM Cloud Classic Infrastructure resources.

        Rules:
        - All letters must be lowercase
        - Must be between 1 and 63 characters long
        - Must not start or end with a hyphen or period
        - Must be alphanumeric, periods, and hyphens only
        - Must not contain only numbers

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
        # must not start or end with a hyphen or
        if tag and (tag[0] in ("-", ".") or tag[-1] in ("-", ".")):
            rules_failed.append(
                "Must not start or end with a hyphen or period"
            )
        # must be alphanumeric, periods, and hyphens only
        if not re.match(r"^[a-z0-9.-]+$", tag):
            rules_failed.append(
                "Must be alphanumeric, periods, and hyphens only"
            )
        # must not contain only numbers
        if tag.isdigit():
            rules_failed.append("Must not contain only numbers")

        if rules_failed:
            raise InvalidTagNameError(tag=tag, rules_failed=rules_failed)
