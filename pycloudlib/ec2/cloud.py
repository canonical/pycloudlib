# This file is part of pycloudlib. See LICENSE file for license information.
"""AWS EC2 Cloud type."""

import re
from typing import List, Optional

import botocore

from pycloudlib.cloud import BaseCloud, ImageType
from pycloudlib.config import ConfigFile
from pycloudlib.ec2.instance import EC2Instance
from pycloudlib.ec2.util import _get_session, _tag_resource
from pycloudlib.ec2.vpc import VPC
from pycloudlib.errors import (
    CloudSetupError,
    ImageNotFoundError,
    PycloudlibError,
)
from pycloudlib.util import LTS_RELEASES, UBUNTU_RELEASE_VERSION_MAP

# Images before mantic don't have gp3 disk type
NO_GP3_RELEASES = ["xenial", "bionic", "focal", "jammy"]


class EC2(BaseCloud):
    """EC2 Cloud Class."""

    _type = "ec2"

    def __init__(
        self,
        tag: str,
        timestamp_suffix: bool = True,
        config_file: Optional[ConfigFile] = None,
        *,
        access_key_id: Optional[str] = None,
        secret_access_key: Optional[str] = None,
        region: Optional[str] = None,
    ):
        """Initialize the connection to EC2.

        boto3 will read a users /home/$USER/.aws/* files if no
        arguments are provided here to find values.

        Args:
            tag: string used to name and tag resources with
            timestamp_suffix: bool set True to append a timestamp suffix to the
                tag
            config_file: path to pycloudlib configuration file
            access_key_id: user's access key ID
            secret_access_key: user's secret access key
            region: region to login to
        """
        super().__init__(
            tag,
            timestamp_suffix,
            config_file,
            required_values=[access_key_id, secret_access_key, region],
        )
        self._log.debug("logging into EC2")

        try:
            session = _get_session(
                access_key_id or self.config.get("access_key_id"),
                secret_access_key or self.config.get("secret_access_key"),
                region or self.config.get("region"),
            )
            self.client = session.client("ec2")
            self.resource = session.resource("ec2")
            self.region = session.region_name
        except botocore.exceptions.NoRegionError as e:
            raise CloudSetupError(
                "Please configure default region in $HOME/.aws/config"
            ) from e
        except botocore.exceptions.NoCredentialsError as e:
            raise CloudSetupError(
                "Please configure ec2 credentials in $HOME/.aws/credentials"
            ) from e

        self.created_vpcs: List[VPC] = []
        self.created_keys: List[str] = []

    def get_or_create_vpc(self, name, ipv4_cidr="192.168.1.0/20"):
        """Create a or return matching VPC.

        This can be used instead of using the default VPC to create
        a custom VPC for usage.

        Args:
            name: name of the VPC
            ipv4_cidr: CIDR of IPV4 subnet

        Returns:
            VPC object

        """
        # Check to see if current VPC exists
        vpcs = self.client.describe_vpcs(
            Filters=[{"Name": "tag:Name", "Values": [name]}]
        )["Vpcs"]
        if vpcs:
            return VPC.from_existing(self.resource, vpc_id=vpcs[0]["VpcId"])
        new_vpc = VPC.create(self.resource, name=name, ipv4_cidr=ipv4_cidr)
        self.created_vpcs.append(new_vpc)
        return new_vpc

    def released_image(
        self,
        release: str,
        *,
        arch: str = "x86_64",
        image_type: ImageType = ImageType.GENERIC,
        include_deprecated: bool = False,
        **kwargs,
    ):
        """Find the id of the latest released image for a particular release.

        Args:
            release: string, Ubuntu release to look for
            arch: string, architecture to use
            root_store: string, root store to use

        Returns:
            string, id of latest image

        """
        self._log.debug("finding released Ubuntu image for %s", release)
        image = self._find_latest_image(
            release=release,
            arch=arch,
            image_type=image_type,
            daily=False,
            include_deprecated=include_deprecated,
        )
        return image["ImageId"]

    def _get_name_for_image_type(
        self, release: str, image_type: ImageType, daily: bool
    ):
        disk_type = "hvm-ssd" if release in NO_GP3_RELEASES else "hvm-ssd-gp3"
        if image_type in (ImageType.GENERIC, ImageType.MINIMAL):
            base_location = "ubuntu{}/{}/{}".format(
                "-minimal" if image_type == ImageType.MINIMAL else "",
                "images-testing" if daily else "images",
                disk_type,
            )
            if release in LTS_RELEASES:
                return "{}/ubuntu-{}{}-*-{}-*".format(
                    base_location,
                    release,
                    "-daily" if daily else "",
                    "minimal" if image_type == ImageType.MINIMAL else "server",
                )

            return "{}/ubuntu-{}{}-*-{}-*".format(
                base_location,
                release,
                "-daily" if daily else "",
                "minimal" if image_type == ImageType.MINIMAL else "server",
            )

        release_ver = UBUNTU_RELEASE_VERSION_MAP.get(release)
        if image_type == ImageType.PRO:
            return (
                f"ubuntu-pro-server/images/{disk_type}/"
                f"ubuntu-{release}-{release_ver}-*"
            )

        if image_type == ImageType.PRO_FIPS:
            return (
                f"ubuntu-pro-fips*/images/{disk_type}/"
                f"ubuntu-{release}-{release_ver}-*"
            )

        raise ValueError("Invalid image_type")

    def _get_owner(self, image_type: ImageType):
        return (
            "099720109477"
            if image_type
            in (ImageType.GENERIC, ImageType.MINIMAL, ImageType.PRO)
            else "aws-marketplace"
        )

    def _get_search_filters(
        self, release: str, arch: str, image_type: ImageType, daily: bool
    ):
        return [
            {
                "Name": "name",
                "Values": [
                    self._get_name_for_image_type(release, image_type, daily)
                ],
            },
            {
                "Name": "architecture",
                "Values": [arch],
            },
        ]

    def _find_latest_image(
        self,
        release: str,
        arch: str,
        image_type: ImageType,
        daily: bool,
        include_deprecated: bool = False,
    ):
        filters = self._get_search_filters(
            release=release, arch=arch, image_type=image_type, daily=daily
        )
        owner = self._get_owner(image_type=image_type)

        images = self.client.describe_images(
            Owners=[owner],
            Filters=filters,
            IncludeDeprecated=include_deprecated,
        )

        if not images.get("Images"):
            raise ValueError(
                "Could not find {} image for {} release".format(
                    image_type.value, release
                )
            )

        return sorted(images["Images"], key=lambda x: x["CreationDate"])[-1]

    def daily_image(
        self,
        release: str,
        *,
        arch: str = "x86_64",
        image_type: ImageType = ImageType.GENERIC,
        include_deprecated: bool = False,
        **kwargs,
    ):
        """Find the id of the latest daily image for a particular release.

        Args:
            release: string, Ubuntu release to look for
            arch: string, architecture to use

        Returns:
            string, id of latest image

        """
        self._log.debug("finding daily Ubuntu image for %s", release)
        image = self._find_latest_image(
            release=release,
            arch=arch,
            image_type=image_type,
            daily=True,
            include_deprecated=include_deprecated,
        )
        return image["ImageId"]

    def _find_image_serial(
        self, image_id, image_type: ImageType = ImageType.GENERIC
    ):
        owner = self._get_owner(image_type=image_type)
        filters = [
            {
                "Name": "image-id",
                "Values": (image_id,),
            }
        ]

        images = self.client.describe_images(
            Owners=[owner],
            Filters=filters,
        )

        if not images.get("Images"):
            raise ImageNotFoundError(image_id)

        image_name = images["Images"][0].get("Name", "")
        serial_regex = r"ubuntu/.*/.*/.*-(?P<serial>\d+(\.\d+)?)$"
        serial_match = re.match(serial_regex, image_name)

        if not serial_match:
            raise ImageNotFoundError(resource_id=image_id)

        return serial_match.groupdict().get("serial")

    def image_serial(
        self, image_id, image_type: ImageType = ImageType.GENERIC
    ):
        """Find the image serial of a given EC2 image ID.

        Args:
            image_id: string, Ubuntu image id

        Returns:
            string, serial of latest image

        """
        self._log.debug(
            "finding image serial for EC2 Ubuntu image %s", image_id
        )
        return self._find_image_serial(image_id, image_type)

    def delete_image(self, image_id, **kwargs):
        """Delete an image.

        Args:
            image_id: string, id of the image to delete
        """
        image = self.resource.Image(image_id)
        try:
            snapshot_id = image.block_device_mappings[0]["Ebs"]["SnapshotId"]
        except AttributeError:
            return

        self._log.debug("removing custom ami %s", image_id)
        self.client.deregister_image(ImageId=image_id)

        self._log.debug("removing custom snapshot %s", snapshot_id)
        self.client.delete_snapshot(SnapshotId=snapshot_id)

    def delete_key(self, name):
        """Delete an uploaded key.

        Args:
            name: The key name to delete.
        """
        self._log.debug("deleting SSH key %s", name)
        self.client.delete_key_pair(KeyName=name)

    def get_instance(
        self, instance_id, *, username: Optional[str] = None, **kwargs
    ):
        """Get an instance by id.

        Args:
            instance_id: ID used to identify the instance
            username: username to use when connecting via SSH
            **kwargs: dictionary of other arguments to be used by this
                method. Currently unused but provided for base
                class compatibility.

        Returns:
            An instance object to use to manipulate the instance further.

        """
        instance = self.resource.Instance(instance_id)
        return EC2Instance(
            self.key_pair, self.client, instance, username=username
        )

    def launch(
        self,
        image_id,
        instance_type="t3.micro",  # Using nitro instance for IPv6
        user_data=None,
        vpc=None,
        *,
        disk_size_gb: int = 15,
        username: Optional[str] = None,
        enable_ipv6: bool = False,
        **kwargs,
    ):
        """Launch instance on EC2.

        Args:
            image_id: string, AMI ID to use default: latest Ubuntu LTS
            instance_type: string, instance type to launch
            user_data: string, user-data to pass to instance
            vpc: optional vpc object to create instance under
            disk_size_gb: size of instance disk in GB
            username: username to use when connecting via SSH
            enable_ipv6: indicates if ipv6 IMDS support must be added to the
                instance
            kwargs: other named arguments to add to instance JSON

        Returns:
            EC2 Instance object
        Raises: ValueError on invalid image_id
        """
        # pylint: disable=too-many-locals
        if not image_id:
            raise ValueError(
                f"{self._type} launch requires image_id param."
                f" Found: {image_id}"
            )
        args = {
            "ImageId": image_id,
            "InstanceType": instance_type,
            "KeyName": self.key_pair.name,
            "MaxCount": 1,
            "MinCount": 1,
            "TagSpecifications": [
                {
                    "ResourceType": "instance",
                    "Tags": [{"Key": "Name", "Value": self.tag}],
                }
            ],
            "BlockDeviceMappings": [
                {
                    "DeviceName": "/dev/sda1",
                    "Ebs": {
                        "DeleteOnTermination": True,
                        "VolumeSize": disk_size_gb,
                        "VolumeType": "gp3",
                    },
                }
            ],
        }

        if user_data:
            args["UserData"] = user_data

        for key, value in kwargs.items():
            args[key] = value

        if enable_ipv6:
            # Enable IPv6 metadata at http://[fd00:ec2::254]
            if "Ipv6AddressCount" not in args:
                args["Ipv6AddressCount"] = 1
            if "MetadataOptions" not in args:
                args["MetadataOptions"] = {}
            if "HttpProtocolIpv6" not in args["MetadataOptions"]:
                args["MetadataOptions"] = {"HttpProtocolIpv6": "enabled"}

        if vpc:
            try:
                [subnet_id] = [s.id for s in vpc.vpc.subnets.all()]
            except ValueError as e:
                raise PycloudlibError(
                    "Too many subnets in vpc {}. pycloudlib does not support"
                    " launching into VPCs with multiple subnets".format(vpc.id)
                ) from e
            args["SubnetId"] = subnet_id
            args["SecurityGroupIds"] = [
                sg.id for sg in vpc.vpc.security_groups.all()
            ]

        self._log.debug("launching instance")
        instances = self.resource.create_instances(**args)
        instance = EC2Instance(
            self.key_pair, self.client, instances[0], username=username
        )
        self.created_instances.append(instance)

        return instance

    def list_keys(self):
        """List all ssh key pair names loaded on this EC2 region."""
        keypair_names = []
        for keypair in self.client.describe_key_pairs()["KeyPairs"]:
            keypair_names.append(keypair["KeyName"])
        return keypair_names

    def snapshot(self, instance, clean=True):
        """Snapshot an instance and generate an image from it.

        Args:
            instance: Instance to snapshot
            clean: run instance clean method before taking snapshot

        Returns:
            An image id

        """
        if clean:
            instance.clean()

        instance.shutdown(wait=True)

        self._log.debug("creating custom ami from instance %s", instance.id)

        response = self.client.create_image(
            Name="%s-%s" % (self.tag, instance.image_id),
            InstanceId=instance.id,
        )
        image_ami_edited = response["ImageId"]
        image = self.resource.Image(image_ami_edited)
        self.created_images.append(image.id)

        self._wait_for_snapshot(image)
        _tag_resource(image, self.tag)

        instance.start(wait=True)

        return image.id

    def upload_key(self, public_key_path, private_key_path=None, name=None):
        """Use an existing already uploaded key.

        Args:
            public_key_path: path to the public key to upload
            private_key_path: path to the private key to upload
            name: name to reference key by
        """
        self._log.debug("uploading SSH key %s", name)
        self.client.import_key_pair(
            KeyName=name, PublicKeyMaterial=self.key_pair.public_key_content
        )
        self.use_key(public_key_path, private_key_path, name)
        self.created_keys.append(name)

    def use_key(self, public_key_path, private_key_path=None, name=None):
        """Use an existing already uploaded key.

        Args:
            public_key_path: path to the public key to upload
            private_key_path: path to the private key to upload
            name: name to reference key by
        """
        if not name:
            name = self.tag
        super().use_key(public_key_path, private_key_path, name)

    def _wait_for_snapshot(self, image):
        """Wait for snapshot image to be created.

        Args:
            image: image boto3 object to wait to be available
        """
        image.wait_until_exists()
        waiter = self.client.get_waiter("image_available")
        waiter.wait(ImageIds=[image.id])
        image.reload()

    # pylint: disable=broad-except
    def clean(self) -> List[Exception]:
        """Cleanup ALL artifacts associated with this Cloud instance.

        Cleanup any cloud artifacts created at any time during this class's
        existence. This includes all instances, snapshots, resources, etc.
        """
        exceptions = super().clean()
        for vpc in self.created_vpcs:
            try:
                vpc.delete()
            except Exception as e:
                exceptions.append(e)

        for key in self.created_keys:
            try:
                self.delete_key(key)
            except Exception as e:
                exceptions.append(e)
        return exceptions
