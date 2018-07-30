# This file is part of pycloudlib. See LICENSE file for license information.
"""AWS EC2 Cloud type."""

import datetime

import botocore

from pycloudlib.base_cloud import BaseCloud
from pycloudlib.ec2.instance import EC2Instance
from pycloudlib.ec2.util import _get_session
from pycloudlib.ec2.vpc import VPC
from pycloudlib.exceptions import (
    NoKeyPairConfiguredError,
    PlatformError
)
from pycloudlib.key import KeyPair
from pycloudlib.streams import Streams


class EC2(BaseCloud):
    """EC2 Cloud Class."""

    def __init__(self, access_key_id=None, secret_access_key=None,
                 region=None, tag=None):
        """Initialize the connection to EC2.

        boto3 will read a users /home/$USER/.aws/* files if no
        arguments are provided here to find values.

        Args:
            access_key_id: user's access key ID
            secret_access_key: user's secret access key
            region: region to login to
        """
        super(EC2, self).__init__()
        self._log.debug('logging into EC2')

        try:
            session = _get_session(access_key_id, secret_access_key, region)
            self.client = session.client('ec2')
            self.resource = session.resource('ec2')
            self.region = session.region_name
        except botocore.exceptions.NoRegionError:
            raise RuntimeError(
                'Please configure default region in $HOME/.aws/config')
        except botocore.exceptions.NoCredentialsError:
            raise RuntimeError(
                'Please configure ec2 credentials in $HOME/.aws/credentials')

        self.key_pair = None
        self.tag = tag
        if not tag:
            self.tag = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    def create_vpc(self, name, ipv4_cidr='192.168.1.0/20'):
        """Create a custom VPC.

        This can be used instead of using the default VPC to create
        a custom VPC for usage.

        Args:
            name: name of the VPC
            ipv4_cidr: CIDR of IPV4 subnet

        Returns:
            VPC object

        """
        return VPC(self.resource, name, ipv4_cidr)

    def daily_image(self, release, arch='amd64', root_store='ssd'):
        """Find the id of the latest image for a particular release.

        Args:
            release: string, Ubuntu release to look for
            arch: string, architecture to use
            root_store: string, root store to use

        Returns:
            string, id of latest image

        """
        self._log.debug('finding daily image for %s', release)
        images = self._image_list(release, arch, root_store)
        return images[0]['id']

    def delete_image(self, image_id):
        """Delete an image.

        Args:
            image_id: string, id of the image to delete
        """
        image = self.resource.Image(image_id)
        snapshot_id = image.block_device_mappings[0]['Ebs']['SnapshotId']

        self._log.debug('removing custom ami %s', image_id)
        self.client.deregister_image(ImageId=image_id)

        self._log.debug('removing custom snapshot %s', snapshot_id)
        self.client.delete_snapshot(SnapshotId=snapshot_id)

    def delete_key(self, name):
        """Delete an uploaded key.

        Args:
            name: The key name to delete.
        """
        self._log.debug('deleting SSH key %s', name)
        self.client.delete_key_pair(KeyName=name)

    def get_instance(self, instance_id):
        """Get an instance by id.

        Args:
            instance_id:

        Returns:
            An instance object to use to manipulate the instance further.

        """
        instance = self.resource.Instance(instance_id)
        return EC2Instance(self.client, self.key_pair, instance)

    def launch(self, image_id, instance_type='t2.micro', user_data=None,
               vpc=None, wait=True, **kwargs):
        """Launch instance on EC2.

        Args:
            image_id: string, AMI ID for instance to use
            instance_type: string, instance type to launch
            user_data: string, user-data to pass to instance
            vpc: optional vpc object to create instance under
            wait: boolean, wait for instance to come up
            kwargs: other named arguments to add to instance JSON

        Returns:
            EC2 Instance object

        """
        if not self.key_pair:
            raise NoKeyPairConfiguredError

        args = {
            'ImageId': image_id,
            'InstanceType': instance_type,
            'KeyName': self.key_pair.name,
            'MaxCount': 1,
            'MinCount': 1,
            'TagSpecifications': [{
                'ResourceType': 'instance',
                'Tags': [{'Key': 'Name', 'Value': self.tag}]
            }],
        }

        if user_data:
            args['UserData'] = user_data

        for key, value in kwargs.items():
            args[key] = value

        if vpc:
            args['SecurityGroupIds'] = [vpc.security_group.id]
            args['SubnetId'] = vpc.subnet.id

        self._log.debug('launching instance')
        try:
            instances = self.resource.create_instances(**args)
        except botocore.exceptions.ClientError as error:
            error_msg = error.response['Error']['Message']
            raise PlatformError('start', error_msg)

        instance = EC2Instance(self.client, self.key_pair, instances[0])

        if wait:
            instance.wait()

        return instance

    def snapshot(self, instance, clean=True):
        """Snapshot an instance and generate an image from it.

        Args:
            instance: Instance to snapshot
            clean: run instance clean method before taking snapshot
            wait: wait for instance to get created

        Returns:
            An image object

        """
        if clean:
            instance.clean()

        instance.shutdown(wait=True)

        self._log.debug(
            'creating custom ami from instance %s', instance.id
        )

        response = self.client.create_image(
            Name='%s-%s' % (self.tag, instance.image_id),
            InstanceId=instance.id
        )
        image_ami_edited = response['ImageId']
        image = self.resource.Image(image_ami_edited)

        self._wait_for_snapshot(image)

        instance.start(wait=True)

        return image.id

    def upload_key(self, name, public_key_path):
        """Upload and use a specific public key.

        Args:
            name: name to reference key by
            public_key_path: path to the public key to upload
        """
        self._log.debug('uploading SSH key %s', name)
        self.client.import_key_pair(
            KeyName=name, PublicKeyMaterial=self.key_pair.public_key_content
        )
        self.use_key(name, public_key_path)

    def use_key(self, name, public_key_path):
        """Use an existing already uploaded key.

        Args:
            name: name to reference key by
            public_key_path: path to the public key to upload
        """
        self._log.debug('using SSH key %s', name)
        self.key_pair = KeyPair(name, public_key_path)

    def _image_list(self, release, arch='amd64', root_store='ssd'):
        """Find list of images with a filter.

        Args:
            release: string, Ubuntu release to look for
            arch: string, architecture to use
            root_store: string, root store to use
            latest: default false, boolean to only return latest image

        Returns:
            list of dictionaries of images

        """
        filters = [
            'arch=%s' % arch,
            'endpoint=%s' % 'https://ec2.%s.amazonaws.com' % self.region,
            'region=%s' % self.region,
            'release=%s' % release,
            'root_store=%s' % root_store,
            'virt=hvm',
        ]

        stream = Streams(
            'https://cloud-images.ubuntu.com/daily',
            '/usr/share/keyrings/ubuntu-cloudimage-keyring.gpg'
        )
        return stream.query(filters)

    def _wait_for_snapshot(self, image):
        """Wait for snapshot image to be created.

        Args:
            snapshot_id: snapshot ID to wait to be available
        """
        image.wait_until_exists()
        waiter = self.client.get_waiter('image_available')
        waiter.wait(ImageIds=[image.id])
        image.reload()
