# This file is part of pycloudlib. See LICENSE file for license information.
"""GCP instance."""

from pycloudlib.base_instance import BaseInstance
from pycloudlib.exceptions import NullInstanceError


class GCPInstance(BaseInstance):
    """GCP backed instance."""

    boot_timeout = 120
    platform_name = "GCE"
    _ssh_client = None
    _tmp_count = 0

    def __init__(self, client, key_pair, instance):
        """Set up instance.

        Args:
            client: GCP client object
            key_pair: SSH key object
            instance: created boto3 instance object
        """
        super().__init__(key_pair)

        self._instance = instance
        self._ip = None
        self._client = client

    @property
    def ip(self):
        """Return IP address of instance."""
        pass

    @property
    def id(self):
        """Return id of instance."""
        pass

    @property
    def image_id(self):
        """Return id of instance."""
        pass

    def console_log(self):
        """Collect console log from instance.

        The console log is buffered and not always present, therefore
        may return empty string.

        Returns:
            The console log or error message

        """
        pass

    def delete(self, wait=True):
        """Delete instance."""
        self._log.debug('deleting instance %s', self._instance.id)
        self._instance.terminate()

        if wait:
            self.wait_for_delete()

    def start(self, wait=True):
        """Start the instance.

        Args:
            wait: wait for the instance to start.
        """
        if not self._instance:
            raise NullInstanceError
        if self._instance.state['Name'] == 'running':
            return

        self._log.debug('starting instance %s', self._instance.id)
        self._instance.start()

        if wait:
            self.wait()

    def stop(self, wait=True):
        """Stop the instance.

        Args:
            wait: wait for the instance to stop
        """
        self._log.debug('stopping instance %s', self._instance.id)
        self._instance.stop()

        if wait:
            self.wait_for_stop()

    def wait(self):
        """Wait for instance to be up and cloud-init to be complete."""
        self._instance.wait_until_running()
        self._instance.reload()
        self._wait_for_system()

    def wait_for_delete(self):
        """Wait for instance to be deleted."""
        self._instance.wait_until_terminated()
        self._instance.reload()

    def wait_for_stop(self):
        """Wait for instance stop."""
        self._instance.wait_until_stopped()
        self._instance.reload()
