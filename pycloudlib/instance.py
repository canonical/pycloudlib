# This file is part of pycloudlib. See LICENSE file for license information.
# pylint: disable=too-many-public-methods
"""Base class for all instances to provide consistent set of functions."""

import logging
import time
from abc import ABC, abstractmethod
from contextlib import suppress
from typing import List, Optional

import paramiko
from paramiko.ssh_exception import (
    AuthenticationException,
    BadHostKeyException,
    NoValidConnectionsError,
    PasswordRequiredException,
    SSHException,
)

from pycloudlib.errors import CleanupError, PycloudlibTimeoutError
from pycloudlib.result import Result
from pycloudlib.util import log_exception_list, shell_pack, shell_quote


class BaseInstance(ABC):
    """Base instance object."""

    _type = "base"

    def __init__(self, key_pair, username: Optional[str] = None):
        """Set up instance."""
        self._log = logging.getLogger(__name__)
        self._ssh_client = None
        self._sftp_client = None
        self._tmp_count = 0

        self.boot_timeout = 120
        self.key_pair = key_pair
        self.port = "22"
        self.username = username or "ubuntu"
        self.connect_timeout = 60
        self.banner_timeout = 60

    def __enter__(self):
        """Enter context manager for this class."""
        return self

    def __exit__(self, _type, _value, _traceback):
        """Exit context manager for this class."""
        exceptions = self.delete()
        log_exception_list(exceptions)
        if exceptions:
            raise CleanupError(exceptions)

    @property
    @abstractmethod
    def id(self) -> str:
        """Return instance id."""
        raise NotImplementedError

    @property
    @abstractmethod
    def name(self):
        """Return instance name."""
        raise NotImplementedError

    @property
    @abstractmethod
    def ip(self):
        """Return IP address of instance."""
        raise NotImplementedError

    def get_boot_id(self):
        """Get the instance boot_id.

        Returns:
            string with the boot UUID
        """
        result = self.execute(
            "cat /proc/sys/kernel/random/boot_id", no_log=True
        )
        if result.failed:
            raise OSError(
                f"Failed to get boot_id. Return code: {result.return_code}, "
                f"stdout: {result.stdout}, stderr: {result.stderr}"
            )
        return result

    def console_log(self):
        """Return the instance console log.

        Raises NotImplementedError if the cloud does not support fetching the
        console log for this instance.
        """
        raise NotImplementedError

    @abstractmethod
    def delete(self, wait=True) -> List[Exception]:
        """Delete the instance.

        Args:
            wait: wait for instance to be deleted
        """
        raise NotImplementedError

    def restart(self, wait=True, **kwargs):
        """Restart an instance."""
        self._sync_filesystem()
        # If we're not waiting, just call subclass's restart and return.
        if not wait:
            self._do_restart(**kwargs)
            return

        pre_boot_id = None

        # If we attempt to restart, but the instance is already in a
        # non-connectable state, then don't check boot ids.
        try:
            pre_boot_id = self.get_boot_id()
        except (SSHException, OSError):
            # Case 2: wait=True, but the instance is unreachable.
            # The best we can do is to send a reboot signal and wait.
            self._log.debug(
                "Instance seems down; will attempt restart and wait."
            )
            self._do_restart()
            self.wait()
            return

        self._log.debug("Pre-reboot boot_id: %s", pre_boot_id)

        # The instance is reachable, so do the restart and wait for changed
        # boot id
        self._do_restart(**kwargs)
        if wait:
            self.wait_for_restart(old_boot_id=pre_boot_id)

    @abstractmethod
    def _do_restart(self, **kwargs):
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

    def _wait_for_instance_start(self, **kwargs):
        """Wait for the cloud instance to be up.

        Subclasses should implement this if their cloud provides a way of
        detecting when an instance has started through their API.
        """

    def wait(self, **kwargs):
        """Wait for instance to be up and cloud-init to be complete."""
        self._wait_for_instance_start(**kwargs)
        self._wait_for_execute()
        self._wait_for_cloudinit()

    def wait_for_restart(self, old_boot_id):
        """Wait for instance to be restarted and cloud-init to be complete.

        old_boot_id is the boot id prior to restart
        """
        self._wait_for_instance_start()
        self._wait_for_execute(old_boot_id=old_boot_id)
        self._wait_for_cloudinit()

    @abstractmethod
    def wait_for_delete(self, **kwargs):
        """Wait for instance to be deleted."""
        raise NotImplementedError

    @abstractmethod
    def wait_for_stop(self, **kwargs):
        """Wait for instance stop."""
        raise NotImplementedError

    def add_network_interface(self) -> str:
        """Add nic to running instance."""
        raise NotImplementedError

    def remove_network_interface(self, ip_address: str):
        """Remove nic from running instance."""
        raise NotImplementedError

    def __del__(self):
        """Cleanup of instance."""
        if self._sftp_client:
            try:
                self._sftp_client.close()
            except SSHException:
                self._log.warning("Failed to close SFTP connection.")
            self._sftp_client = None
        if self._ssh_client:
            try:
                self._ssh_client.close()
            except SSHException:
                self._log.warning("Failed to close SSH connection.")
            self._ssh_client = None

    def clean(self):
        """Clean an instance to make it look prestine.

        This will clean out specifically the cloud-init files and system logs.
        """
        # Note: revert this commit once bionic-pro images contain
        # cloud-init >= v23.1 .
        # We end up hitting LP: #1508766 on systemd == 237 (bionic) because
        # the cloud-init's fix [1] for LP: #1999680 is not included on some
        # bionic-pro cloud images.
        #
        # [1] https://github.com/canonical/cloud-init/commit/abfdf1d83995cc20e
        self.execute("sudo cloud-init clean --logs")
        self.execute("sudo echo 'uninitialized' > /etc/machine-id")
        self.execute("sudo rm -rf /var/log/syslog")

    def _run_command(self, command, stdin):
        """Run command in the instance."""
        return self._ssh(list(command), stdin=stdin)

    def execute(
        self,
        command,
        stdin=None,
        description=None,
        *,
        use_sudo=False,
        no_log=False,
        **kwargs,
    ):
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

        Raises SSHException if there are any problem with the ssh connection

        """
        if isinstance(command, str):
            command = ["sh", "-c", command]
        if use_sudo:
            command = ["sudo", "--"] + command

        if not no_log:
            self._log.info("executing: %s", shell_quote(command))
            if description:
                self._log.debug(description)
            else:
                self._log.debug("executing: %s", shell_quote(command))

        return self._run_command(command, stdin, **kwargs)

    def install(self, packages):
        """Install specific packages.

        Args:
            packages: string or list of package(s) to install

        Returns:
            result from install

        """
        if isinstance(packages, str):
            packages = packages.split(" ")

        self.execute(["sudo", "apt-get", "update"])
        return self.execute(
            [
                "DEBIAN_FRONTEND=noninteractive",
                "sudo",
                "apt-get",
                "install",
                "--yes",
            ]
            + packages
        )

    def pull_file(self, remote_path, local_path):
        """Copy file at 'remote_path', from instance to 'local_path'.

        Args:
            remote_path: path on remote instance
            local_path: local path

        Raises SSHException if there are any problem with the ssh connection
        """
        self._log.debug("pulling file %s to %s", remote_path, local_path)

        sftp = self._sftp_connect()
        sftp.get(remote_path, local_path)

    def push_file(self, local_path, remote_path):
        """Copy file at 'local_path' to instance at 'remote_path'.

        Args:
            local_path: local path
            remote_path: path on remote instance

        Raises SSHException if there are any problem with the ssh connection
        """
        self._log.debug("pushing file %s to %s", local_path, remote_path)

        sftp = self._sftp_connect()
        sftp.put(local_path, remote_path)

    def run_script(self, script, description=None):
        """Run script in target and return stdout.

        Args:
            script: script contents
            description: purpose of script

        Returns:
            result from script execution

        Raises SSHException if there are any problem with the ssh connection
        """
        # Just write to a file, add execute, run it, then remove it.
        shblob = "; ".join(
            (
                "set -e",
                's="$1"',
                "shift",
                'cat > "$s"',
                'trap "rm -f $s" EXIT',
                'chmod +x "$s"',
                '"$s" "$@"',
            )
        )
        return self.execute(
            ["sh", "-c", shblob, "runscript", self._tmpfile()],
            stdin=script,
            description=description,
        )

    def update(self):
        """Run apt-get update/upgrade on instance.

        Returns:
            result from upgrade

        """
        self.execute(["sudo", "apt-get", "update"])
        return self.execute(
            [
                "DEBIAN_FRONTEND=noninteractive",
                "sudo",
                "apt-get",
                "--yes",
                "upgrade",
            ]
        )

    def _ssh(self, command, stdin=None):
        """Run a command via SSH.

        Args:
            command: string or list of the command to run
            stdin: optional, values to be passed in

        Returns:
            tuple of stdout, stderr and the return code

        """
        cmd = shell_pack(command)
        client = self._ssh_connect()
        try:
            fp_in, fp_out, fp_err = client.exec_command(cmd)
        except (ConnectionResetError, NoValidConnectionsError, EOFError) as e:
            raise SSHException from e
        channel = fp_in.channel

        if stdin is not None:
            fp_in.write(stdin)
            fp_in.close()

        channel.shutdown_write()

        out = fp_out.read()
        err = fp_err.read()
        return_code = channel.recv_exit_status()

        out = "" if not out else out.rstrip().decode("utf-8")
        err = "" if not err else err.rstrip().decode("utf-8")

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
                self.key_pair.private_key_path
            )
        except PasswordRequiredException:
            self._log.warning(
                "The specified key (%s) requires a passphrase. If you have not"
                " added this key to a running SSH agent, you will see failures"
                " to connect after a long timeout.",
                self.key_pair.private_key_path,
            )
        except SSHException:
            pass

        try:
            client.connect(
                username=self.username,
                hostname=self.ip,
                port=int(self.port),
                timeout=self.connect_timeout,
                banner_timeout=self.banner_timeout,
                key_filename=self.key_pair.private_key_path,
            )
        except (
            ConnectionRefusedError,
            AuthenticationException,
            BadHostKeyException,
            ConnectionResetError,
            SSHException,
            OSError,
        ) as e:
            raise SSHException from e
        self._ssh_client = client
        return client

    def _sftp_connect(self):
        """Connect to instance via SFTP."""
        if (
            self._sftp_client
            and self._sftp_client.get_channel().get_transport().is_active()
        ):
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

    def _wait_for_execute(self, old_boot_id=None):
        """Wait until we can execute a command in the instance.

        If old_boot_id is specified, we use its value to wait until we
        find a new boot id
        """
        self._log.info("_wait_for_execute to complete")

        # Wait 40 minutes before failing. AWS EC2 metal instances can take
        # over 20 minutes to start or restart, so we shouldn't lower
        # this timeout
        start = time.time()
        end = start + 40 * 60
        while time.time() < end:
            with suppress(SSHException, OSError):
                boot_id = self.get_boot_id()
                if not old_boot_id or boot_id != old_boot_id:
                    return
            time.sleep(1)

        raise PycloudlibTimeoutError(
            "Instance can't be reached after 40 minutes. "
            "Failed to obtain new boot id",
        )

    def _wait_for_cloudinit(self):
        """Wait until cloud-init has finished."""
        self._log.info("_wait_for_cloudinit to complete")
        if self.execute("command -v systemctl").ok:
            # We may have issues with cloud-init status early boot, so also
            # ensure our cloud-init.target is active as an extra layer of
            # protection against connecting before the system is ready
            for _ in range(300):
                with suppress(SSHException):
                    if self.execute(
                        ["systemctl", "is-active", "cloud-init.target"],
                        no_log=True,
                    ).ok:
                        break
                time.sleep(1)
        cmd = ["cloud-init", "status", "--wait", "--long"]
        self.execute(cmd, description="waiting for start")

    def _sync_filesystem(self):
        """Sync the filesystem before powering down."""
        with suppress(SSHException):
            self.execute("sync")
