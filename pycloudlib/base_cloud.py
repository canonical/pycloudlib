# This file is part of pycloudlib. See LICENSE file for license information.
"""Base class for all other clouds to provide consistent set of functions."""

import logging


class BaseCloud(object):
    """Base Cloud Class."""

    def __init__(self):
        """Initialize base cloud class."""
        self._log = logging.getLogger(__name__)

        self.key_pair = None

    def delete_image(self, image_id):
        """Delete an image.

        Args:
            image_id: string, id of the image to delete
        """
        raise NotImplementedError

    def delete_key(self, name):
        """Delete an uploaded key.

        Args:
            name: The key name to delete.
        """
        raise NotImplementedError

    def daily_image(self, release):
        """ID of the latest image for a particular release.

        Args:
            release: The release to look for

        Returns:
            A single string with the latest image ID for the specified release

        """
        raise NotImplementedError

    def get_instance(self, instance_id):
        """Get an instance by id.

        Args:
            instance_id:

        Returns:
            An instance object to use to manipulate the instance further.

        """
        raise NotImplementedError

    def launch(self, instance_type, image_id, wait=False, **kwargs):
        """Launch an instance.

        Args:
            instance_type: string, type of instance to create
            image_id: string, image ID to use for the instance
            wait: wait for instance to be live
            **kwargs: dictionary of other arguments to pass to launch

        Returns:
            An instance object to use to manipulate the instance further.

        """
        raise NotImplementedError

    def snapshot(self, instance_id, clean=True, wait=True):
        """Snapshot an instance and generate an image from it.

        Args:
            instance: Instance to snapshot
            clean: run instance clean method before taking snapshot
            wait: wait for instance to get created

        Returns:
            An image object

        """
        raise NotImplementedError

    def upload_key(self, public_key_path=None):
        """Upload and use a specific public key.

        Args:
            name: name to reference key by
            public_key_path: path to the public key to upload
        """
        raise NotImplementedError

    def use_key(self, name, public_key_path):
        """Use an existing already uploaded key.

        Args:
            name: name to reference key by
            public_key_path: path to the public key to upload
        """
        raise NotImplementedError
