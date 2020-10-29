# This file is part of pycloudlib. See LICENSE file for license information.
"""LXD Cloud type."""

from pycloudlib.cloud import BaseCloud
from pycloudlib.lxd.instance import LXDInstance
from pycloudlib.util import subp
from pycloudlib.constants import LOCAL_UBUNTU_ARCH
from pycloudlib.lxd.defaults import base_vm_profiles


class LXD(BaseCloud):
    """LXD Cloud Class."""

    _type = 'lxd'
    _daily_remote = 'ubuntu-daily'
    _releases_remote = 'ubuntu'

    def clone(self, base, new_instance_name):
        """Create copy of an existing instance or snapshot.

        Uses the `lxc copy` command to create a copy of an existing
        instance or a snapshot. To clone a snapshot then the base
        is `instance_name/snapshot_name` otherwise if base is only
        an existing instance it will clone an instance.

        Args:
            base: base instance or instance/snapshot
            new_instance_name: name of new instance

        Returns:
            The created LXD instance object

        """
        self._log.debug('cloning %s to %s', base, new_instance_name)
        subp(['lxc', 'copy', base, new_instance_name])
        return LXDInstance(new_instance_name)

    def create_profile(
        self, profile_name, profile_config, force_creation=False
    ):
        """Create a lxd profile.

        Create a lxd profile and populate it with the given
        profile config. If the profile already exists, we will
        not recreate it, unless the force_creation parameter is set to True.

        Args:
            profile_name: Name of the profile to be created
            profile_config: Config to be added to the new profile
            force_creation: Force the profile creation if it already exists
        """
        profile_list = subp(["lxc", "profile", "list"])

        if profile_name in profile_list and not force_creation:
            msg = "The profile named {} already exist".format(profile_name)
            self._log.debug(msg)
            print(msg)
        else:

            if force_creation:
                self._log.debug(
                    "Deleting current profile %s ...", profile_name)
                subp(["lxc", "profile", "delete", profile_name])

            self._log.debug("Creating profile %s ...", profile_name)
            subp(["lxc", "profile", "create", profile_name])
            subp(["lxc", "profile", "edit", profile_name], data=profile_config)

    def delete_instance(self, instance_name, wait=True):
        """Delete an instance.

        Args:
            instance_name: instance name to delete
            wait: wait for delete to complete
        """
        self._log.debug('deleting %s', instance_name)
        inst = self.get_instance(instance_name)
        inst.delete(wait)

    def get_instance(self, instance_id):
        """Get an existing instance.

        Args:
            instance_id: instance name to get

        Returns:
            The existing instance as a LXD instance object

        """
        return LXDInstance(instance_id)

    def _set_release_image(self, release, is_vm):
        """Return the qualified name to launch a given release.

        Args:
            release: Name of the release to be launched
            is_vm: If instance should be a virtual machine or not

        Returns:
            The qualified name to launch the given release.
        """
        if is_vm and release == "xenial":
            # xenial needs to launch images:ubuntu/16.04/cloud
            # because it contains the HWE kernel which has vhost-vsock support
            release = "images:ubuntu/16.04/cloud"
        elif ':' not in release:
            release = self._daily_remote + ':' + release

        return release

    # pylint: disable=R0914
    def init(
            self, name, image_id, ephemeral=False, network=None, storage=None,
            inst_type=None, profile_list=None, user_data=None,
            config_dict=None, is_vm=False):
        """Init a container.

        This will initialize a container, but not launch or start it.
        If no remote is specified pycloudlib default to daily images.

        Args:
            name: string, what to call the instance
            image_id: string, [<remote>:]<release>, what release to launch
                     (default remote: )
            ephemeral: boolean, ephemeral, otherwise persistent
            network: string, optional, network name to use
            storage: string, optional, storage name to use
            inst_type: string, optional, type to use
            profile_list: list, optional, profile(s) to use
            user_data: used by cloud-init to run custom scripts/configuration
            config_dict: dict, optional, configuration values to pass
            is_vm: boolean, optional, defines if a virtual machine will
                   be created

        Returns:
            The created LXD instance object

        """
        base_release = image_id

        release = self._set_release_image(image_id, is_vm)
        self._log.debug("Full release to launch: '%s'", release)

        cmd = ['lxc', 'init', release, name]

        if is_vm:
            cmd.append('--vm')

            if not profile_list:
                profile_name = "vm-{}".format(base_release)

                self.create_profile(
                    profile_name=profile_name,
                    profile_config=base_vm_profiles[base_release]
                )

                profile_list = [profile_name]

        if ephemeral:
            cmd.append('--ephemeral')

        if network:
            cmd.append('--network')
            cmd.append(network)

        if storage:
            cmd.append('--storage')
            cmd.append(storage)

        if inst_type:
            cmd.append('--type')
            cmd.append(inst_type)

        profile_list = profile_list if profile_list else []
        for profile in profile_list:
            cmd.append('--profile')
            cmd.append(profile)

        config_dict = config_dict if config_dict else {}
        for key, value in config_dict.items():
            cmd.append('--config')
            cmd.append('%s=%s' % (key, value))

        if user_data:
            if 'user.user-data' in config_dict:
                raise ValueError(
                    "User data cannot be defined in config_dict and also"
                    "passed through user_data. Pick one"
                )
            cmd.append('--config')
            cmd.append('user.user-data=%s' % user_data)

        self._log.debug('Creating new instance...')
        print(cmd)
        result = subp(cmd)
        if not name:
            name = result.split('Instance name is: ')[1]
        self._log.debug('Created %s', name)

        return LXDInstance(name, is_vm)

    def launch(self, image_id, instance_type=None, user_data=None, wait=True,
               name=None, ephemeral=False, network=None, storage=None,
               profile_list=None, config_dict=None, is_vm=False, **kwargs):
        """Set up and launch a container.

        This will init and start a container with the provided settings.
        If no remote is specified pycloudlib defaults to daily images.

        Args:
            image_id: string, [<remote>:]<image>, what release to launch
            instance_type: string, type to use
            user_data: used by cloud-init to run custom scripts/configuration
            wait: boolean, wait for instance to start
            name: string, what to call the instance
            ephemeral: boolean, ephemeral, otherwise persistent
            network: string, network name to use
            storage: string, storage name to use
            profile_list: list, profile(s) to use
            config_dict: dict, configuration values to pass
            is_vm: boolean, optional, defines if a virtual machine will
                   be created

        Returns:
            The created LXD instance object

        """
        instance = self.init(name, image_id, ephemeral, network,
                             storage, instance_type, profile_list, user_data,
                             config_dict, is_vm)
        instance.start(wait)
        return instance

    def released_image(self, release, arch=LOCAL_UBUNTU_ARCH):
        """Find the LXD fingerprint of the latest released image.

        Args:
            release: string, Ubuntu release to look for
            arch: string, architecture to use

        Returns:
            string, LXD fingerprint of latest image

        """
        self._log.debug('finding released Ubuntu image for %s', release)
        image_data = self._find_image(release, arch, daily=False)
        image = '%s:%s' % (self._releases_remote,
                           image_data['combined_squashfs_sha256'])
        return image

    def daily_image(self, release, arch=LOCAL_UBUNTU_ARCH):
        """Find the LXD fingerprint of the latest daily image.

        Args:
            release: string, Ubuntu release to look for
            arch: string, architecture to use

        Returns:
            string, LXD fingerprint of latest image

        """
        self._log.debug('finding daily Ubuntu image for %s', release)
        image_data = self._find_image(release, arch, daily=True)
        image = '%s:%s' % (self._daily_remote,
                           image_data['combined_squashfs_sha256'])
        return image

    def image_serial(self, image_id):
        """Find the image serial of a given LXD image.

        Args:
            image_id: string, LXD image fingerprint

        Returns:
            string, serial of latest image

        """
        self._log.debug(
            'finding image serial for LXD Ubuntu image %s', image_id)

        daily = True
        if ':' in image_id:
            remote = image_id[:image_id.index(':')]
            image_id = image_id[image_id.index(':')+1:]
            if remote == self._releases_remote:
                daily = False
            elif remote != self._daily_remote:
                raise RuntimeError('Unknown remote: %s' % remote)

        filters = ['combined_squashfs_sha256=%s' % image_id]
        image_info = self._streams_query(filters, daily=daily)
        return image_info[0]['version_name']

    def delete_image(self, image_id):
        """Delete the image.

        Args:
            image_id: string, LXD image fingerprint
        """
        self._log.debug("Deleting image: '%s'", image_id)

        subp(['lxc', 'image', 'delete', image_id])
        self._log.debug('Deleted %s', image_id)

    def snapshot(self, instance, clean=True, name=None):
        """Take a snapshot of the passed in instance for use as image.

        :param instance: The instance to create an image from
        :type instance: LXDInstance
        :param clean: Whether to call cloud-init clean before creation
        :param wait: Whether to wait until before image is created
            before returning
        :param name: Name of the new image
        :param stateful: Whether to use an LXD stateful snapshot
        """
        if clean:
            instance.clean()

        return instance.snapshot(name)

    def _find_image(self, release, arch=LOCAL_UBUNTU_ARCH, daily=True):
        """Find the latest image for a given release.

        Args:
            release: string, Ubuntu release to look for
            arch: string, architecture to use

        Returns:
            list of dictionaries of images

        """
        filters = [
            'datatype=image-downloads',
            'ftype=lxd.tar.xz',
            'arch=%s' % arch,
            'release=%s' % release,
        ]

        return self._streams_query(filters, daily)[0]
