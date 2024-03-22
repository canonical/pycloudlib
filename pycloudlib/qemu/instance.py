# This file is part of pycloudlib. See LICENSE file for license information.
"""Instance class for QEMU."""

import asyncio
import logging
import shutil
import time
from pathlib import Path
from subprocess import Popen
from typing import Any, Dict, List, Optional

from qemu.qmp import QMPClient

from pycloudlib.errors import (
    CleanupError,
    MissingPrerequisiteError,
    PycloudlibTimeoutError,
)
from pycloudlib.instance import BaseInstance


class QmpConnection:
    """Stupid wrapper to handle asyncio."""

    def __init__(self, qmp_socket: Path, log: logging.Logger):
        """Set up QMP connection.

        Args:
            qmp_socket: path to QMP socket
            log: logger to use
        """
        self._log = log
        self.qmp = QMPClient()
        self.loop = asyncio.get_event_loop()
        self.loop.run_until_complete(
            asyncio.wait_for(self.qmp.connect(str(qmp_socket)), timeout=10)
        )

    def execute(
        self, command: str, arguments: Optional[Dict[str, Any]] = None
    ) -> Any:
        """Write data to QMP socket.

        Args:
            command: command to run
            arguments: arguments to pass to command

        Returns the response from QMP.
        """
        return self.loop.run_until_complete(
            self.qmp.execute(command, arguments)
        )

    def disconnect(self):
        """Disconnect from QMP socket."""
        return self.loop.run_until_complete(self.qmp.disconnect())


class QemuInstance(BaseInstance):
    """QEMU instance object."""

    _type = "qemu"

    def __init__(
        self,
        key_pair,
        *,
        instance_id: str,
        handle: Optional[Popen] = None,
        username: Optional[str] = None,
    ):
        """Set up instance.

        Args:
            key_pair: key pair to use for instance
            instance_id: ID identifying the instance, in the form
                <instance_path>::<port>::<telnet_port>
            handle: handle to qemu process
            username: username to use for ssh
        """
        super().__init__(key_pair=key_pair, username=username)
        self.instance_path, self.port, self.telnet_port = instance_id.rsplit(
            "::", 2
        )
        self.instance_id = instance_id
        self.handle = handle
        self.instance_dir: Path = Path(self.instance_id).parent
        self.qmp = self._setup_qmp(self.instance_dir)

    def _setup_qmp(self, instance_dir):
        """Set up QMP connection.

        Args:
            instance_dir: directory containing instance files
        """
        # If we don't get a socket file fairly quickly, something is wrong
        qmp_socket = None

        for _ in range(10):
            possible_qmp_socket = instance_dir / "qmp-socket"
            if possible_qmp_socket.exists():
                qmp_socket = possible_qmp_socket
                break
            time.sleep(1)
        else:
            # Since our VM may still have started, we don't want to
            # force a cleanup here since it may still be useful for debugging
            self._log.error(
                "Failed to find QMP socket. Instance likely in an "
                "unusable state"
            )

        qmp = None
        if qmp_socket:
            try:
                qmp = QmpConnection(qmp_socket=qmp_socket, log=self._log)
            except AssertionError as e:
                self._log.error(
                    "QMP socket not working as expected: %s", str(e)
                )
        return qmp

    @property
    def id(self) -> str:
        """Return instance ID."""
        return self.instance_id

    @property
    def name(self):
        """Return instance name."""
        return self.id

    @property
    def ip(self):
        """Return IP address of instance."""
        return "127.0.0.1"

    def console_log(self):
        """Return the instance console log."""
        return Path(self.instance_dir, "console.log").read_text(
            encoding="utf-8"
        )

    def delete(self, wait=True) -> List[Exception]:
        """Delete the instance.

        Args:
            wait: Ignored. Our 'quit' command is synchronous.
        """
        if not self.instance_dir.exists():
            # We've already cleaned up. Nothing left to do
            return []
        errors = []
        try:
            if self.qmp:
                self.qmp.execute("quit")
                self.qmp.disconnect()
                self.qmp = None
            elif self.handle:
                # No point in graceful shutdown. We want it gone
                self.handle.kill()
            else:
                raise CleanupError(
                    "No QMP connection or process handle. "
                    "Manual cleanup required"
                )
        except Exception as e:  # pylint: disable=broad-except
            errors.append(e)
        try:
            shutil.rmtree(self.instance_dir)
        except Exception as e:  # pylint: disable=broad-except
            errors.append(e)
        return errors

    def _do_restart(self, **kwargs):
        """Restart the instance."""
        self.shutdown(wait=True)
        self.start()

    def shutdown(self, wait=True, **kwargs):
        """Shutdown the instance.

        Args:
            wait: wait for the instance to shutdown
        """
        if self.qmp:
            if self.get_status() == "running":
                self.qmp.execute("system_powerdown")
                if wait:
                    self.wait_for_stop()
                self.qmp.execute("system_reset")
            else:
                self._log.debug("Instance already shutdown.")

        else:
            self._log.warning("No QMP connection. Doing a soft shutdown")
            self.execute("shutdown now", use_sudo=True)

    def start(self, wait=True):
        """Start the instance.

        Args:
            wait: wait for the instance to start.
        """
        if not self.qmp:
            raise MissingPrerequisiteError("No QMP connection")
        self.qmp.execute("cont")
        if wait:
            self.wait()

    def _wait_for_instance_start(self, **kwargs):
        """Wait for instance to be up."""
        self.wait_till_status("running")

    def wait_for_delete(self, **kwargs):
        """Not implemented as "quit" is executed synchronously."""

    def wait_for_stop(self, **kwargs):
        """Wait for instance stop."""
        self.wait_till_status("shutdown")

    def get_status(self):
        """Get instance status."""
        if not self.qmp:
            raise MissingPrerequisiteError("No QMP connection")
        return self.qmp.execute("query-status")["status"]

    def wait_till_status(self, expected_status: str, timeout: int = 500):
        """Wait for instance to reach a certain status.

        Args:
            status: status to wait for
            timeout: timeout in seconds
        """
        if not self.qmp:
            raise MissingPrerequisiteError("No QMP connection")
        start_time = time.time()
        while True:
            query_status = self.get_status()
            if query_status == expected_status:
                return
            if query_status == "prelaunch" and expected_status == "running":
                # It can take some time for the VM to be ready to run,
                # so retry here if we're not in expected state
                self.qmp.execute("cont")
            if time.time() - start_time > timeout:
                raise PycloudlibTimeoutError(
                    f"Timed out waiting for instance to reach status "
                    f"{expected_status}"
                )
            time.sleep(1)

    def add_network_interface(self, **kwargs) -> str:
        """Add nic to running instance."""
        raise NotImplementedError

    def remove_network_interface(self, ip_address: str):
        """Remove nic from running instance."""
        raise NotImplementedError
