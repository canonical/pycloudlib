# This file is part of pycloudlib. See LICENSE file for license information.
"""Base class for all instances to provide consistent set of functions."""

import logging
import time

import paramiko
from paramiko.ssh_exception import (
    AuthenticationException,
    BadHostKeyException,
    PasswordRequiredException,
    SSHException
)

from pycloudlib.exceptions import (
    InTargetExecuteError,
    SSHEncryptedPrivateKeyError
)
from pycloudlib.util import shell_quote, shell_pack


class BaseInstance:
    """Base instance object."""

    def __init__(self, key_pair):
        """Set up instance."""
        self._log = logging.getLogger(__name__)
        self._ssh_client = None
        self._tmp_count = 0

        self.boot_timeout = 120
        self.key_pair = key_pair
        self.port = '22'
        self.username = 'ubuntu'

    @property
    def ip(self):  # pylint: disable=C0103
        """Return IP address of instance.

        Returns:
            IP address assigned to instance.

        """
        return ''

    def __del__(self):
        """Cleanup of instance."""
        if self._ssh_client:
            try:
                self._ssh_client.close()
            except SSHException:
                self._log.warning('Failed to close SSH connection.')
            self._ssh_client = None

    def clean(self):
        """Clean an instance to make it look prestine.

        This will clean out specifically the cloud-init files and system logs.
        """
        self.execute(
            'sudo rm -rf /var/log/cloud-init.log '
            '/var/log/cloud-init-output.log /var/lib/cloud/ '
            '/run/cloud-init/ /var/log/syslog'
        )

    def console_log(self):
        """Return the instance console log."""
        raise NotImplementedError

    def delete(self, wait=True):
        """Delete the instance.

        Args:
            wait: wait for instance to be deleted
        """
        raise NotImplementedError

    def execute(self, command, stdin=None, description=None):
        """Execute command in instance, recording output, error and exit code.

        Assumes functional networking and execution with the target filesystem
        being available at /.

        Args:
            command: the command to execute as root inside the image. If
                     command is a string, then it will be executed as:
                     `['sh', '-c', command]`
            stdin: bytes content for standard in
            description: purpose of command

        Returns:
            tuple containing stdout data, stderr data, exit code

        """
        if isinstance(command, str):
            command = ['sh', '-c', command]

        if description:
            self._log.debug(description)
        else:
            self._log.debug('executing: %s', shell_quote(command))

        out, err, return_code = self._ssh(list(command), stdin=stdin)

        out = '' if not out else out.rstrip().decode("utf-8")
        err = '' if not err else err.rstrip().decode("utf-8")

        return out, err, return_code

    def install(self, packages):
        """Install specific packages.

        Args:
            packages: string of package(s) to install
        """
        self.execute('sudo apt-get update')
        self.execute('DEBIAN_FRONTEND=noninteractive sudo apt-get '
                     'install -y %s' % packages)

    def pull_file(self, remote_path, local_path, decode=False):
        """Copy file at 'remote_path', from instance to 'local_path'.

        Args:
            remote_path: path on remote instance
            local_path: path on local instance
        """
        # when sh is invoked with '-c', then the first argument is "$0"
        # which is commonly understood as the "program name".
        # 'read_data' is the program name, and 'remote_path' is '$1'
        stdout, _stderr, return_code = self.execute(
            ["sh", "-c", 'exec cat "$1"', 'read_data', remote_path])
        if return_code != 0:
            raise RuntimeError("Failed to read file '%s'" % remote_path)

        if decode:
            stdout = stdout.decode()

        with open(local_path, 'wb') as file:
            file.write(stdout)

    def push_file(self, local_path, remote_path):
        """Copy file at 'local_path' to instance at 'remote_path'.

        Args:
            local_path: path on local instance
            remote_path: path on remote instance
        """
        with open(local_path, "rb") as file:
            # when sh is invoked with '-c', then the first argument is "$0"
            # which is commonly understood as the "program name".
            # 'write_data' is the program name, and 'remote_path' is '$1'
            _, _, return_code = self.execute(
                ["sh", "-c", 'exec cat >"$1"', 'write_data', remote_path],
                stdin=file)

            if return_code != 0:
                raise RuntimeError("Failed to write to '%s'" % remote_path)

    def restart(self):
        """Restart an instance."""
        raise NotImplementedError

    def run_script(self, script, description=None):
        """Run script in target and return stdout.

        Args:
            script: script contents
            description: purpose of script

        Returns:
            stdout from script

        """
        # Just write to a file, add execute, run it, then remove it.
        shblob = '; '.join((
            'set -e',
            's="$1"',
            'shift',
            'cat > "$s"',
            'trap "rm -f $s" EXIT',
            'chmod +x "$s"',
            '"$s" "$@"'))
        return self.execute(
            ['sh', '-c', shblob, 'runscript', self._tmpfile()],
            stdin=script, description=description)

    def shutdown(self, wait=True):
        """Shutdown the instance.

        Args:
            wait: wait for the instance to shutdown
        """
        raise NotImplementedError

    def start(self, wait=True):
        """Start the instance.

        Args:
            wait: wait for the instance to start.
        """
        raise NotImplementedError

    def update(self):
        """Run apt-get update/upgrade on instance."""
        self.execute('sudo apt-get update')
        self.execute('DEBIAN_FRONTEND=noninteractive sudo apt-get -y upgrade')

    def wait(self):
        """Wait for instance to be up and cloud-init to be complete."""
        raise NotImplementedError

    def wait_for_delete(self):
        """Wait for instance to be deleted."""
        raise NotImplementedError

    def wait_for_stop(self):
        """Wait for instance stop."""
        raise NotImplementedError

    def _ssh(self, command, stdin=None):
        """Run a command via SSH.

        Args:
            command: string or list of the command to run
            stdin: optional, values to be passed in

        Returns:
            tuple of stdout, stderr and the return code

        """
        client = self._ssh_connect()

        cmd = shell_pack(command)
        fp_in, fp_out, fp_err = client.exec_command(cmd)
        channel = fp_in.channel

        if stdin is not None:
            fp_in.write(stdin)
            fp_in.close()

        channel.shutdown_write()
        return_code = channel.recv_exit_status()

        return (fp_out.read(), fp_err.read(), return_code)

    def _ssh_connect(self):
        """Connect to instance via SSH."""
        if self._ssh_client and self._ssh_client.get_transport().isAlive():
            return self._ssh_client

        logging.getLogger("paramiko").setLevel(logging.WARNING)
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        try:
            private_key = paramiko.RSAKey.from_private_key_file(
                self.key_pair.private_key_path
            )
        except PasswordRequiredException:
            raise SSHEncryptedPrivateKeyError

        retries = 30
        while retries:
            try:
                client.connect(username=self.username, hostname=self.ip,
                               port=self.port, pkey=private_key)
                self._ssh_client = client
                return client
            except (ConnectionRefusedError, AuthenticationException,
                    BadHostKeyException, ConnectionResetError, SSHException,
                    OSError):
                retries -= 1
                time.sleep(10)

        ssh_cmd = 'Failed ssh connection to %s@%s:%s after 300 seconds' % (
            self.username, self.ip, self.port
        )
        raise InTargetExecuteError(ssh_cmd, b'', b'', 1)

    def _tmpfile(self):
        """Get a tmp file in the target.

        Returns:
            path to new file in target

        """
        path = "/tmp/%s-%04d" % (type(self).__name__, self._tmp_count)
        self._tmp_count += 1
        return path

    def _wait_for_system(self, wait_for_cloud_init=True):
        """Wait until system is fully booted and cloud-init has finished.

        Args:
            wait_for_cloud_init: boolean, wait for cloud-init to complete

        Returns:
            none, may raise OSError if wait_time exceeded

        """
        def clean_test(test):
            """Clean formatting for system ready test testcase."""
            return ' '.join(l for l in test.strip().splitlines()
                            if not l.lstrip().startswith('#'))

        tests = [("[ $(systemctl is-system-running) = 'running' -o "
                  "$(systemctl is-system-running) = 'degraded' ]")]
        if wait_for_cloud_init:
            tests.append("[ -f '/run/cloud-init/result.json' ]")

        formatted_tests = ' && '.join(clean_test(t) for t in tests)
        cmd = (
            'i=0; while [ $i -lt %s ] && i=$(($i+1)); do %s && exit 0;'
            'sleep 1; done; exit 1' % (self.boot_timeout, formatted_tests)
        )

        result = self.execute(cmd, description='waiting for start')
        if result[-1] != 0:
            raise OSError(
                'timeout: after %ss system not started' % self.boot_timeout
            )
