# This file is part of pycloudlib. See LICENSE file for license information.
"""LXD instance."""

import json

from pycloudlib.instance import BaseInstance
from pycloudlib.util import subp


class KVMInstance(BaseInstance):
    """KVM backed instance."""

    _type = 'kvm'

    def __init__(self, name):
        """Set up instance.

        Args:
            name: name of instance
        """
        super().__init__(key_pair=None)

        self._name = name

    def __repr__(self):
        """Create string representation for class."""
        return '{}(name={})'.format(self.__class__.__name__, self.name)

    def _run_command(self, command, stdin):
        """Run command in the instance."""
        # multipass handling of redirects is buggy, so we don't bind
        # stdin to /dev/null for the moment (shortcircuit_stdin=False).
        # See: https://github.com/CanonicalLtd/multipass/issues/667
        base_cmd = ['multipass', 'exec', self.name, '--']
        return subp(
            base_cmd + list(command), rcs=None, shortcircuit_stdin=False
        )

    @property
    def name(self):
        """Return instance name."""
        return self._name

    @property
    def ip(self):
        """Return IP address of instance."""
        raise NotImplementedError

    @property
    def state(self):
        """Return current status of instance.

        If unable to get status will return 'Unknown'.

        Returns:
            Reported status from lxc info

        """
        result = subp(['multipass', 'info', '--format', 'json', self.name])
        info = json.loads(result)
        state = info['info'][self.name]['state']
        return state

    def console_log(self):
        """Return console log.

        Returns:
            bytes of this instance's console

        """
        raise NotImplementedError

    def delete(self, wait=True):
        """Delete and purge the current instance.

        Args:
            wait: wait for delete
        """
        if not wait:
            raise ValueError(
                'wait=False not supported for KVM instance delete'
            )
        self._log.debug('deleting %s', self.name)
        subp(['multipass', 'delete', '--purge', self.name])

    def pull_file(self, remote_path, local_path):
        """Pull file from an instance.

        Args:
            remote_path: path to remote file to pull down
            local_path: local path to put the file
        """
        self._log.debug('pulling file %s to %s', remote_path, local_path)
        result = subp(['multipass', 'transfer', '%s:%s' %
                       (self.name, remote_path), local_path])
        if result.failed:
            raise RuntimeError(result.stderr)

    def push_file(self, local_path, remote_path):
        """Push file to an instance.

        The remote path must be absolute path with LXD due to the way
        files are pulled off. Specifically, the format is 'name/path'
        with path assumed to start from '/'.

        Args:
            local_path: local path to file to push up
            remote_path: absolute path to push file
        """
        self._log.debug('pushing file %s to %s', local_path, remote_path)
        result = subp(['multipass', 'transfer', local_path,
                       '%s:%s' % (self.name, remote_path)])
        if result.failed:
            raise RuntimeError(result.stderr)

    def restart(self, wait=True, **kwargs):
        """Restart an instance."""
        self._log.debug('restarting %s', self.name)
        subp(['multipass', 'restart', self.name])

    def shutdown(self, wait=True, **kwargs):
        """Shutdown instance.

        Args:
            wait: boolean, wait for instance to shutdown
        """
        if not wait:
            raise ValueError(
                'wait=False not supported for KVM instance shutdown'
            )
        if self.state == 'Stopped':
            return

        self._log.debug('shutting down %s', self.name)
        subp(['multipass', 'stop', self.name])

    def start(self, wait=True):
        """Start instance.

        Args:
            wait: boolean, wait for instance to fully start
        """
        if self.state == 'Running':
            return

        self._log.debug('starting %s', self.name)
        subp(['multipass', 'start', self.name])

        if wait:
            self.wait()

    def wait_for_delete(self):
        """Wait for delete.

        Not used for KVM.
        """
        raise NotImplementedError

    def wait_for_stop(self):
        """Wait for stop.

        Not used for KVM.
        """
        raise NotImplementedError
