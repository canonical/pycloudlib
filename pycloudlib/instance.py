# This file is part of pycloudlib. See LICENSE file for license information.
"""Base class for all instances to provide consistent set of functions."""

from abc import ABC, abstractmethod, abstractproperty
import logging
import time

import paramiko
from paramiko.ssh_exception import (
    AuthenticationException,
    BadHostKeyException,
    NoValidConnectionsError,
    PasswordRequiredException,
    SSHException
)

from pycloudlib.result import Result
from pycloudlib.util import shell_quote, shell_pack


class BaseInstance(ABC):
    """Base instance object."""

    _type = 'base'

    def __init__(self, key_pair):
        """Set up instance."""
        self._log = logging.getLogger(__name__)
        self._ssh_client = None
        self._sftp_client = None
        self._tmp_count = 0

        self.boot_timeout = 120
        self.key_pair = key_pair
        self.port = '22'
        self.username = 'ubuntu'
        self.connect_timeout = 60

    @property
    @abstractmethod
    def name(self):
        """Return instance name."""
        raise NotImplementedError

    @abstractproperty
    def ip(self):
        """Return IP address of instance."""
        raise NotImplementedError

    @abstractmethod
    def console_log(self):
        """Return the instance console log."""
        raise NotImplementedError

    @abstractmethod
    def delete(self, wait=True):
        """Delete the instance.

        Args:
            wait: wait for instance to be deleted
        """
        raise NotImplementedError

    @abstractmethod
    def restart(self, wait=True, **kwargs):
        """Restart an instance."""
        raise NotImplementedError

    @abstractmethod
    def shutdown(self, wait=True, **kwargs):
        """Shutdown the instance.

        Args:
            wait: wait for the instance to shutdown
        """
        raise NotImplementedError

    @abstractmethod
    def start(self, wait=True):
        """Start the instance.

        Args:
            wait: wait for the instance to start.
        """
        raise NotImplementedError

    def _wait_for_instance_start(self):
        """Wait for the cloud instance to be up.

        Subclasses should implement this if their cloud provides a way of
        detecting when an instance has started through their API.
        """

    def wait(self):
        """Wait for instance to be up and cloud-init to be complete."""
        self._wait_for_instance_start()
        self._wait_for_execute()
        self._wait_for_cloudinit()

    @abstractmethod
    def wait_for_delete(self):
        """Wait for instance to be deleted."""
        raise NotImplementedError

    @abstractmethod
    def wait_for_stop(self):
        """Wait for instance stop."""
        raise NotImplementedError

    def __del__(self):
        """Cleanup of instance."""
        if self._sftp_client:
            try:
                self._sftp_client.close()
            except SSHException:
                self._log.warning('Failed to close SFTP connection.')
            self._sftp_client = None
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
        self.execute('sudo cloud-init clean --logs')
        self.execute('sudo rm -rf /var/log/syslog')

    def _run_command(self, command, stdin):
        """Run command in the instance."""
        return self._ssh(list(command), stdin=stdin)

    def execute(self, command, stdin=None, description=None, *, use_sudo=False,
                **kwargs):
        """Execute command in instance, recording output, error and exit code.

        Assumes functional networking and execution with the target filesystem
        being available at /.

        Args:
            command: the command to execute as root inside the image. If
                     command is a string, then it will be executed as:
                     `['sh', '-c', command]`
            stdin: bytes content for standard in
            description: purpose of command
            use_sudo: boolean to run the command as sudo

        Returns:
            Result object

        """
        if isinstance(command, str):
            command = ['sh', '-c', command]
        if use_sudo:
            command = ['sudo', '--'] + command

        self._log.info('executing: %s', shell_quote(command))
        if description:
            self._log.debug(description)
        else:
            self._log.debug('executing: %s', shell_quote(command))

        return self._run_command(command, stdin, **kwargs)

    def install(self, packages):
        """Install specific packages.

        Args:
            packages: string or list of package(s) to install

        Returns:
            result from install

        """
        if isinstance(packages, str):
            packages = packages.split(' ')

        self.execute(['sudo', 'apt-get', 'update'])
        return self.execute(
            [
                'DEBIAN_FRONTEND=noninteractive',
                'sudo', 'apt-get', 'install', '--yes'
            ] + packages
        )

    def pull_file(self, remote_path, local_path):
        """Copy file at 'remote_path', from instance to 'local_path'.

        Args:
            remote_path: path on remote instance
            local_path: local path
        """
        self._log.debug('pulling file %s to %s', remote_path, local_path)

        sftp = self._sftp_connect()
        sftp.get(remote_path, local_path)

    def push_file(self, local_path, remote_path):
        """Copy file at 'local_path' to instance at 'remote_path'.

        Args:
            local_path: local path
            remote_path: path on remote instance
        """
        self._log.debug('pushing file %s to %s', local_path, remote_path)

        sftp = self._sftp_connect()
        sftp.put(local_path, remote_path)

    def run_script(self, script, description=None):
        """Run script in target and return stdout.

        Args:
            script: script contents
            description: purpose of script

        Returns:
            result from script execution

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

    def update(self):
        """Run apt-get update/upgrade on instance.

        Returns:
            result from upgrade

        """
        self.execute(['sudo', 'apt-get', 'update'])
        return self.execute([
            'DEBIAN_FRONTEND=noninteractive',
            'sudo', 'apt-get', '--yes', 'upgrade'
        ])

    def _ssh(self, command, stdin=None):
        """Run a command via SSH.

        Args:
            command: string or list of the command to run
            stdin: optional, values to be passed in

        Returns:
            tuple of stdout, stderr and the return code

        """
        cmd = shell_pack(command)
        for _ in range(10):
            try:
                client = self._ssh_connect()
                fp_in, fp_out, fp_err = client.exec_command(cmd)
                break
            except (ConnectionResetError, NoValidConnectionsError) as e:
                last_error = e
        else:
            raise last_error  # noqa
        channel = fp_in.channel

        if stdin is not None:
            fp_in.write(stdin)
            fp_in.close()

        channel.shutdown_write()

        out = fp_out.read()
        err = fp_err.read()
        return_code = channel.recv_exit_status()

        out = '' if not out else out.rstrip().decode("utf-8")
        err = '' if not err else err.rstrip().decode("utf-8")

        return Result(out, err, return_code)

    def _ssh_connect(self):
        """Connect to instance via SSH."""
        if self._ssh_client and self._ssh_client.get_transport().is_active():
            return self._ssh_client

        logging.getLogger("paramiko").setLevel(logging.INFO)
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Paramiko can barf on valid keys when initializing this way,
        # so the check here is _only_ for checking if we have a
        # password protected keyfile. The filename is passed directly
        # when connecting
        try:
            paramiko.RSAKey.from_private_key_file(
                self.key_pair.private_key_path)
        except PasswordRequiredException:
            self._log.warning(
                "The specified key (%s) requires a passphrase. If you have not"
                " added this key to a running SSH agent, you will see failures"
                " to connect after a long timeout.",
                self.key_pair.private_key_path,
            )
        except SSHException:
            pass

        start = time.time()
        end = start + 600
        last_exception = None
        while True:
            try:
                client.connect(
                    username=self.username,
                    hostname=self.ip,
                    port=int(self.port),
                    timeout=self.connect_timeout,
                    key_filename=self.key_pair.private_key_path,
                )
                self._ssh_client = client
                return client
            except (ConnectionRefusedError, AuthenticationException,
                    BadHostKeyException, ConnectionResetError, SSHException,
                    OSError) as e:
                last_exception = e
            if time.time() > end:
                break
            self._log.info(
                "%s\nRetrying SSH connection to %s@%s:%s (%ds left)",
                last_exception, self.username, self.ip, self.port,
                end - time.time()
            )
            time.sleep(1)

        self._log.error('Failed ssh connection to %s@%s:%s after 10 minutes',
                        self.username, self.ip, self.port)
        raise last_exception

    def _sftp_connect(self):
        """Connect to instance via SFTP."""
        if (self._sftp_client and
                self._sftp_client.get_channel().get_transport().is_active()):
            return self._sftp_client

        logging.getLogger("paramiko").setLevel(logging.INFO)

        # _ssh_connect() implements the required retry logic.
        client = self._ssh_connect()
        sftpclient = client.open_sftp()
        self._sftp_client = sftpclient
        return sftpclient

    def _tmpfile(self):
        """Get a tmp file in the target.

        Returns:
            path to new file in target

        """
        path = "/tmp/%s-%04d" % (type(self).__name__, self._tmp_count)
        self._tmp_count += 1
        return path

    def _wait_for_execute(self):
        """Wait until we can execute a command in the instance."""
        self._log.debug('_wait_for_execute to complete')

        test_instance_command = "whoami"
        result = self.execute(test_instance_command)
        if result.failed:
            retries = 100
            while retries:
                result = self.execute(test_instance_command)

                if result.ok:
                    break

                retries -= 1
                time.sleep(1)

        if result.failed:
            raise OSError(
                "{}\n{}".format(
                    "Instance can't be reached",
                    "Failed to execute {} command".format(
                        test_instance_command)
                )
            )

    def _wait_for_cloudinit(self):
        """Wait until cloud-init has finished."""
        self._log.debug('_wait_for_cloudinit to complete')

        result = self.execute("cloud-init status --help")
        has_wait = "--wait" in result.stdout

        if has_wait:
            cmd = ["cloud-init", "status", "--wait", "--long"]
        else:
            # runlevel 'N 2' supports distros without recent cloud-init
            # (e.g. trusty).
            runlevel_result = (
                '[ "$(runlevel)" = "N 2" ] && '
                "[ -f /run/cloud-init/result.json ]"
            )
            cmd = (
                "i=0; while [ $i -lt {} ] && i=$(($i+1)); do {} && exit 0;"
                " sleep 1; done; exit 1".format(
                    self.boot_timeout, runlevel_result
                )
            )
        result = self.execute(cmd, description='waiting for start')
