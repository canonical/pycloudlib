# This file is part of pycloudlib. See LICENSE file for license information.
"""VMWare instance."""
import subprocess
from typing import List, Mapping, Optional

from pycloudlib.errors import PycloudlibTimeoutError
from pycloudlib.instance import BaseInstance
from pycloudlib.key import KeyPair


class VMWareInstance(BaseInstance):
    """VMWare backed instance."""

    _type = "vmware"

    def __init__(self, key_pair: KeyPair, vm_id: str, env: Mapping):
        """Instance for VMWare.

        Args:
            key_pair: SSH key object
            vm_id: ID of the VM to interact with
        """
        super().__init__(key_pair=key_pair)
        self.vm_id = vm_id
        self._ip: Optional[str] = None
        self.env = env

    @property
    def id(self) -> str:
        """Return instance id."""
        return self.vm_id

    @property
    def name(self) -> str:
        """Return VM name."""
        return self.vm_id

    @property
    def ip(self) -> str:
        """Return VM IP."""
        if self._ip is not None:
            return self._ip
        ips_output = subprocess.check_output(
            ["govc", "vm.ip", "-wait", "5m", self.vm_id], env=self.env
        )
        if not ips_output:
            raise PycloudlibTimeoutError(
                "Could not retrieve IP address after 5 minutes"
            )

        ips = ips_output.decode().strip().split(",")
        if len(ips) > 1:
            self._log.warning("Expected 1 IP but got %s. Using the first", ips)
        self._ip = ips[0]
        return ips[0]  # Not self._ip here because mypy isn't smart enough

    def delete(self, wait=True) -> List[Exception]:
        """Delete the instance."""
        exceptions: List[Exception] = []
        try:
            self.shutdown()
            subprocess.run(
                ["govc", "vm.destroy", self.vm_id], env=self.env, check=True
            )
        except subprocess.CalledProcessError as e:
            if "not found" not in str(e):
                exceptions.append(e)
        return exceptions

    def _do_restart(self, **kwargs):
        """Restart the instance."""
        self.shutdown()
        self.start()

    def shutdown(self, wait=True, **kwargs):
        """Shutdown the instance.

        Args:
            wait: wait for the instance shutdown
        """
        try:
            subprocess.run(
                ["govc", "vm.power", "-off", self.vm_id],
                env=self.env,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            if "Powered on" not in str(e):
                raise

    def start(self, wait=True):
        """Start the instance.

        Args:
            wait: wait for the instance to start.
        """
        try:
            subprocess.run(
                ["govc", "vm.power", "-on", self.vm_id],
                env=self.env,
                check=True,
            )
        except subprocess.CalledProcessError as e:
            if "Powered on" not in str(e):
                raise
        if wait:
            self.wait()

    def _wait_for_instance_start(self, **kwargs):
        """Wait for the cloud instance to be up."""
        assert self.ip  # Obtain IP operation is blocking

    def wait_for_delete(self, **kwargs):
        """Wait for instance to be deleted."""  # Delete operation is blocking

    def wait_for_stop(self, **kwargs):
        """Wait for instance to stop."""  # Stop operation is blocking
