# This file is part of pycloudlib. See LICENSE file for license information.
"""GCP Cloud type.

Utilizes the Compute Engine API:

https://developers.google.com/resources/api-libraries/documentation/compute/v1/python/latest/
https://developers.google.com/apis-explorer/#p/compute/v1/
"""

import googleapiclient

from pycloudlib.base_cloud import BaseCloud
from pycloudlib.gcp.instance import GCEInstance
from pycloudlib.key import KeyPair
from pycloudlib.streams import Streams


class GCP(BaseCloud):
    """GCP Cloud Class."""

    def __init__(self, access_key_id=None, secret_access_key=None,
                 region=None, tag=None):
        """Initialize the connection to GCP.

        Args:
            access_key_id: user's access key ID
            secret_access_key: user's secret access key
            region: region to login to
        """
        super().__init__()
        self._log.debug('logging into GCE')

        compute = googleapiclient.discovery.build('compute', 'v1')

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
        pass

    def delete_image(self, image_id):
        """Delete an image.

        Args:
            image_id: string, id of the image to delete
        """
        pass

    def delete_key(self, name):
        """Delete an uploaded key.

        Args:
            name: The key name to delete.
        """
        self._log.debug('deleting SSH key %s', name)
        pass

    def get_instance(self, instance_id):
        """Get an instance by id.

        Args:
            instance_id:

        Returns:
            An instance object to use to manipulate the instance further.

        """
        pass

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
        pass

    def snapshot(self, instance, clean=True):
        """Snapshot an instance and generate an image from it.

        Args:
            instance: Instance to snapshot
            clean: run instance clean method before taking snapshot
            wait: wait for instance to get created

        Returns:
            An image object

        """
        pass

    def upload_key(self, name, public_key_path):
        """Upload and use a specific public key.

        Args:
            name: name to reference key by
            public_key_path: path to the public key to upload
        """
        self._log.debug('uploading SSH key %s', name)
        pass

    def use_key(self, name, public_key_path):
        """Use an existing already uploaded key.

        Args:
            name: name to reference key by
            public_key_path: path to the public key to upload
        """
        self._log.debug('using SSH key %s', name)
        pass