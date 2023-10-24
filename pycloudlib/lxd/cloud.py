# This file is part of pycloudlib. See LICENSE file for license information.
"""LXD Cloud type."""
import warnings
from abc import ABC
from itertools import count
from typing import List, Optional

import yaml

from pycloudlib.cloud import BaseCloud
from pycloudlib.constants import LOCAL_UBUNTU_ARCH
from pycloudlib.lxd import _images
from pycloudlib.lxd.defaults import base_vm_profiles
from pycloudlib.lxd.instance import LXDInstance, LXDVirtualMachineInstance
from pycloudlib.util import subp


class _BaseLXD(BaseCloud, ABC):
    """LXD Base Cloud Class."""

    _type = "lxd"
    _daily_remote = "ubuntu-daily"
    _releases_remote = "ubuntu"
    _lxd_instance_cls = LXDInstance
    _instance_counter = count()
    _is_container: bool

    def __init__(self, *args, **kwargs):
        """Initialize the LXD Instance."""
        super().__init__(*args, **kwargs)
        self.created_profiles = []
        self.created_snapshots = []

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
        self._log.debug("cloning %s to %s", base, new_instance_name)
        subp(["lxc", "copy", base, new_instance_name])
        instance = LXDInstance(new_instance_name)
        self.created_instances.append(instance)
        return instance

    def create_profile(self, profile_name, profile_config, force=False):
        """Create a lxd profile.

        Create a lxd profile and populate it with the given
        profile config. If the profile already exists, we will
        not recreate it, unless the force parameter is set to True.

        Args:
            profile_name: Name of the profile to be created
            profile_config: Config to be added to the new profile
            force: Force the profile creation if it already exists
        """
        profile_yaml = subp(["lxc", "profile", "list", "--format", "yaml"])
        profile_list = [
            profile["name"] for profile in yaml.safe_load(profile_yaml)
        ]

        if profile_name in profile_list and not force:
            msg = f"The profile named {profile_name} already exists"
            self._log.debug(msg)
            return

        if force:
            self._log.debug("Deleting current profile %s ...", profile_name)
            subp(["lxc", "profile", "delete", profile_name])

        self._log.debug("Creating profile %s ...", profile_name)
        subp(["lxc", "profile", "create", profile_name])
        subp(["lxc", "profile", "edit", profile_name], data=profile_config)
        self.created_profiles.append(profile_name)

    def delete_instance(self, instance_name, wait=True):
        """Delete an instance.

        Args:
            instance_name: instance name to delete
            wait: wait for delete to complete
        """
        self._log.debug("deleting %s", instance_name)
        inst = self.get_instance(instance_name)
        inst.delete(wait)

    def get_instance(
        self, instance_id, *, username: Optional[str] = None, **kwargs
    ):
        """Get an existing instance.

        Args:
            instance_id: instance name to get
            username: username to use when connecting via SSH

        Returns:
            The existing instance as a LXD instance object

        """
        return self._lxd_instance_cls(
            instance_id, key_pair=self.key_pair, username=username
        )

    def _normalize_image_id(self, image_id: str) -> str:
        if ":" not in image_id:
            return self._daily_remote + ":" + image_id
        return image_id

    # pylint: disable=R0914,R0912,R0915
    def _prepare_command(
        self,
        name,
        image_id,
        ephemeral=False,
        network=None,
        storage=None,
        inst_type=None,
        profile_list=None,
        user_data=None,
        config_dict=None,
    ):
        """Build a the command to be used to launch the LXD instance.

        Args:
            name: string, what to call the instance
            image_id: string, [<remote>:]<image identifier>, the image to
                      launch
            ephemeral: boolean, ephemeral, otherwise persistent
            network: string, optional, network name to use
            storage: string, optional, storage name to use
            inst_type: string, optional, type to use
            profile_list: list, optional, profile(s) to use
            user_data: used by cloud-init to run custom scripts/configuration
            config_dict: dict, optional, configuration values to pass

        Returns:
            A list of string representing the command to be run to
            launch the LXD instance.
        """
        profile_list = profile_list if profile_list else []
        config_dict = config_dict if config_dict else {}

        self._log.debug("Full image ID to launch: '%s'", image_id)
        cmd = ["lxc", "init", image_id]

        if name:
            cmd.append(name)

        if self.key_pair:
            metadata = "public-keys: {}".format(
                self.key_pair.public_key_content
            )
            config_dict["user.meta-data"] = metadata

        if ephemeral:
            cmd.append("--ephemeral")

        if network:
            cmd.append("--network")
            cmd.append(network)

        if storage:
            cmd.append("--storage")
            cmd.append(storage)

        if inst_type:
            cmd.append("--type")
            cmd.append(inst_type)

        for profile in profile_list:
            cmd.append("--profile")
            cmd.append(profile)

        for key, value in config_dict.items():
            cmd.append("--config")
            cmd.append("%s=%s" % (key, value))

        if user_data:
            if "user.user-data" in config_dict:
                raise ValueError(
                    "User data cannot be defined in config_dict and also"
                    "passed through user_data. Pick one"
                )
            cmd.append("--config")
            cmd.append("user.user-data=%s" % user_data)

        return cmd

    def init(
        self,
        name,
        image_id,
        ephemeral=False,
        network=None,
        storage=None,
        inst_type=None,
        profile_list=None,
        user_data=None,
        config_dict=None,
        execute_via_ssh=True,
        username: Optional[str] = None,
    ):
        """Init a container.

        This will initialize a container, but not launch or start it.
        If no remote is specified pycloudlib default to daily images.

        Args:
            name: string, what to call the instance
            image_id: string, [<remote>:]<image identifier>, the image to
                      launch
            ephemeral: boolean, ephemeral, otherwise persistent
            network: string, optional, network name to use
            storage: string, optional, storage name to use
            inst_type: string, optional, type to use
            profile_list: list, optional, profile(s) to use
            user_data: used by cloud-init to run custom scripts/configuration
            config_dict: dict, optional, configuration values to pass
            execute_via_ssh: bool, optional, execute commands on the instance
                             via SSH if True (the default)

        Returns:
            The created LXD instance object

        """
        image_id = self._normalize_image_id(image_id)
        series = _images.find_release(image_id)

        cmd = self._prepare_command(
            name=name,
            image_id=image_id,
            ephemeral=ephemeral,
            network=network,
            storage=storage,
            inst_type=inst_type,
            profile_list=profile_list,
            user_data=user_data,
            config_dict=config_dict,
        )

        self._log.info(cmd)
        result = subp(cmd)

        if not name:
            name = result.split("Instance name is: ")[1]

        self._log.debug("Created %s", name)
        instance = self._lxd_instance_cls(
            name=name,
            key_pair=self.key_pair,
            execute_via_ssh=execute_via_ssh,
            series=series,
            ephemeral=ephemeral,
            username=username,
        )
        self.created_instances.append(instance)
        return instance

    def launch(
        self,
        image_id,
        instance_type=None,
        user_data=None,
        name=None,
        ephemeral=False,
        network=None,
        storage=None,
        profile_list=None,
        config_dict=None,
        execute_via_ssh=True,
        *,
        username: Optional[str] = None,
        **kwargs,
    ):
        """Set up and launch a container.

        This will init and start a container with the provided settings.
        If no remote is specified pycloudlib defaults to daily images.

        Args:
            image_id: string, [<remote>:]<image>, the image to launch
            instance_type: string, type to use
            user_data: used by cloud-init to run custom scripts/configuration
            name: string, what to call the instance
            ephemeral: boolean, ephemeral, otherwise persistent
            network: string, network name to use
            storage: string, storage name to use
            profile_list: list, profile(s) to use
            config_dict: dict, configuration values to pass
            execute_via_ssh: bool, optional, execute commands on the instance
                             via SSH if True (the default)
            username: username to use when connecting via SSH

        Returns:
            The created LXD instance object
        Raises: ValueError on missing image_id
        """
        if not image_id:
            raise ValueError(
                f"{self._type} launch requires image_id param."
                f" Found: {image_id}"
            )
        instance = self.init(
            name=name or f"{self.tag}-{next(self._instance_counter)}",
            image_id=image_id,
            ephemeral=ephemeral,
            network=network,
            storage=storage,
            inst_type=instance_type,
            profile_list=profile_list,
            user_data=user_data,
            config_dict=config_dict,
            execute_via_ssh=execute_via_ssh,
            username=username,
        )
        instance.start(wait=False)

        return instance

    def released_image(self, release, arch=LOCAL_UBUNTU_ARCH):
        """Find the LXD fingerprint of the latest released image.

        Args:
            release: string, Ubuntu release to look for
            arch: string, architecture to use

        Returns:
            string, LXD fingerprint of latest image

        """
        self._log.debug("finding released Ubuntu image for %s", release)
        return _images.find_last_fingerprint(
            daily=False,
            release=release,
            arch=arch,
            is_container=self._is_container,
        )

    def daily_image(
        self, release: str, arch: str = LOCAL_UBUNTU_ARCH, **kwargs
    ):
        """Find the LXD fingerprint of the latest daily image.

        Args:
            release: string, Ubuntu release to look for
            arch: string, architecture to use

        Returns:
            string, LXD fingerprint of latest image

        """
        self._log.debug("finding daily Ubuntu image for %s", release)
        return _images.find_last_fingerprint(
            daily=True,
            release=release,
            arch=arch,
            is_container=self._is_container,
        )

    def image_serial(self, image_id):
        """Find the image serial of a given LXD image.

        Args:
            image_id: string, LXD image fingerprint

        Returns:
            string, serial of latest image

        """
        self._log.debug(
            "finding image serial for LXD Ubuntu image %s", image_id
        )
        return _images.find_image_serial(image_id)

    def delete_image(self, image_id, **kwargs):
        """Delete the image.

        Args:
            image_id: string, LXD image fingerprint
        """
        self._log.debug("Deleting image: '%s'", image_id)

        subp(["lxc", "image", "delete", image_id])
        self._log.debug("Deleted %s", image_id)

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

        snapshot_name = instance.snapshot(name)
        self.created_snapshots.append(snapshot_name)
        return snapshot_name

    # pylint: disable=broad-except
    def clean(self) -> List[Exception]:
        """Cleanup ALL artifacts associated with this Cloud instance.

        Cleanup any cloud artifacts created at any time during this class's
        existence. This includes all instances, snapshots, resources, etc.
        """
        exceptions = super().clean()

        for snapshot in self.created_snapshots:
            try:
                subp(["lxc", "image", "delete", snapshot])
            except RuntimeError as e:
                if "Image not found" not in str(e):
                    exceptions.append(e)

        for profile in self.created_profiles:
            try:
                subp(["lxc", "profile", "delete", profile])
            except RuntimeError as e:
                if "Profile not found" not in str(e):
                    exceptions.append(e)
        return exceptions


class LXDContainer(_BaseLXD):
    """LXD Containers Cloud Class."""

    def __init__(self, *args, **kwargs):
        """Run LXDContainer constructor."""
        super().__init__(*args, **kwargs)
        self._is_container = True


class LXD(LXDContainer):
    """Old LXD Container Cloud Class (Kept for compatibility issues)."""

    def __init__(self, *args, **kwargs):
        """Run LXDContainer constructor."""
        warnings.warn("LXD class is deprecated; use LXDContainer instead.")
        super().__init__(*args, **kwargs)


class LXDVirtualMachine(_BaseLXD):
    """LXD Virtual Machine Cloud Class."""

    _lxd_instance_cls = LXDVirtualMachineInstance

    def __init__(self, *args, **kwargs):
        """Run LXDVirtualMachine constructor."""
        super().__init__(*args, **kwargs)
        self._is_container = False

    def build_necessary_profiles(self, image_id):
        """Build necessary profiles to launch the LXD instance.

        Args:
            image_id: string, [<remote>:]<release>, the image to build profiles
                      for

        Returns:
            A list containing the profiles created
        """
        image_id = self._normalize_image_id(image_id)
        base_release = _images.find_release(image_id)
        if base_release not in ["xenial", "bionic"]:
            base_release = "default"
        profile_name = f"pycloudlib-vm-{base_release}"

        self.create_profile(
            profile_name=profile_name,
            profile_config=base_vm_profiles[base_release],
        )

        return [profile_name]

    def _prepare_command(
        self,
        name,
        image_id,
        ephemeral=False,
        network=None,
        storage=None,
        inst_type=None,
        profile_list=None,
        user_data=None,
        config_dict=None,
    ):
        """Build a the command to be used to launch the LXD instance.

        Args:
            name: string, what to call the instance
            image_id: string, [<remote>:]<image identifier>, the image to
                      launch
            ephemeral: boolean, ephemeral, otherwise persistent
            network: string, optional, network name to use
            storage: string, optional, storage name to use
            inst_type: string, optional, type to use
            profile_list: list, optional, profile(s) to use
            user_data: used by cloud-init to run custom scripts/configuration
            config_dict: dict, optional, configuration values to pass

        Returns:
            A list of string representing the command to be run to
            launch the LXD instance.
        """
        if not profile_list:
            profile_list = self.build_necessary_profiles(image_id)

        cmd = super()._prepare_command(
            name=name,
            image_id=image_id,
            ephemeral=ephemeral,
            network=network,
            storage=storage,
            inst_type=inst_type,
            profile_list=profile_list,
            user_data=user_data,
            config_dict=config_dict,
        )

        cmd.append("--vm")

        return cmd
