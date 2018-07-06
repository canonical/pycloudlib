# This file is part of pycloudlib. See LICENSE file for license information.
"""LXD Cloud type."""

from pycloudlib.base_cloud import BaseCloud
from pycloudlib.lxd.instance import LXDInstance
from pycloudlib.util import subp


class LXD(BaseCloud):  # pylint: disable=W0223
    """LXD Cloud Class."""

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

    def init(self, name, release, image_remote='ubuntu-daily', ephemeral=False,
             network=None, storage=None, inst_type=None, profile_list=None,
             config_dict=None):
        """Init a container.

        This will initialize a container, but not launch or start it.

        Args:
            name: string, what to call the instance
            release: string, what release to launch
            image_remote: string, image remote name (default: ubuntu-daily)
            ephemeral: boolean, ephemeral, otherwise persistent
            network: string, optional, network name to use
            storage: string, optional, storage name to use
            inst_type: string, optional, type to use
            profile_list: list, optional, profile(s) to use
            config_dict: dict, optional, configuration values to pass

        Returns:
            The created LXD instance object

        """
        cmd = ['lxc', 'init', '%s:%s' % (image_remote, release), name]

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

    def launch(self, name, release, image_remote='ubuntu-daily',
               ephemeral=False, network=None, storage=None, inst_type=None,
               profile_list=None, config_dict=None, wait=True):
        """Set up and launch a container.

        This will init and start a container with the provied settings.

        Args:
            name: string, what to call the instance
            release: string, what release to launch
            image_remote: string, image remote name (default: ubuntu-daily)
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
        instance = self.init(
            name, release, image_remote, ephemeral, network, storage,
            inst_type, profile_list, config_dict
        )
        instance.start(wait)
        return instance
