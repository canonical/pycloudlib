# This file is part of pycloudlib. See LICENSE file for license information.
"""LXD instance."""

import json
import re
import time
from typing import List, Optional

from pycloudlib.errors import PycloudlibTimeoutError
from pycloudlib.instance import BaseInstance
from pycloudlib.util import subp

MISSING_AGENT_MSG = (
    "Many Xenial images do not support `%s` due to missing lxd-agent:"
    " you may see unavoidable failures.\n"
    "See https://github.com/canonical/pycloudlib/issues/132 for details."
)


# pylint: disable=too-many-public-methods
class LXDInstance(BaseInstance):
    """LXD backed instance."""

    _type = "lxd"
    _is_vm = None
    _is_ephemeral = None

    def __init__(
        self,
        name,
        key_pair=None,
        execute_via_ssh=True,
        series=None,
        ephemeral=None,
        *,
        username: Optional[str] = None,
    ):
        """Set up instance.

        Args:
            name: name of instance
            key_pair: SSH key object
            execute_via_ssh: Boolean True to use ssh instead of lxc exec for
                all operations.
            series: Ubuntu release name: xenial, bionic etc.
            ephemeral: Boolean True if instance is ephemeral. If left
                unspecified, ephemeral type will be determined and cached by
                the ephemeral method.
            username: username to use when connecting via SSH
        """
        super().__init__(key_pair=key_pair, username=username)

        self._name = name
        self.execute_via_ssh = execute_via_ssh
        self.series = series
        self._is_ephemeral = ephemeral

    def __repr__(self):
        """Create string representation for class."""
        return "LXDInstance(name={})".format(self.name)

    def _run_command(self, command, stdin):
        """Run command in the instance."""
        if self.execute_via_ssh:
            return super()._run_command(command, stdin)

        base_cmd = [
            "lxc",
            "exec",
            self.name,
            "--",
            "sudo",
            "-u",
            self.username,
            "--",
        ]
        return subp(base_cmd + list(command), rcs=None)

    def parse_ip(self, query: dict):
        """Return ip address from lxd query.

        Returns None if no address found
        """
        ipv6 = []
        network = query.get("state", {}).get("network")
        if network is None:
            network = {}
        for nic_cfg in sorted(
            network.values(),
            # prefer nics with host_name defined
            key=lambda cfg: not cfg.get("host_name"),
        ):
            for addr in nic_cfg["addresses"]:
                if addr.get("scope") != "global":
                    continue
                family = addr.get("family")
                if family == "inet":
                    return addr.get("address")
                if family == "inet6":
                    ipv6.append(addr.get("address"))
        if ipv6:
            return ipv6[0]
        self._log.debug(
            "Unable to find valid IP. Found network: %s",
            network,
        )
        return None

    @property
    def is_vm(self):
        """Return boolean if vm type or not.

        Will return False if unknown.

        Returns:
            boolean if virtual-machine
        """
        if self._is_vm is None:
            result = subp(["lxc", "info", self.name])

            try:
                info_type = re.findall(r"Type: (.*)", result)[0]
            except IndexError:
                return False

            self._is_vm = bool(info_type == "virtual-machine")

        return self._is_vm

    @property
    def id(self) -> str:
        """Return instance id."""
        return self.name

    @property
    def name(self):
        """Return instance name."""
        return self._name

    @property
    def ip(self):
        """Return IP address of instance.

        Returns:
            IP address assigned to instance.

        Raises: PycloudlibTimeoutError when exhausting retries trying to parse
            lxc list for ip addresses.
        """
        retries = 150

        while retries != 0:
            command = [
                "lxc",
                "query",
                f"/1.0/instances/{self.name}?recursion=1",
            ]
            result = subp(command)
            if result.ok and result.stdout:
                try:
                    info = json.loads(result.stdout)
                except ValueError:
                    self._log.debug(
                        "Unable to parse output of cmd: %s. Expected JSON,"
                        " got: %s. Retrying %d time(s)...",
                        command,
                        result.stdout,
                        retries,
                    )
                else:
                    ip = self.parse_ip(info)
                    if ip:
                        return ip
            retries -= 1
            time.sleep(1)
        raise PycloudlibTimeoutError(
            "Unable to determine IP address after 150 retries."
            " exit:{} stdout: {} stderr: {}".format(
                result.return_code, result.stdout, result.stderr
            )
        )

    @property
    def ephemeral(self):
        """Return boolean if ephemeral or not.

        Will return False if unknown.

        Returns:
            boolean if ephemeral
        """
        if self._is_ephemeral is None:
            result = subp(["lxc", "info", self.name])

            try:
                info_type = re.findall(r"Type: (.*)", result)[0]
                self._is_ephemeral = bool("ephemeral" in info_type)
            except IndexError:
                self._log.debug(
                    "Unable to parse lxc show %s to determine ephemeral type."
                    " Assuming not ephemeral.",
                    self.name,
                )
                self._is_ephemeral = False
        return self._is_ephemeral

    @property
    def state(self):
        """Return current status of instance.

        If unable to get status will return 'Unknown'.

        Returns:
            Reported status from lxc info

        """
        result = subp(["lxc", "info", self.name])
        try:
            return re.findall(r"Status: (.*)", result)[0]
        except IndexError:
            return "Unknown"

    def console_log(self):
        """Return console log.

        Uses the '--show-log' option of console to get the console log
        from an instance.

        Returns:
            bytes of this instance's console

        """
        self._log.debug("getting console log for %s", self.name)
        try:
            return subp(["lxc", "console", self.name, "--show-log"])
        except RuntimeError as exc:
            if "Instance is not container type" not in str(exc):
                raise
            # "Instance is not container type" means we don't support console
            # log for this instance: raise NotImplementedError
            raise NotImplementedError from exc

    def delete(self, wait=True) -> List[Exception]:
        """Delete the current instance.

        By default this will use the '--force' option to prevent the
        need to always stop the instance first. This makes it easier
        to work with ephemeral instances as well, which are deleted
        on stop.

        Args:
            wait: wait for delete
        """
        self._log.debug("deleting %s", self.name)

        try:
            subp(["lxc", "delete", self.name, "--force"])
        except RuntimeError as e:
            if "Instance not found" not in str(e):
                return [e]

        if wait:
            self.wait_for_delete()

        return []

    def delete_snapshot(self, snapshot_name):
        """Delete a snapshot of the instance.

        Args:
            snapshot_name: the name to delete
        """
        self._log.debug("deleting snapshot %s/%s", self.name, snapshot_name)
        subp(["lxc", "delete", "%s/%s" % (self.name, snapshot_name)])

    def edit(self, key, value):
        """Edit the config of the instance.

        Args:
            key: The config key to edit
            value: The new value to set the key to
        """
        self._log.debug("editing %s with %s=%s", self.name, key, value)
        subp(["lxc", "config", "set", self.name, key, value])

    def pull_file(self, remote_path, local_path):
        """Pull file from an instance.

        The remote path must be absolute path with LXD due to the way
        files are pulled off. Specifically, the format is 'name/path'
        with path assumed to start from '/'.

        Args:
            remote_path: path to remote file to pull down
            local_path: local path to put the file
        """
        self._log.debug("pulling file %s to %s", remote_path, local_path)

        if self.execute_via_ssh:
            super().pull_file(remote_path, local_path)
            return

        if self.series == "xenial":
            self._log.warning(MISSING_AGENT_MSG, "lxc file pull")

        if remote_path[0] != "/":
            remote_pwd = self.execute("pwd")
            remote_path = remote_pwd + "/" + remote_path
            self._log.debug("Absolute remote path: %s", remote_path)

        subp(
            [
                "lxc",
                "file",
                "pull",
                "%s%s" % (self.name, remote_path),
                local_path,
            ]
        )

    def push_file(self, local_path, remote_path):
        """Push file to an instance.

        The remote path must be absolute path with LXD due to the way
        files are pulled off. Specifically, the format is 'name/path'
        with path assumed to start from '/'.

        Args:
            local_path: local path to file to push up
            remote_path: path to push file
        """
        self._log.debug("pushing file %s to %s", local_path, remote_path)

        if self.execute_via_ssh:
            super().push_file(local_path, remote_path)
            return

        if self.series == "xenial":
            self._log.warning(MISSING_AGENT_MSG, "lxc file push")

        if remote_path[0] != "/":
            remote_pwd = self.execute("pwd")
            remote_path = remote_pwd + "/" + remote_path
            self._log.debug("Absolute remote path: %s", remote_path)

        subp(
            [
                "lxc",
                "file",
                "push",
                local_path,
                "%s%s" % (self.name, remote_path),
            ]
        )

    def _do_restart(self, force=False, **kwargs):
        """Restart an instance.

        Args:
            force: boolean, force instance to shutdown before restart
        """
        self._log.debug("restarting %s", self.name)

        # Note: even if slightly faster in some cases, do not replace
        # `lxc restart` with stop + start, as ephemeral instances do
        # not survive being stopped, while they do survive restarts.
        cmd = ["lxc", "restart", self.name]
        if force:
            cmd.append("--force")
        subp(cmd)

    def restore(self, snapshot_name):
        """Restore instance from a specific snapshot.

        Args:
            snapshot_name: Name of snapshot to restore from
        """
        self._log.debug(
            "restoring %s from snapshot %s", self.name, snapshot_name
        )
        subp(["lxc", "restore", self.name, snapshot_name])

    def shutdown(self, wait=True, force=False, **kwargs):
        """Shutdown instance.

        Args:
            wait: boolean, wait for instance to shutdown
            force: boolean, force instance to shutdown
        """
        if self.state == "Stopped":
            return

        self._log.debug("shutting down %s", self.name)
        cmd = ["lxc", "stop", self.name]

        if force:
            cmd.append("--force")

        subp(cmd)

        if wait:
            self.wait_for_stop()

    def local_snapshot(self, snapshot_name, stateful=False):
        """Create an LXD snapshot (not a launchable image).

        Args:
            snapshot_name: name to call snapshot
            stateful: boolean, stateful snapshot or not
        """
        self.clean()
        self.shutdown()

        if snapshot_name is None:
            snapshot_name = "{}-snapshot".format(self.name)
        cmd = ["lxc", "snapshot", self.name, snapshot_name]
        if stateful:
            cmd.append("--stateful")

        self._log.debug("creating snapshot %s", snapshot_name)
        subp(cmd)
        return snapshot_name

    def snapshot(self, snapshot_name):
        """Create an image snapshot.

        Snapshot is a bit of a misnomer here. Since "snapshot" in the
        context of clouds means "create a launchable container from
        this instance", we actually need to do a publish here. If you
        need the lxd "snapshot" functionality, use local_snapshot

        Args:
            snapshot_name: name to call snapshot
        """
        if not self.ephemeral:
            self.shutdown()
        if snapshot_name is None:
            snapshot_name = "{}-snapshot".format(self.name)
        cmd = [
            "lxc",
            "publish",
            "--force",
            self.name,
            "--alias",
            snapshot_name,
        ]

        self._log.debug("Publishing snapshot %s", snapshot_name)
        subp(cmd)
        return "local:{}".format(snapshot_name)

    def start(self, wait=True):
        """Start instance.

        Args:
            wait: boolean, wait for instance to fully start
        """
        if self.state == "Running":
            return

        self._log.debug("starting %s", self.name)
        subp(["lxc", "start", self.name])

        if wait:
            self.wait()

    def wait_for_delete(self):
        """Wait for delete.

        Not used for LXD.
        """

    def wait_for_state(self, desired_state: str, num_retries: int = 100):
        """Wait for instance to reach desired state value.

        :param desired_state: String representing one of lxc instance states
            seen by `lxc ls -s`. For example, ACTIVE, FROZEN, RUNNING, STOPPED
        :param retries: Integer for number of retry attempts before raising a
            PycloudlibTimeoutError.
        """
        self._log.debug("waiting for %s: %s", desired_state, self.name)
        for _ in range(num_retries):
            result = subp(
                [
                    "lxc",
                    "list",
                    "^{}$".format(self.name),
                    "-cs",
                    "--format",
                    "csv",
                ]
            )

            if result == desired_state:
                return
            time.sleep(1)
        raise PycloudlibTimeoutError

    def wait_for_stop(self):
        """Wait for cloud instance to transition to stop state."""
        # Ephemeral instances will not go to STOPPED. They get destroyed.
        if not self.ephemeral:
            self.wait_for_state("STOPPED")

    def _wait_for_instance_start(self):
        """Wait for the cloud instance to be up.

        LXD VMs need to install systemd units upon initialization. There is
        no easy way to do this and also enable them on boot, so an LXD VM
        will reboot as part of its initialization process. It is possible
        we have connected the VM before this reboot occurs, so then any
        following SSH connections will fail.

        The VM doesn't accurately report the number of processes until
        the initialization is fully complete, so block until our number
        of processes isn't -1.
        """
        processes = -1
        for _ in range(600):
            try:
                processes = int(
                    subp(
                        "lxc list --columns N {} --format csv".format(
                            self.name
                        ).split()
                    )
                )
            except ValueError:
                pass
            if processes > -1:
                return
            time.sleep(1)
        raise PycloudlibTimeoutError


class LXDVirtualMachineInstance(LXDInstance):
    """LXD Virtual Machine backed instance."""

    def _run_command(self, command, stdin):
        """Run command in the instance."""
        if self.execute_via_ssh:
            return super()._run_command(command, stdin)

        if self.series == "xenial":
            self._log.warning(MISSING_AGENT_MSG, "lxc exec")

        return super()._run_command(command, stdin)

    def _wait_for_instance_start(self):
        """Wait for the cloud instance to be up.

        LXD VMs need to install systemd units upon initialization. There is
        no easy way to do this and also enable them on boot, so an LXD VM
        will reboot as part of its initialization process. It is possible
        we have connected the VM before this reboot occurs, so then any
        following SSH connections will fail.

        The VM doesn't accurately report the number of processes until
        the initialization is fully complete, so block until our number
        of processes isn't -1.
        """
        # On xenial, we don't install the LXD agent, so we cannot count the
        # number of processes running on the VM. For xenial, we will rely
        # on the other wait methods that are run to guarantee that the instance
        # is running
        if self.series != "xenial":
            super()._wait_for_instance_start()
        else:
            self.wait_for_state(desired_state="RUNNING", num_retries=200)
