"""Openstack cloud type."""
import base64

import openstack

from pycloudlib.cloud import BaseCloud
from pycloudlib.openstack.instance import OpenstackInstance


class Openstack(BaseCloud):
    """Openstack cloud class."""

    _type = 'openstack'

    def __init__(self, tag, network, timestamp_suffix=True):
        """Initialize the connection to openstack.

        Requires valid pre-configured environment variables or clouds.yaml.
        See https://docs.openstack.org/python-openstackclient/pike/configuration/index.html

        Args:
            tag: Name of instance
            network: Name of the network to use (from openstack network list)
            timestamp_suffix: bool set True to append a timestamp suffix to the
                tag
        """  # noqa: E501
        super().__init__(tag, timestamp_suffix)
        self.network = network
        self._openstack_keypair = None
        self.conn = openstack.connect()

    def delete_image(self, image_id):
        """Delete an image.

        Args:
            image_id: string, id of the image to delete
        """
        self.conn.delete_image(image_id, wait=True)

    def released_image(self, release, **kwargs):
        """Not supported for openstack."""
        raise Exception(
            'Obtaining released image for a release is not supported on '
            'Openstack because we have no guarantee of what images will be '
            'available for any particular openstack setup.'
        )

    def daily_image(self, release, **kwargs):
        """Not supported for openstack."""
        raise Exception(
            'Obtaining daily image for a release is not supported on '
            'Openstack because we have no guarantee of what images will be '
            'available for any particular openstack setup.'
        )

    def image_serial(self, image_id):
        """Find the image serial of the latest daily image for a particular release.

        Args:
            image_id: string, Ubuntu image id

        Returns:
            string, serial of latest image

        """
        raise NotImplementedError

    def get_instance(self, instance_id) -> OpenstackInstance:
        """Get an instance by id.

        Args:
            instance_id:

        Returns:
            An instance object to use to manipulate the instance further.

        """
        return OpenstackInstance(
            self.key_pair,
            instance_id,
        )

    def launch(self, image_id, instance_type='m1.small', user_data=None,
               wait=True, **kwargs) -> OpenstackInstance:
        """Launch an instance.

        Args:
            image_id: string, image ID to use for the instance
            instance_type: string, type (flavor) of instance to create
            user_data: used by cloud-init to run custom scripts/configuration
            wait: wait for instance to be live
            **kwargs: dictionary of other arguments to pass to launch

        Returns:
            An instance object to use to manipulate the instance further.

        """
        net = self.conn.network.find_network(self.network)
        networks = [{'uuid': net.id}]
        if not self._openstack_keypair:
            self._openstack_keypair = self._get_openstack_keypair()
        instance = self.conn.compute.create_server(
            name=self.tag,
            image_id=image_id,
            flavor_id=self.conn.compute.find_flavor(instance_type).id,
            networks=networks,
            key_name=self._openstack_keypair.name,
            user_data=base64.b64encode(user_data.encode()).decode(),
            wait=wait,
            **kwargs,
        )
        instance = OpenstackInstance(
            self.key_pair,
            instance.id,
            self.conn
        )
        if wait:
            instance.wait()
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
        self.conn.create_image_snapshot(
            '{}-snapshot'.format(self.tag),
            instance.server.id,
            wait=True
        )

    def use_key(self, public_key_path, private_key_path=None, name=None):
        """Use an existing key.

        Args:
            public_key_path: path to the public key to upload
            private_key_path: path to the private key
            name: name to reference key by
        """
        super().use_key(public_key_path, private_key_path, name)
        self._openstack_keypair = self._get_openstack_keypair()

    def _get_openstack_keypair(self):
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
            return self.conn.create_keypair(
                name,
                public_key_content
            )
        elif public_key_content == openstack_keypair.public_key:
            return openstack_keypair
        else:
            raise Exception(
                "An openstack keypair with name {name} already exists, "
                "but its public key doesn't match the public key passed "
                "in.\n"
                "{name} key: {openstack_key}\n"
                "Passed in key: {passed_key}".format(
                    name=name,
                    openstack_key=openstack_keypair.public_key,
                    passed_key=public_key_content
                )
            )
        # TODO: Figure out if I want to incorporate this...
        # If you don't specify a keypair to pycloudlib, the default keypair
        # uses your username as the default name. It's possible somebody
        # already created an openstack keypair with their username, but
        # using a public key that isn't ~/.ssh/id_rsa.pub. In that case,
        # they'll hit the exception we raise above. Is that case likely /
        # do we care about it? Meh...?

        # # First check to see if we already have this public key under
        # # an existing name
        # openstack_keypairs = self.conn.list_keypairs()
        # for openstack_keypair in openstack_keypairs:
        #     if openstack_keypair.public_key == public_key_content:
        #         return openstack_keypair
        # else:
        #     # Create a 'default' one
        #     return self.conn.create_keypair(
        #         'pycloudlib_default',
        #         self.key_pair.public_key_path
        #     )
