# This file is part of pycloudlib. See LICENSE file for license information.
"""LXD Cloud type."""
import io
import re
import textwrap
import paramiko

from pycloudlib.cloud import BaseCloud
from pycloudlib.lxd.instance import LXDInstance
from pycloudlib.util import subp, UBUNTU_RELEASE_VERSION_MAP
from pycloudlib.constants import LOCAL_UBUNTU_ARCH
from pycloudlib.lxd.defaults import base_vm_profiles


class UnsupportedReleaseException(Exception):
    """Unsupported release exception."""

    msg_tmpl = "Release {} is not supported for LXD{}"

    def __init__(self, release, is_vm):
        """Prepare unsupported release message."""
        vm_msg = ""

        if is_vm:
            vm_msg = " vms"

        super().__init__(
            self.msg_tmpl.format(release, vm_msg)
        )


class LXD(BaseCloud):
    """LXD Cloud Class."""

    _type = 'lxd'
    _daily_remote = 'ubuntu-daily'
    _releases_remote = 'ubuntu'

    XENIAL_IMAGE_VSOCK_SUPPORT = "images:ubuntu/16.04/cloud"
    VM_HASH_KEY = "combined_disk1-img_sha256"
    TRUSTY_CONTAINER_HASH_KEY = "combined_rootxz_sha256"
    CONTAINER_HASH_KEY = "combined_squashfs_sha256"

    def __init__(self, tag, timestamp_suffix=True):
        """Initialize LXD cloud class.

        Args:
            tag: string used to name and tag resources with
            timestamp_suffic: Append a timestamped suffix to the tag string.
        """
        super().__init__(tag, timestamp_suffix)

        # User must manually specify the key pair to be used
        self.key_pair = None

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
        self, profile_name, profile_config, force=False
    ):
        """Create a lxd profile.

        Create a lxd profile and populate it with the given
        profile config. If the profile already exists, we will
        not recreate it, unless the force parameter is set to True.

        Args:
            profile_name: Name of the profile to be created
            profile_config: Config to be added to the new profile
            force: Force the profile creation if it already exists
        """
        profile_list = subp(["lxc", "profile", "list"])

        if profile_name in profile_list and not force:
            msg = "The profile named {} already exists".format(profile_name)
            self._log.debug(msg)
            print(msg)
            return

        if force:
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
        instance = LXDInstance(instance_id)

        if self.key_pair:
            local_path = "/tmp/{}-authorized-keys".format(instance_id)

            instance.pull_file(
                remote_path="/home/ubuntu/.ssh/authorized_keys",
                local_path=local_path
            )

            with open(local_path, "r") as f:
                if self.key_pair.public_key_content in f.read():
                    instance.key_pair = self.key_pair

        return instance

    def create_key_pair(self):
        """Create and set a ssh key pair to be used by the lxd instance.

        Args:
            name: The name of the pycloudlib instance

        Returns:
            A tuple containing the public and private key created
        """
        key = paramiko.RSAKey.generate(4096)
        priv_str = io.StringIO()

        pub_key = key.get_base64()
        key.write_private_key(priv_str, password=None)

        return pub_key, priv_str.getvalue()

    def _extract_release_from_image_id(self, image_id, is_vm=False):
        """Extract the base release from the image_id.

        Args:
            image_id: string, [<remote>:]<release>, what release to launch
                     (default remote: )

        Returns:
            A string contaning the base release from the image_id that is used
            to launch the image.
        """
        release_regex = (
            "(.*ubuntu.*(?P<release>(" +
            "|".join(UBUNTU_RELEASE_VERSION_MAP) + "|" +
            "|".join(UBUNTU_RELEASE_VERSION_MAP.values()) +
            ")).*)"
        )
        ubuntu_match = re.match(release_regex, image_id)
        if ubuntu_match:
            release = ubuntu_match.groupdict()["release"]
            for codename, version in UBUNTU_RELEASE_VERSION_MAP.items():
                if release in (codename, version):
                    return codename

        # If we have a hash in the image_id we need to query simplestreams to
        # identify the release.
        return self._image_info(image_id, is_vm)[0]["release"]

    # pylint: disable=R0914,R0912,R0915
    def init(
            self, name, release, ephemeral=False, network=None, storage=None,
            inst_type=None, profile_list=None, user_data=None,
            config_dict=None, is_vm=False):
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
            user_data: used by cloud-init to run custom scripts/configuration
            config_dict: dict, optional, configuration values to pass
            is_vm: boolean, optional, defines if a virtual machine will
                   be created

        Returns:
            The created LXD instance object

        """
        profile_list = profile_list if profile_list else []
        config_dict = config_dict if config_dict else {}

        if ':' not in release:
            release = self._daily_remote + ':' + release

        self._log.debug("Full release to launch: '%s'", release)
        cmd = ['lxc', 'init', release]

        if name:
            cmd.append(name)

        if is_vm:
            cmd.append('--vm')
            base_release = self._extract_release_from_image_id(release, is_vm)

            if not profile_list:
                profile_name = "pycloudlib-vm-{}".format(base_release)

                self.create_profile(
                    profile_name=profile_name,
                    profile_config=base_vm_profiles[base_release]
                )

                profile_list = [profile_name]

        if self.key_pair:
            pub_key = self.key_pair.public_key_content

            # When we create keys through paramiko, we end up not
            # having the key type on the public key content. Because
            # of that, we are manually adding the ssh-rsa type into it
            if "ssh-" not in pub_key:
                pub_key = "ssh-rsa {}".format(pub_key)

            ssh_user_data = textwrap.dedent(
                """\
                ssh_authorized_keys:
                    - {}
                """.format(pub_key)
            )

            if user_data:
                user_data += "\n{}".format(ssh_user_data)

            if "user.user-data" in config_dict:
                config_dict["user.user-data"] += "\n{}".format(ssh_user_data)

            if not user_data and "user.user-data" not in config_dict:
                user_data = "#cloud-config\n{}".format(ssh_user_data)

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

        for profile in profile_list:
            cmd.append('--profile')
            cmd.append(profile)

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

        return LXDInstance(name, self.key_pair)

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

    def released_image(self, release, arch=LOCAL_UBUNTU_ARCH, is_vm=False):
        """Find the LXD fingerprint of the latest released image.

        Args:
            release: string, Ubuntu release to look for
            arch: string, architecture to use
            is_vm: boolean, specify if the image_id represents a
                   virtual machine

        Returns:
            string, LXD fingerprint of latest image

        """
        self._log.debug('finding released Ubuntu image for %s', release)
        return self._search_for_image(
            remote=self._releases_remote,
            daily=False,
            release=release,
            arch=arch,
            is_vm=is_vm
        )

    def daily_image(self, release, arch=LOCAL_UBUNTU_ARCH, is_vm=False):
        """Find the LXD fingerprint of the latest daily image.

        Args:
            release: string, Ubuntu release to look for
            arch: string, architecture to use
            is_vm: boolean, specify if the image_id represents a
                   virtual machine

        Returns:
            string, LXD fingerprint of latest image

        """
        self._log.debug('finding daily Ubuntu image for %s', release)
        return self._search_for_image(
            remote=self._daily_remote,
            daily=True,
            release=release,
            arch=arch,
            is_vm=is_vm
        )

    def _search_for_image(
        self, remote, daily, release, arch=LOCAL_UBUNTU_ARCH, is_vm=False
    ):
        """Find the LXD fingerprint in a given remote.

        Args:
            remote: string, remote to prepend to image_id
            daily: boolean, search on daily remote
            release: string, Ubuntu release to look for
            arch: string, architecture to use
            is_vm: boolean, specify if the image_id represents a
                   virtual machine

        Returns:
            string, LXD fingerprint of latest image

        """
        if release == "xenial":
            # xenial needs to launch images:ubuntu/16.04/cloud
            # because it contains the HWE kernel which has vhost-vsock support
            return self.XENIAL_IMAGE_VSOCK_SUPPORT

        if is_vm and release == "trusty":
            # trusty is not supported on LXD vms
            raise UnsupportedReleaseException(
                release="trusty",
                is_vm=is_vm
            )

        image_data = self._find_image(release, arch, daily=daily)

        if is_vm:
            image_hash_key = self.VM_HASH_KEY
        elif release == "trusty":
            image_hash_key = self.TRUSTY_CONTAINER_HASH_KEY
        else:
            image_hash_key = self.CONTAINER_HASH_KEY

        return '%s:%s' % (remote, image_data[image_hash_key])

    def _image_info(self, image_id, is_vm=False):
        """Find the image serial of a given LXD image.

        Args:
            image_id: string, LXD image fingerprint
            is_vm: boolean, specify if the image_id represents a
                   virtual machine

        Returns:
            dict, image info available for the image_id

        """
        daily = True
        if ':' in image_id:
            remote = image_id[:image_id.index(':')]
            image_id = image_id[image_id.index(':')+1:]
            if remote == self._releases_remote:
                daily = False
            elif remote != self._daily_remote:
                raise RuntimeError('Unknown remote: %s' % remote)

        if is_vm:
            image_hash_key = self.VM_HASH_KEY
        else:
            image_hash_key = self.CONTAINER_HASH_KEY

        filters = ['%s=%s' % (image_hash_key, image_id)]
        image_info = self._streams_query(filters, daily=daily)

        if not image_info:
            # If this is a trusty image, the hash key for it is different.
            # We will perform a second query for this situation.
            filters = ['%s=%s' % (self.TRUSTY_CONTAINER_HASH_KEY, image_id)]
            image_info = self._streams_query(filters, daily=daily)

        return image_info

    def image_serial(self, image_id, is_vm=False, **kwargs):
        """Find the image serial of a given LXD image.

        Args:
            image_id: string, LXD image fingerprint
            is_vm: boolean, specify if the image_id represents a
                   virtual machine

        Returns:
            string, serial of latest image

        """
        self._log.debug(
            'finding image serial for LXD Ubuntu image %s', image_id)

        image_info = self._image_info(image_id, is_vm=is_vm)

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
