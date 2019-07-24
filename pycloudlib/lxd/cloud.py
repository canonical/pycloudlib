# This file is part of pycloudlib. See LICENSE file for license information.
"""LXD Cloud type."""

from pycloudlib.cloud import BaseCloud
from pycloudlib.lxd.instance import LXDInstance
from pycloudlib.util import subp
from pycloudlib.util import local_ubuntu_arch


class LXD(BaseCloud):  # pylint: disable=W0223
    """LXD Cloud Class."""

    _type = 'lxd'
    _daily_remote = 'ubuntu-daily'
    _releases_remote = 'ubuntu'
    _local_ubuntu_arch = local_ubuntu_arch()

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

    def delete_instance(self, instance_name, wait=True):
        """Delete an instance.

        Args:
            instance_name: instance name to delete
            wait: wait for delete to complete
        """
        self._log.debug('deleting %s', instance_name)
        inst = self.get_instance(instance_name)
        inst.delete(wait)

    def get_instance(self, instance_name):
        """Get an existing instance.

        Args:
            instance_name: instance name to get

        Returns:
            The existing instance as a LXD instance object

        """
        return LXDInstance(instance_name)

    # pylint: disable=R0914
    def init(
            self, name, release, ephemeral=False, network=None, storage=None,
            inst_type=None, profile_list=None, config_dict=None):
        """Init a container.

        This will initialize a container, but not launch or start it.
        If no remote is specified pycloudlib default to daily images.

        Args:
            name: string, what to call the instance
            release: string, [<remote>:]<release>, what release to launch
                     (default remote: )
            ephemeral: boolean, ephemeral, otherwise persistent
            network: string, optional, network name to use
            storage: string, optional, storage name to use
            inst_type: string, optional, type to use
            profile_list: list, optional, profile(s) to use
            config_dict: dict, optional, configuration values to pass

        Returns:
            The created LXD instance object

        """
        if ':' not in release:
            release = self._daily_remote + ':' + release

        self._log.debug("Full release to launch: '%s'", release)

        cmd = ['lxc', 'init', release, name]

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

        self._log.debug('Creating %s', name)
        subp(cmd)

        return LXDInstance(name)

    def launch(
            self, name, release, ephemeral=False, network=None, storage=None,
            inst_type=None, profile_list=None, config_dict=None, wait=True):
        """Set up and launch a container.

        This will init and start a container with the provided settings.
        If no remote is specified pycloudlib defaults to daily images.

        Args:
            name: string, what to call the instance
            release: string, [<remote>:]<image>, what release to launch
            ephemeral: boolean, ephemeral, otherwise persistent
            network: string, network name to use
            storage: string, storage name to use
            inst_type: string, type to use
            profile_list: list, profile(s) to use
            config_dict: dict, configuration values to pass
            wait: boolean, wait for instance to start

        Returns:
            The created LXD instance object

        """
        instance = self.init(name, release, ephemeral, network,
                             storage, inst_type, profile_list, config_dict)
        instance.start(wait)
        return instance

    def released_image(self, release, arch=_local_ubuntu_arch):
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

    def daily_image(self, release, arch=_local_ubuntu_arch):
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

    def _find_image(self, release, arch=_local_ubuntu_arch, daily=True):
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
