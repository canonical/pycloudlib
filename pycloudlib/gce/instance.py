# This file is part of pycloudlib. See LICENSE file for license information.
"""GCE instance."""

from time import sleep

import googleapiclient.discovery
from googleapiclient.errors import HttpError

from pycloudlib.gce.util import raise_on_error
from pycloudlib.instance import BaseInstance


class GceInstance(BaseInstance):
    """GCE backed instance."""

    _type = 'gce'

    def __init__(self, key_pair, instance_id, project, zone, name=None):
        """Set up the instance.

        Args:
            key_pair: A KeyPair for SSH interactions
            instance_id: Id returned when creating the instance
            project: Project instance was created in
            zone: Zone instance was created in
        """
        if project is None or zone is None:
            raise ValueError("kwargs 'project' and 'zone' are required. "
                             "Project: {}, Zone: {}".format(project, zone))
        super().__init__(key_pair)
        self.instance_id = instance_id
        self._name = name
        self.project = project
        self.zone = zone
        self._ip = None
        self.instance = googleapiclient.discovery.build(
            'compute', 'v1', cache_discovery=False
        ).instances()

    def __repr__(self):
        """Create string representation of class."""
        return '{}(instance_id={})'.format(
            self.__class__.__name__,
            self.instance_id,
        )

    @property
    def id(self):
        """Return the instance id."""
        return self.instance_id

    @property
    def name(self):
        """Return the instance name."""
        if not self._name:
            result = self.instance.get(
                project=self.project,
                zone=self.zone,
                instance=self.instance_id,
            ).execute()
            self._name = result['name']
        return self._name

    @property
    def ip(self):
        """Return IP address of instance."""
        if not self._ip:
            self._ip = self._get_ip()
        return self._ip

    def _get_ip(self):
        result = self.instance.get(
            project=self.project,
            zone=self.zone,
            instance=self.instance_id,
        ).execute()
        ip = result['networkInterfaces'][0]['accessConfigs'][0]['natIP']
        return ip

    def console_log(self):
        """Not currently implemented."""
        raise NotImplementedError

    def delete(self, wait=True):
        """Delete the instance.

        Args:
            wait: wait for instance to be deleted
        """
        response = self.instance.delete(
            project=self.project,
            zone=self.zone,
            instance=self.instance_id
        ).execute()
        raise_on_error(response)
        if wait:
            self.wait_for_delete()

    def restart(self, wait=True):
        """Restart the instance.

        Args:
            wait: wait for the instance to be fully started
        """
        self.shutdown()
        self.start()

    def shutdown(self, wait=True):
        """Shutdown the instance.

        Args:
            wait: wait for the instance to shutdown
        """
        response = self.instance.stop(
            project=self.project,
            zone=self.zone,
            instance=self.instance_id
        ).execute()
        raise_on_error(response)
        if wait:
            self.wait_for_stop()

    def start(self, wait=True):
        """Start the instance.

        Args:
            wait: wait for the instance to start.
        """
        response = self.instance.start(
            project=self.project,
            zone=self.zone,
            instance=self.instance_id
        ).execute()
        raise_on_error(response)
        if wait:
            self.wait()

    def wait(self):
        """Wait for instance to be up."""
        self._wait_for_status('RUNNING')
        self._ip = self._get_ip()
        self._wait_for_system()

    def wait_for_delete(self, sleep_seconds=300):
        """Wait for instance to be deleted."""
        # Once instance is deleted, URL just 404s
        for _ in range(sleep_seconds):
            try:
                self.instance.get(
                    project=self.project,
                    zone=self.zone,
                    instance=self.instance_id
                ).execute()
            except HttpError as e:
                if e.resp.status == 404:
                    break
                raise e
        else:
            raise Exception(
                'Instance not terminated after {} seconds. '
                'Check GCE console.'.format(sleep_seconds)
            )

    def wait_for_stop(self):
        """Wait for instance stop."""
        self._wait_for_status('TERMINATED')

    def _wait_for_status(self, status, sleep_seconds=300):
        response = None
        for _ in range(sleep_seconds):
            response = self.instance.get(
                project=self.project,
                zone=self.zone,
                instance=self.instance_id
            ).execute()
            if response['status'] == status:
                break
            sleep(1)
        else:
            raise Exception(
                'Expected {} state, but found {} after waiting {} seconds. '
                'Check GCE console for more details. \n'
                'Status message: {}'.format(
                    status, response['status'],
                    sleep_seconds, response['statusMessage']
                )
            )
