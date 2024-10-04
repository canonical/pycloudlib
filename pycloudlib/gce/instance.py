# This file is part of pycloudlib. See LICENSE file for license information.
"""GCE instance."""

from time import sleep
from typing import List, Optional

from google.api_core.exceptions import GoogleAPICallError, NotFound
from google.api_core.extended_operation import ExtendedOperation
from google.cloud import compute_v1
from google.cloud.compute_v1.types import Instance

from pycloudlib.errors import PycloudlibTimeoutError
from pycloudlib.gce.util import get_credentials, raise_on_error
from pycloudlib.instance import BaseInstance


class GceInstance(BaseInstance):
    """GCE backed instance."""

    _type = "gce"

    def __init__(
        self,
        key_pair,
        instance_id,
        project,
        zone,
        credentials_path,
        *,
        name=None,
        username: Optional[str] = None,
    ):
        """Set up the instance.

        Args:
            key_pair: A KeyPair for SSH interactions
            instance_id: Id returned when creating the instance
            project: Project instance was created in
            zone: Zone instance was created in
            name: Name of the instance
            username: username to use when connecting via SSH
        """
        if project is None or zone is None:
            raise ValueError(
                "kwargs 'project' and 'zone' are required. "
                "Project: {}, Zone: {}".format(project, zone)
            )
        super().__init__(key_pair, username=username)
        self.instance_id = instance_id
        self._name = name
        self.project = project
        self.zone = zone
        self._ip = None
        credentials = get_credentials(credentials_path)
        self._instances_client = compute_v1.InstancesClient(
            credentials=credentials
        )

    def __repr__(self):
        """Create string representation of class."""
        return "{}(instance_id={})".format(
            self.__class__.__name__,
            self.instance_id,
        )

    @property
    def id(self):
        """Return the instance id."""
        return str(self.instance_id)

    @property
    def name(self):
        """Return the instance name."""
        if not self._name:
            try:
                get_instance_request = compute_v1.GetInstanceRequest(
                    project=self.project,
                    zone=self.zone,
                    instance=str(self.instance_id),
                )
                result = self._instances_client.get(get_instance_request)
                self._name = result.name
            except GoogleAPICallError as e:
                raise_on_error(e)
        return self._name

    @property
    def ip(self):
        """Return IP address of instance."""
        if not self._ip:
            self._ip = self._get_ip()
        return self._ip

    def _get_ip(self):
        try:
            get_instance_request = compute_v1.GetInstanceRequest(
                project=self.project,
                zone=self.zone,
                instance=str(self.instance_id),
            )
            result = self._instances_client.get(get_instance_request)
            ip = result.network_interfaces[0].access_configs[0].nat_i_p
        except GoogleAPICallError as e:
            raise_on_error(e)
        return ip

    # pylint: disable=broad-except
    def delete(self, wait=True) -> List[Exception]:
        """Delete the instance.

        Args:
            wait: wait for instance to be deleted
        """
        if not self.instance_id:
            return []
        try:
            delete_instance_request = compute_v1.DeleteInstanceRequest(
                project=self.project,
                zone=self.zone,
                instance=str(self.instance_id),
            )
            response: ExtendedOperation = self._instances_client.delete(
                delete_instance_request
            )
            raise_on_error(response)
            if wait:
                self.wait_for_delete()
            self.instance_id = None
        except Exception as e:
            return [e]

        return []

    def _do_restart(self, **kwargs):
        """Restart the instance."""
        self.shutdown(wait=True)
        self.start(wait=False)

    def shutdown(self, wait=True, **kwargs):
        """Shutdown the instance.

        Args:
            wait: wait for the instance to shutdown
        """
        try:
            stop_instance_request = compute_v1.StopInstanceRequest(
                project=self.project,
                zone=self.zone,
                instance=str(self.instance_id),
            )
            operation: ExtendedOperation = self._instances_client.stop(
                stop_instance_request
            )
            raise_on_error(operation)
        except GoogleAPICallError as e:
            raise_on_error(e)
        if wait:
            self.wait_for_stop()

    def start(self, wait=True):
        """Start the instance.

        Args:
            wait: wait for the instance to start.
        """
        try:
            start_instance_request = compute_v1.StartInstanceRequest(
                project=self.project,
                zone=self.zone,
                instance=str(self.instance_id),
            )
            operation: ExtendedOperation = self._instances_client.start(
                start_instance_request
            )
            raise_on_error(operation)
        except GoogleAPICallError as e:
            raise_on_error(e)
        if wait:
            self.wait()

    def _wait_for_instance_start(self, **kwargs):
        """Wait for instance to be up."""
        self._wait_for_status("RUNNING")
        self._ip = self._get_ip()

    def wait_for_delete(self, sleep_seconds=30, raise_on_fail=False):
        """Wait for instance to be deleted."""
        get_instance_request = compute_v1.GetInstanceRequest(
            project=self.project,
            zone=self.zone,
            instance=str(self.instance_id),
        )
        for _ in range(sleep_seconds):
            try:
                response = self._instances_client.get(get_instance_request)
                if response.status == "TERMINATED":
                    break
            except NotFound:
                # Sometimes URL just 404s once deleted
                break
            except GoogleAPICallError as e:
                raise_on_error(e)
            sleep(1)
        else:
            msg = (
                f"Instance {self.instance_id} still exists after waiting "
                f"{sleep_seconds} seconds. Check GCE console for more details."
            )
            if raise_on_fail:
                raise PycloudlibTimeoutError(msg)
            self._log.warning(msg)

    def wait_for_stop(self, **kwargs):
        """Wait for instance stop."""
        self._wait_for_status("TERMINATED")

    def _wait_for_status(self, status, sleep_seconds=300):
        response: Instance = Instance(status=None)
        get_instance_request = compute_v1.GetInstanceRequest(
            project=self.project,
            zone=self.zone,
            instance=str(self.instance_id),
        )
        for _ in range(sleep_seconds):
            try:
                response = self._instances_client.get(get_instance_request)
                if response.status == status:
                    break
            except GoogleAPICallError as e:
                raise_on_error(e)
            sleep(1)
        else:
            raise PycloudlibTimeoutError(
                f"Expected {status} state, but found {response.status} "
                f"after waiting {sleep_seconds} seconds. "
                "Check GCE console for more details."
            )
