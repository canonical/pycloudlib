# This file is part of pycloudlib. See LICENSE file for license information.
"""LXD Cloud type."""

import requests
import yaml

from pycloudlib.cloud import BaseCloud
from pycloudlib.kvm.instance import KVMInstance
from pycloudlib.util import subp
from pycloudlib.constants import LOCAL_UBUNTU_ARCH


class KVM(BaseCloud):  # pylint: disable=W0223
    """KVM Cloud Class."""

    _type = 'kvm'
    _daily_remote = 'daily'
    _releases_remote = 'release'

    def __init__(self, tag):
        """Initialize KVM cloud class.

        Args:
            tag: string used to name and tag resources with
        """
        super().__init__(tag)
        self._instance_types = None

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
            The existing instance as a KVM instance object

        """
        return KVMInstance(instance_name)

    def launch(self, name, release, inst_type=None, wait=True):
        """Set up and launch a container.

        This will init and start a container with the provided settings.
        If no remote is specified pycloudlib defaults to daily images.

        Args:
            name: string, what to call the instance
            release: string, [<remote>:]image, what release to launch
            inst_type: string, type to use
            wait: boolean, wait for instance to start

        Returns:
            The created KVM instance object

        """
        if ':' not in release:
            release = self._daily_remote + ':' + release

        self._log.debug("Full release to launch: '%s'", release)

        cmd = ['multipass', 'launch', '--name', name]

        if inst_type:
            inst_types = self._get_instance_types()
            if inst_type not in inst_types:
                raise RuntimeError('Unknown instance type: %s' % inst_type)
            inst_cpus = str(int(inst_types[inst_type]['cpu']))
            inst_mem = str(int(inst_types[inst_type]['mem']*1024**3))
            self._log.debug(
                "Instance type '%s' => cpus=%s, mem=%s",
                inst_type, inst_cpus, inst_mem)

            cmd += ['--cpus', inst_cpus, '--mem', inst_mem]

        cmd.append(release)

        self._log.debug('Creating %s', name)
        subp(cmd)

        return KVMInstance(name)

    def released_image(self, release, arch=LOCAL_UBUNTU_ARCH):
        """Find the latest released image.

        Args:
            release: string, Ubuntu release to look for

        Returns:
            string, version (serial) of latest image

        """
        self._log.debug('finding released Ubuntu image for %s', release)
        image_data = self._find_image(release, arch, daily=False)
        image = '%s:%s' % (self._releases_remote,
                           image_data['sha256'])
        return image

    def daily_image(self, release, arch=LOCAL_UBUNTU_ARCH):
        """Find the latest daily image.

        Args:
            release: string, Ubuntu release to look for

        Returns:
            string, LXD fingerprint of latest image

        """
        self._log.debug('finding daily Ubuntu image for %s', release)
        image_data = self._find_image(release, arch, daily=True)
        image = '%s:%s' % (self._daily_remote,
                           image_data['sha256'])
        return image

    def image_serial(self, image_id):
        """Find the image serial of a given LXD image.

        Args:
            image_id: string, image version

        Returns:
            string, image serial

        """
        self._log.debug(
            'finding image serial for Ubuntu image %s', image_id)

        daily = True
        if ':' in image_id:
            remote = image_id[:image_id.index(':')]
            image_id = image_id[image_id.index(':')+1:]
            if remote == self._releases_remote:
                daily = False
            elif remote != self._daily_remote:
                raise RuntimeError('Unknown remote: %s' % remote)

        filters = ['sha256=%s' % image_id]
        image_info = self._streams_query(filters, daily=daily)
        return image_info[0]['version_name']

    def purge(self):
        """Purge all deleted instances permanently."""
        self._log.debug('Purging deleted instances')
        subp(['multipass', 'purge'])

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
            'ftype=disk1.img',
            'arch=%s' % arch,
            'release=%s' % release,
        ]

        return self._streams_query(filters, daily)[0]

    def _get_instance_types(self):
        if self._instance_types:
            return self._instance_types

        baseurl = 'https://images.linuxcontainers.org/meta/instance-types/'
        known_clouds = yaml.load(requests.get(baseurl + ".yaml").text)
        self._instance_types = dict()
        for f in known_clouds.values():
            specs = yaml.load(requests.get(baseurl + f).text)
            self._instance_types.update(specs)

        return self._instance_types
