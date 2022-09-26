# This file is part of pycloudlib. See LICENSE file for license information.
"""LXD Cloud type."""
import warnings
from abc import abstractmethod
from contextlib import suppress
from typing import List

import yaml

from pycloudlib.cloud import BaseCloud
from pycloudlib.constants import LOCAL_UBUNTU_ARCH
from pycloudlib.lxd.defaults import (
    BIONIC_VM_METADATA_CONFIG_NOCLOUD,
    BIONIC_VM_TEMPLATES_NOCLOUD,
    base_vm_profiles,
)
from pycloudlib.lxd.instance import LXDInstance, LXDVirtualMachineInstance
from pycloudlib.util import subp


class _BaseLXD(BaseCloud):
    """LXD Base Cloud Class."""

    _type = "lxd"
    _daily_remote = "ubuntu-daily"
    _releases_remote = "ubuntu"
    _lxd_instance_cls = LXDInstance

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
        return LXDInstance(new_instance_name)

    def get_instance_metadata_config(self, instance_name: str) -> dict:
        """Get LXD instance metadata, returning a dict."""
        return yaml.safe_load(
            subp(["lxc", "config", "metadata", "show", instance_name])
        )

    def set_instance_metadata_config(
        self, instance_name: str, metadata_config: dict
    ):
        """Set LXC configuration metadata for an LXC instance.

        Args:
            instance_name: string, unique LXC instance name.
            metadata_config: dict, complete LXC metadata configuration
                values to set on the instance.
        """
        cmd = ["lxc", "config", "metadata", "edit", instance_name]
        self._log.debug("Setting instance metadata: %s", " ".join(cmd))
        subp(cmd, data=yaml.safe_dump(metadata_config))

    def get_instance_template_names(self, instance_name: str) -> List[str]:
        """Get LXD instance template names."""
        return yaml.safe_load(
            subp(
                [
                    "lxc",
                    "config",
                    "template",
                    "list",
                    instance_name,
                    "--format",
                    "yaml",
                ]
            )
        )

    def create_instance_template(
        self,
        instance_name: str,
        template_name: str,
        content: str,
        current_templates: List[str] = None,
    ):
        """Set LXC configuration templates for an LXC instance.

        Args:
            instance_name: string, unique LXC instance name.
            template_name: string, unique LXC instance name.
            content: string, template value to render for this template file
            current_templates: List of template names configured for this
                instance
        """
        if not current_templates:
            current_templates = self.get_instance_template_names(instance_name)
        if template_name not in current_templates:
            create_cmd = [
                "lxc",
                "config",
                "template",
                "create",
                instance_name,
                template_name,
            ]
            self._log.debug("Creating template for instance: %s", create_cmd)
            subp(create_cmd)
        edit_cmd = [
            "lxc",
            "config",
            "template",
            "edit",
            instance_name,
            template_name,
        ]
        self._log.debug("Setting template content for instance: %s", edit_cmd)
        subp(edit_cmd, data=content)

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
            msg = "The profile named {} already exists".format(profile_name)
            self._log.debug(msg)
            print(msg)
            return

        if force:
            self._log.debug("Deleting current profile %s ...", profile_name)
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
        self._log.debug("deleting %s", instance_name)
        inst = self.get_instance(instance_name)
        inst.delete(wait)

    def get_instance(self, instance_id):
        """Get an existing instance.

        Args:
            instance_id: instance name to get

        Returns:
            The existing instance as a LXD instance object

        """
        return self._lxd_instance_cls(instance_id, key_pair=self.key_pair)

    def _lxc_image_info(self, image_id: str) -> dict:
        """Return a dict of the output of ``lxc image info <image_id>``.

        Args:
            image_id: string, [<remote>:]<image identifier>, the image to
                      return the image info dict for

        Returns:
            A dict produced by loading the YAML emitted by ``lxc image info
            <image_id>``, or the empty dict if either the command or YAML load
            fails.
        """
        raw_image_info = subp(["lxc", "image", "info", image_id], rcs=())
        if raw_image_info.ok:
            try:
                return yaml.safe_load(raw_image_info)
            except yaml.YAMLError:
                pass
        return {}

    def _extract_release_from_image_id(self, image_id):
        """Extract the base release from the image_id.

        Args:
            image_id: string, [<remote>:]<image identifier>, the image to
                      determine the release of

        Returns:
            A string containing the base release from the image_id that is used
            to launch the image.
        """
        image_info = self._lxc_image_info(image_id)
        release = None
        try:
            properties = image_info["Properties"]
            os = properties["os"]
            # images: images have "Ubuntu", ubuntu: images have "ubuntu"
            if os.lower() == "ubuntu":
                release = properties["release"]
        except KeyError:
            # Image info doesn't have the info we need, so fallthrough
            pass
        else:
            if release is not None:
                return release

        # If we have a hash in the image_id we need to query simplestreams to
        # identify the release.
        return self._image_info(image_id)[0]["release"]

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
        series = self._extract_release_from_image_id(image_id)

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

        print(cmd)
        result = subp(cmd)

        if not name:
            name = result.split("Instance name is: ")[1]

        self._log.debug("Created %s", name)
        return self._lxd_instance_cls(
            name=name,
            key_pair=self.key_pair,
            execute_via_ssh=execute_via_ssh,
            series=series,
            ephemeral=ephemeral,
        )

    def _setup_instance_metadata_and_templates(self, image_id, instance):
        """Subclass implement when config is needed between init and start.

        LXDVirtualMachine requires additional config on Bionic VMs.
        """

    def launch(
        self,
        image_id,
        instance_type=None,
        user_data=None,
        wait=True,
        name=None,
        ephemeral=False,
        network=None,
        storage=None,
        profile_list=None,
        config_dict=None,
        execute_via_ssh=True,
        **kwargs,
    ):
        """Set up and launch a container.

        This will init and start a container with the provided settings.
        If no remote is specified pycloudlib defaults to daily images.

        On Bionic VMs, pycloudlib is forced to use NoCloud datasource config
        to setup lxd-agent.service to support lxc exec commands. This
        NoCloud config is provided via a config drive device and requires
        supplemental NoCloud templates for meta-data, network-config,
        vendor-data and user-data written to /var/lib/cloud/seed/nocloud-net.


        Args:
            image_id: string, [<remote>:]<image>, the image to launch
            instance_type: string, type to use
            user_data: used by cloud-init to run custom scripts/configuration
            wait: boolean, wait for instance to start
            name: string, what to call the instance
            ephemeral: boolean, ephemeral, otherwise persistent
            network: string, network name to use
            storage: string, storage name to use
            profile_list: list, profile(s) to use
            config_dict: dict, configuration values to pass
            execute_via_ssh: bool, optional, execute commands on the instance
                             via SSH if True (the default)

        Returns:
            The created LXD instance object

        """
        instance = self.init(
            name=name,
            image_id=image_id,
            ephemeral=ephemeral,
            network=network,
            storage=storage,
            inst_type=instance_type,
            profile_list=profile_list,
            user_data=user_data,
            config_dict=config_dict,
            execute_via_ssh=execute_via_ssh,
        )
        self._setup_instance_metadata_and_templates(image_id, instance)
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
        self._log.debug("finding released Ubuntu image for %s", release)
        return self._search_for_image(
            remote=self._releases_remote,
            daily=False,
            release=release,
            arch=arch,
        )

    def daily_image(self, release, arch=LOCAL_UBUNTU_ARCH):
        """Find the LXD fingerprint of the latest daily image.

        Args:
            release: string, Ubuntu release to look for
            arch: string, architecture to use

        Returns:
            string, LXD fingerprint of latest image

        """
        self._log.debug("finding daily Ubuntu image for %s", release)
        return self._search_for_image(
            remote=self._daily_remote, daily=True, release=release, arch=arch
        )

    @abstractmethod
    def _get_image_hash_key(self, release=None):
        """Get the correct hash key to be used to launch LXD instance.

        When query simplestreams for image information, we receive a
        dictionary of metadata. In that metadata we have the necessary
        information to allows us to launch the required image. However,
        we must know which key to use in the metadata dict to allows
        to launch the image.

        Args:
            release: string, optional, Ubuntu release

        Returns
            A string specifying which key of the metadata dictionary
            should be used to launch the image.
        """
        raise NotImplementedError

    def _search_for_image(
        self, remote, daily, release, arch=LOCAL_UBUNTU_ARCH
    ):
        """Find the LXD fingerprint in a given remote.

        Args:
            remote: string, remote to prepend to image_id
            daily: boolean, search on daily remote
            release: string, Ubuntu release to look for
            arch: string, architecture to use

        Returns:
            string, LXD fingerprint of latest image

        """
        image_data = self._find_image(release, arch, daily=daily)
        image_hash_key = self._get_image_hash_key(release)

        return "%s:%s" % (remote, image_data[image_hash_key])

    def _image_info(self, image_id, image_hash_key=None):
        """Find the image serial of a given LXD image.

        Args:
            image_id: string, LXD image fingerprint
            image_hash_key: string, the metadata key used to launch the image

        Returns:
            dict, image info available for the image_id

        """
        daily = True
        if ":" in image_id:
            remote = image_id[: image_id.index(":")]
            image_id = image_id[image_id.index(":") + 1 :]
            if remote == self._releases_remote:
                daily = False
            elif remote != self._daily_remote:
                raise RuntimeError("Unknown remote: %s" % remote)

        if not image_hash_key:
            image_hash_key = self._get_image_hash_key()

        filters = ["%s=%s" % (image_hash_key, image_id)]
        image_info = self._streams_query(filters, daily=daily)

        return image_info

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

        image_info = self._image_info(image_id)

        return image_info[0]["version_name"]

    def delete_image(self, image_id):
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
            "datatype=image-downloads",
            "ftype=lxd.tar.xz",
            "arch=%s" % arch,
            "release=%s" % release,
        ]

        return self._streams_query(filters, daily)[0]


class LXDContainer(_BaseLXD):
    """LXD Containers Cloud Class."""

    CONTAINER_HASH_KEY = "combined_squashfs_sha256"

    def _get_image_hash_key(self, release=None):
        """Get the correct hash key to be used to launch LXD instance.

        When query simplestreams for image information, we receive a
        dictionary of metadata. In that metadata we have the necessary
        information to allows us to launch the required image. However,
        we must know which key to use in the metadata dict to allows
        to launch the image.

        Args:
            release: string, optional, Ubuntu release

        Returns
            A string specifying which key of the metadata dictionary
            should be used to launch the image.
        """
        return self.CONTAINER_HASH_KEY

    def _image_info(self, image_id, image_hash_key=None):
        """Find the image serial of a given LXD image.

        Args:
            image_id: string, LXD image fingerprint
            image_hash_key: string, the metadata key used to launch the image

        Returns:
            dict, image info available for the image_id

        """
        return super()._image_info(
            image_id=image_id, image_hash_key=self.CONTAINER_HASH_KEY
        )


class LXD(LXDContainer):
    """Old LXD Container Cloud Class (Kept for compatibility issues)."""

    def __init__(self, *args, **kwargs):
        """Run LXDContainer constructor."""
        warnings.warn("LXD class is deprecated; use LXDContainer instead.")
        super().__init__(*args, **kwargs)


class LXDVirtualMachine(_BaseLXD):
    """LXD Virtual Machine Cloud Class."""

    DISK1_HASH_KEY = "combined_disk1-img_sha256"
    DISK_UEFI1_KEY = "combined_uefi1-img_sha256"
    DISK_KVM_HASH_KEY = "combined_disk-kvm-img_sha256"
    _lxd_instance_cls = LXDVirtualMachineInstance

    def _image_info(self, image_id, image_hash_key=None):
        """Return image info for the given ID.

        With LXD VMs, there are two possible keys that image_id could refer to;
        we try the more recent one first, followed by the older key.

        (If image_hash_key is passed, then that is used unambiguously.)
        """
        if image_hash_key is not None:
            return super()._image_info(image_id, image_hash_key=image_hash_key)
        with suppress(ValueError):
            return super()._image_info(
                image_id, image_hash_key=self.DISK_KVM_HASH_KEY
            )
        with suppress(ValueError):
            return super()._image_info(
                image_id, image_hash_key=self.DISK_UEFI1_KEY
            )

        return super()._image_info(
            image_id, image_hash_key=self.DISK1_HASH_KEY
        )

    def build_necessary_profiles(self, image_id):
        """Build necessary profiles to launch the LXD instance.

        Args:
            image_id: string, [<remote>:]<release>, the image to build profiles
                      for

        Returns:
            A list containing the profiles created
        """
        image_id = self._normalize_image_id(image_id)
        base_release = self._extract_release_from_image_id(image_id)
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

    def _get_image_hash_key(self, release=None):
        """Get the correct hash key to be used to launch LXD instance.

        When query simplestreams for image information, we receive a
        dictionary of metadata. In that metadata we have the necessary
        information to allows us to launch the required image. However,
        we must know which key to use in the metadata dict to allows
        to launch the image.

        Args:
            release: string, optional, Ubuntu release

        Returns
            A string specifying which key of the metadata dictionary
            should be used to launch the image.
        """
        if release == "bionic":
            # Older releases do not have disk-kvm.img
            return self.DISK1_HASH_KEY

        if release == "xenial":
            return self.DISK_UEFI1_KEY

        return self.DISK_KVM_HASH_KEY

    def _setup_instance_metadata_and_templates(
        self, image_id: str, instance: _BaseLXD
    ):
        # Drop when bionic support no longer needed
        base_release = self._extract_release_from_image_id(image_id)
        if base_release == "bionic":
            # Setup LXC NoCloud metadata templates if absent on this image
            lxc_md = self.get_instance_metadata_config(instance.name)
            missing_templates = []
            for md_key, md_value in BIONIC_VM_METADATA_CONFIG_NOCLOUD.items():
                if md_key not in lxc_md["templates"]:
                    missing_templates.append(md_key)
                    lxc_md["templates"][md_key] = md_value
            if missing_templates:
                self._log.debug(
                    "Adding missing LXD NoCloud templates for instance %s: %s",
                    instance.name,
                    ", ".join(missing_templates),
                )
                self.set_instance_metadata_config(
                    instance.name, metadata_config=lxc_md
                )
            tpl_names = self.get_instance_template_names(instance.name)
            for tpl_name in set(BIONIC_VM_TEMPLATES_NOCLOUD) - set(tpl_names):
                self.create_instance_template(
                    instance.name,
                    tpl_name,
                    BIONIC_VM_TEMPLATES_NOCLOUD[tpl_name],
                    tpl_names,
                )
