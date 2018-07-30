# This file is part of pycloudlib. See LICENSE file for license information.
"""LXD instance."""
import re

from pycloudlib.base_instance import BaseInstance
from pycloudlib.exceptions import InTargetExecuteError
from pycloudlib.util import shell_quote, subp


class LXDInstance(BaseInstance):
    """LXD backed instance."""

    def __init__(self, name):
        """Set up instance.

        Args:
            name: name of instance
        """
        super(LXDInstance, self).__init__(key_pair=None)

        self.name = name

    @property
    def ephemeral(self):
        """Return boolean if ephemeral or not.

        Will return False if unknown.

        Returns:
            boolean if ephemeral

        """
        out, _, _ = subp(['lxc', 'info', self.name])

        try:
            info_type = re.findall(r'Type: (.*)', out.decode())[0]
        except IndexError:
            return False

        return True if info_type == 'ephemeral' else False

    @property
    def state(self):
        """Return current status of instance.

        If unable to get status will return 'Unknown'.

        Returns:
            Reported status from lxc info

        """
        out, _, _ = subp(['lxc', 'info', self.name])
        try:
            return re.findall(r'Status: (.*)', out.decode())[0]
        except IndexError:
            return 'Unknown'

    def console_log(self):
        """Return console log.

        Uses the '--show-log' option of console to get the console log
        from an instance.

        Returns:
            bytes of this instance's console

        """
        self._log.debug('getting console log for %s', self.name)
        out, _, _ = subp(['lxc', 'console', self.name, '--show-log'])
        return out

    def delete(self, wait=True):
        """Delete the current instance.

        By default this will use the '--force' option to prevent the
        need to always stop the instance first. This makes it easier
        to work with ephemeral instances as well, which are deleted
        on stop.

        Args:
            wait: wait for delete
        """
        self._log.debug('deleting %s', self.name)
        subp(['lxc', 'delete', self.name, '--force'])

        if wait:
            self.wait_for_delete()

    def delete_snapshot(self, snapshot_name):
        """Delete a snapshot of the instance.

        Args:
            snapshot_name: the name to delete
        """
        self._log.debug('deleting snapshot %s/%s', self.name, snapshot_name)
        subp(['lxc', 'delete', '%s/%s' % (self.name, snapshot_name)])

    def edit(self, key, value):
        """Edit the config of the instance.

        Args:
            key: The config key to edit
            value: The new value to set the key to
        """
        self._log.debug('editing %s with %s=%s', self.name, key, value)
        subp(['lxc', 'config', 'set', self.name, key, value])

    def execute(self, command, rcs=None, description=None):
        """Execute command in instance, recording output, error and exit code.

        Assumes functional networking and execution with the target filesystem
        being available at /.

        Args:
            command: the command to execute as root inside the image. If
                     command is a string, then it will be executed as:
                     `['sh', '-c', command]`
            rcs: return codes can be one of:

                    * None (default): non-zero exit code will raise exception.
                    * False: any is allowed (No execption raised).
                    * list of int: any rc not in the list will raise exception.
            description: purpose of command

        Returns:
            tuple containing stdout data, stderr data, exit code

        """
        if isinstance(command, str):
            command = ['sh', '-c', command]

        if rcs is None:
            rcs = (0,)

        if description:
            self._log.debug(description)
        else:
            self._log.debug('executing: %s', shell_quote(command))

        base_cmd = ['lxc', 'exec', self.name, '--']
        out, err, return_code = subp(base_cmd + list(command))

        # False means accept anything.
        if (rcs is False or return_code in rcs):
            return out, err, return_code

        raise InTargetExecuteError(command, out, err, return_code)

    def pull_file(self, remote_path, local_path):
        """Pull file from an instance.

        The remote path must be absolute path with LXD due to the way
        files are pulled off. Specifically, the format is 'name/path'
        with path assumed to start from '/'.

        Args:
            remote_path: absolute path to remote file to pull down
            local_path: local path to put the file
        """
        self._log.debug('pulling file %s to %s', remote_path, local_path)
        subp(['lxc', 'file', 'pull', '%s%s' % (self.name, remote_path),
              local_path])

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
        subp(['lxc', 'file', 'push', local_path,
              '%s%s' % (self.name, remote_path)])

    def restart(self):
        """Restart an instance.

        For LXD this means stopping the instance, and then starting it.
        """
        self._log.debug('restarting %s', self.name)
        self.shutdown(wait=True)
        self.start(wait=True)

    def restore(self, snapshot_name):
        """Restore instance from a specific snapshot.

        Args:
            snapshot_name: Name of snapshot to restore from
        """
        self._log.debug('restoring %s from snapshot %s',
                        self.name, snapshot_name)
        subp(['lxc', 'restore', self.name, snapshot_name])

    def shutdown(self, wait=True):
        """Shutdown instance.

        Args:
            wait: boolean, wait for instance to shutdown
        """
        if self.state == 'Stopped':
            return

        self._log.debug('shutting down %s', self.name)
        subp(['lxc', 'stop', self.name, '--force'])

        if wait:
            self.wait_for_stop()

    def snapshot(self, snapshot_name, stateful=False):
        """Create a snapshot from the instance.

        Args:
            snapshot_name: name to call snapshot
            stateful: boolean, stateful snapshot or not
        """
        self.clean()
        self.shutdown()

        cmd = ['lxc', 'snapshot', self.name, snapshot_name]
        if stateful:
            cmd.append('--stateful')

        self._log.debug('creating snapshot %s', snapshot_name)
        subp(cmd)

    def start(self, wait=True):
        """Start instance.

        Args:
            wait: boolean, wait for instance to fully start
        """
        if self.state == 'Running':
            return

        self._log.debug('starting %s', self.name)
        subp(['lxc', 'start', self.name])

        if wait:
            self.wait()

    def wait(self):
        """Wait for instance to be up and cloud-init to be complete."""
        self._wait_for_system()

    def wait_for_delete(self):
        """Wait for delete.

        Not used for LXD.
        """
        pass

    def wait_for_stop(self):
        """Wait for stop.

        Not used for LXD.
        """
        pass
