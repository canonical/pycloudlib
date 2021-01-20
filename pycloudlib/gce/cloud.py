# This file is part of pycloudlib. See LICENSE file for license information.
"""GCE Cloud type.

This is an initial implimentation of the GCE class. It enables
authentication into the cloud, finding an image, and launching an
instance. It however, does not allow any further actions from occuring.
"""

import logging
import os
import time
from itertools import count

import googleapiclient.discovery

from pycloudlib.cloud import BaseCloud
from pycloudlib.gce.util import raise_on_error
from pycloudlib.gce.instance import GceInstance
from pycloudlib.util import subp


logging.getLogger('googleapiclient.discovery').setLevel(logging.WARNING)


class GCE(BaseCloud):
    """GCE Cloud Class."""

    _type = 'gce'

    def __init__(
        self, tag, timestamp_suffix=True, credentials_path=None, project=None,
        region="us-west2", zone="a"
    ):
        """Initialize the connection to GCE.

        Args:
            tag: string used to name and tag resources with
            timestamp_suffix: bool set True to append a timestamp suffix to the
                tag
            credentials_path: path to credentials file for GCE
            project: GCE project
            region: GCE region
            zone: GCE zone
        """
        super().__init__(tag, timestamp_suffix)
        self._log.debug('logging into GCE')

        if credentials_path:
            os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(
                credentials_path)

        if project:
            os.environ["GOOGLE_CLOUD_PROJECT"] = str(project)
        else:
            command = ['gcloud', 'config', 'get-value', 'project']
            exception_text = (
                "Could not obtain GCE project id. Has the CLI client been "
                "setup?\nCommand attempted: '{}'".format(' '.join(command))
            )
            try:
                result = subp(command, rcs=())
            except FileNotFoundError as e:
                raise Exception(exception_text) from e
            if not result.ok:
                exception_text += '\nstdout: {}\nstderr: {}'.format(
                    result.stdout, result.stderr)
                raise Exception(exception_text)
            project = result.stdout

        # disable cache_discovery due to:
        # https://github.com/google/google-api-python-client/issues/299
        self.compute = googleapiclient.discovery.build(
            'compute', 'v1', cache_discovery=False
        )
        self.project = project
        self.region = region
        self.zone = '%s-%s' % (region, zone)
        self.instance_counter = count()

    def _find_image(self, release, daily, arch='amd64'):
        images = self._image_list(release, daily, arch)

        image_id = None
        try:
            image_id = images[0]['id']
        except IndexError:
            Exception('No images found')

        return 'projects/ubuntu-os-cloud-devel/global/images/%s' % image_id

    def released_image(self, release, arch='amd64'):
        """ID of the latest released image for a particular release.

        Args:
            release: The release to look for
            arch: string, architecture to use

        Returns:
            A single string with the latest released image ID for the
            specified release.
        """
        return self.daily_image(release, arch)

    def daily_image(self, release, arch='amd64'):
        """Find the id of the latest image for a particular release.

        Args:
            release: string, Ubuntu release to look for
            arch: string, architecture to use

        Returns:
            string, path to latest daily image

        """
        self._log.debug('finding daily Ubuntu image for %s', release)
        return self._find_image(release, daily=True, arch=arch)

    def image_serial(self, image_id):
        """Find the image serial of the latest daily image for a particular release.

        Args:
            image_id: string, Ubuntu image id

        Returns:
            string, serial of latest image

        """
        raise NotImplementedError

    def delete_image(self, image_id):
        """Delete an image.

        Args:
            image_id: string, id of the image to delete
        """
        api_image_id = self.compute.images().get(
            project=self.project,
            image=os.path.basename(image_id)
        ).execute()['id']
        response = self.compute.images().delete(
            project=self.project,
            image=api_image_id,
        ).execute()

        raise_on_error(response)

    def get_instance(self, instance_id, name=None):
        """Get an instance by id.

        Args:
            instance_id: The instance ID returned upon creation

        Returns:
            An instance object to use to manipulate the instance further.

        """
        return GceInstance(self.key_pair, instance_id,
                           self.project, self.zone, name)

    def launch(self, image_id, instance_type='n1-standard-1', user_data=None,
               wait=True, **kwargs):
        """Launch instance on GCE and print the IP address.

        Args:
            image_id: string, image ID for instance to use
            instance_type: string, instance type to launch
            user_data: string, user-data to pass to instance
            wait: boolean, wait for instance to come up
            kwargs: other named arguments to add to instance JSON

        """
        instance_name = 'i{}-{}'.format(next(self.instance_counter), self.tag)
        config = {
            'name': instance_name,
            'machineType': 'zones/%s/machineTypes/%s' % (
                self.zone, instance_type
            ),
            'disks': [{
                'boot': True,
                'autoDelete': True,
                'initializeParams': {
                    'sourceImage': image_id,
                }
            }],
            'networkInterfaces': [{
                'network': 'global/networks/default',
                'accessConfigs': [
                    {'type': 'ONE_TO_ONE_NAT', 'name': 'External NAT'}
                ]
            }],
            "metadata": {
                "items": [{
                    "key": "ssh-keys",
                    "value": "ubuntu:%s" % self.key_pair.public_key_content,
                }]
            },
        }

        if user_data:
            user_metadata = {
                'key': 'user-data',
                'value': user_data
            }
            config['metadata']['items'].append(user_metadata)

        operation = self.compute.instances().insert(
            project=self.project,
            zone=self.zone,
            body=config
        ).execute()
        raise_on_error(operation)

        self._wait_for_operation(operation, operation_type='zone')

        result = self.compute.instances().get(
            project=self.project,
            zone=self.zone,
            instance=instance_name,
        ).execute()
        raise_on_error(result)

        self._log.info(
            result['networkInterfaces'][0]['accessConfigs'][0]['natIP']
        )

        return self.get_instance(result['id'], name=result['name'])

    def snapshot(self, instance: GceInstance, clean=True, **kwargs):
        """Snapshot an instance and generate an image from it.

        Args:
            instance: Instance to snapshot
            clean: run instance clean method before taking snapshot

        Returns:
            An image id
        """
        response = self.compute.disks().list(
            project=self.project, zone=self.zone
        ).execute()

        instance_disks = [
            disk for disk in response['items'] if disk['name'] == instance.name
        ]

        if len(instance_disks) > 1:
            raise Exception(
                "Snapshotting an image with multiple disks not supported")

        instance.shutdown()

        snapshot_name = '{}-image'.format(instance.name)
        operation = self.compute.images().insert(
            project=self.project,
            body={
                'name': snapshot_name,
                'sourceDisk': instance_disks[0]['selfLink'],
            }
        ).execute()
        raise_on_error(operation)
        self._wait_for_operation(operation)

        return 'projects/{}/global/images/{}'.format(
            self.project, snapshot_name)

    def _image_list(self, release, daily, arch='amd64'):
        """Find list of images with a filter.

        Args:
            release: string, Ubuntu release to look for
            arch: string, architecture to use

        Returns:
            list of dictionaries of images

        """
        filters = [
            'arch=%s' % arch,
            'endpoint=%s' % 'https://www.googleapis.com',
            'region=%s' % self.region,
            'release=%s' % release,
            'virt=kvm'
        ]

        return self._streams_query(filters, daily)

    def _wait_for_operation(self, operation, operation_type='global',
                            sleep_seconds=300):
        response = None
        kwargs = {
            'project': self.project,
            'operation': operation['name']
        }
        if operation_type == 'zone':
            kwargs['zone'] = self.zone
            api = self.compute.zoneOperations()
        else:
            api = self.compute.globalOperations()
        for _ in range(sleep_seconds):
            response = api.get(**kwargs).execute()
            if response['status'] == 'DONE':
                break
            time.sleep(1)
        else:
            raise Exception(
                'Expected DONE state, but found {} after waiting {} seconds. '
                'Check GCE console for more details. \n'
                'Status message: {}'.format(
                    response['status'], sleep_seconds,
                    response['statusMessage']
                )
            )
