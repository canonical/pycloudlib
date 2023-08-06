"""Openstack cloud type."""
import base64
from typing import Optional

import openstack

from pycloudlib.cloud import BaseCloud
from pycloudlib.config import ConfigFile
from pycloudlib.errors import (
    CloudSetupError,
    NetworkNotFoundError,
    PycloudlibError,
)
from pycloudlib.key import KeyPair
from pycloudlib.openstack.errors import OpenStackFlavorNotFound
from pycloudlib.openstack.instance import OpenstackInstance


class Openstack(BaseCloud):
    """Openstack cloud class."""

    _type = "openstack"

    def __init__(
        self,
        tag: str,
        timestamp_suffix: bool = True,
        config_file: Optional[ConfigFile] = None,
        *,
        network: Optional[str] = None,
    ):
        """Initialize the connection to openstack.

        Requires valid pre-configured environment variables or clouds.yaml.
        See https://docs.openstack.org/python-openstackclient/pike/configuration/index.html

        Args:
            tag: Name of instance
            timestamp_suffix: bool set True to append a timestamp suffix to the
                tag
            config_file: path to pycloudlib configuration file
            network: Name of the network to use (from openstack network list)

        """  # noqa: E501
        super().__init__(
            tag, timestamp_suffix, config_file, required_values=[network]
        )

        self.network = network or self.config["network"]
        self._openstack_keypair: Optional[KeyPair] = None
        self.conn = openstack.connect()

    def delete_image(self, image_id, **kwargs):
        """Delete an image.

        Args:
            image_id: string, id of the image to delete
        """
        self.conn.delete_image(image_id, wait=True)

    def released_image(self, release, **kwargs):
        """Not supported for openstack."""
        raise PycloudlibError(
            "Obtaining released image for a release is not supported on "
            "Openstack because we have no guarantee of what images will be "
            "available for any particular openstack setup."
        )

    def daily_image(self, release: str, **kwargs):
        """Not supported for openstack."""
        raise PycloudlibError(
            "Obtaining daily image for a release is not supported on "
            "Openstack because we have no guarantee of what images will be "
            "available for any particular openstack setup."
        )

    def image_serial(self, image_id):
        """Find the image serial of the latest daily image for a particular release.

        Args:
            image_id: string, Ubuntu image id

        Returns:
            string, serial of latest image

        """
        raise NotImplementedError

    def get_instance(
        self, instance_id, *, username: Optional[str] = None, **kwargs
    ) -> OpenstackInstance:
        """Get an instance by id.

        Args:
            instance_id: ID of instance to get

        Returns:
            An instance object to use to manipulate the instance further.

        """
        return OpenstackInstance(
            key_pair=self.key_pair,
            instance_id=instance_id,
            network_id=self._get_network_id(),
            username=username,
        )

    def _get_network_id(self):
        try:
            return self.conn.network.find_network(self.network).id
        except AttributeError as e:
            raise NetworkNotFoundError(resource_name=self.network) from e

    def launch(
        self,
        image_id,
        instance_type="m1.small",
        user_data="",
        *,
        username: Optional[str] = None,
        **kwargs,
    ) -> OpenstackInstance:
        """Launch an instance.

        Args:
            image_id: string, image ID to use for the instance
            instance_type: string, type (flavor) of instance to create
            user_data: used by cloud-init to run custom scripts/configuration
            username: username to use when connecting via SSH
            **kwargs: dictionary of other arguments to pass to launch

        Returns:
            An instance object to use to manipulate the instance further.
        Raises: ValueError on invalid image_id
        """
        if not image_id:
            raise ValueError(
                f"{self._type} launch requires image_id param."
                f" Found: {image_id}"
            )
        network_id = self._get_network_id()
        networks = [{"uuid": network_id}]
        if not self._openstack_keypair:
            self._openstack_keypair = self._get_openstack_keypair()
        if user_data:
            user_data = base64.b64encode(user_data.encode()).decode()
        else:
            user_data = ""

        flavor = self.conn.compute.find_flavor(instance_type)
        if flavor is None:
            raise OpenStackFlavorNotFound(
                "No Openstack flavor found named {}. Please pass a valid "
                "Openstack flavor as the `instance_type` when calling "
                "launch.".format(instance_type)
            )

        instance = self.conn.compute.create_server(
            name=self.tag,
            image_id=image_id,
            flavor_id=flavor.id,
            networks=networks,
            key_name=self._openstack_keypair.name,
            user_data=user_data,
            wait=False,
            **kwargs,
        )
        instance = OpenstackInstance(
            key_pair=self.key_pair,
            instance_id=instance.id,
            network_id=network_id,
            connection=self.conn,
            username=username,
        )
        self.created_instances.append(instance)
        return instance

    def snapshot(self, instance, clean=True, **kwargs):
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
        image = self.conn.create_image_snapshot(
            "{}-snapshot".format(self.tag), instance.server.id, wait=True
        )
        self.created_images.append(image.id)
        return image.id

    def use_key(self, public_key_path, private_key_path=None, name=None):
        """Use an existing key.

        Args:
            public_key_path: path to the public key to upload
            private_key_path: path to the private key
            name: name to reference key by
        """
        super().use_key(public_key_path, private_key_path, name)
        self._openstack_keypair = self._get_openstack_keypair()

    def _get_openstack_keypair(self) -> KeyPair:
        """Get openstack keypair corresponding to this instances keypair.

        When creating an openstack instance, a keypair (maintained in
        openstack) must be created first. This method gets or creates
        the openstack keypair corresponding to the keypair already created
        for this cloud instance.
        """
        name = self.key_pair.name
        public_key_content = self.key_pair.public_key_content

        openstack_keypair = self.conn.get_keypair(name)
        if not openstack_keypair:
            # If the openstack keypair doesn't exist, create it
            return self.conn.create_keypair(name, public_key_content)
        if public_key_content == openstack_keypair.public_key:
            return openstack_keypair
        raise CloudSetupError(
            "An openstack keypair with name {name} already exists, but its"
            " public key doesn't match the public key passed in.\n"
            "{name} key: {openstack_key}\n"
            "Passed in key: {passed_key}".format(
                name=name,
                openstack_key=openstack_keypair.public_key,
                passed_key=public_key_content,
            )
        )
