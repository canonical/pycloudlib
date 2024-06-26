# This file is part of pycloudlib. See LICENSE file for license information.
# pylint: disable=too-many-public-methods
"""IBM Classic instance class."""

import logging
from typing import List, Optional

import SoftLayer  # type: ignore

from pycloudlib.ibm._util import wait_until as _wait_until
from pycloudlib.ibm_classic.errors import IBMClassicException
from pycloudlib.instance import BaseInstance

logger = logging.getLogger(__name__)


class IBMClassicInstance(BaseInstance):
    """IBM Classic instance class."""

    _type = "ibm_classic"

    def __init__(
        self,
        key_pair,
        *,
        softlayer_client: SoftLayer.BaseClient,
        vs_manager: SoftLayer.VSManager,
        instance: dict,
        username: Optional[str] = None,
    ):
        """Set up instance."""
        super().__init__(key_pair, username=username)

        self._softlayer_client = softlayer_client
        self._vs_manager = vs_manager
        self._instance = instance
        self._deleted = False

        if username:
            self._log.error(
                "Specifiying username is not supported for IBM Classic "
                "instances. The default 'ubuntu' user will be used."
            )

    @property
    def id(self) -> str:
        """Return instance id."""
        return self._instance["id"]

    @property
    def name(self):
        """Return instance name."""
        return self._instance["hostname"]

    @property
    def ip(self):
        """Return IP address of instance."""
        # update instance info if IP address was not previously available
        if "primaryIpAddress" not in self._instance:
            self._instance = self._vs_manager.get_instance(self.id)
        # if IP address is still not available, raise exception
        if "primaryIpAddress" not in self._instance:
            raise IBMClassicException(
                f"Failed to get IP address for instance {self.id}"
            )

        return self._instance["primaryIpAddress"]

    @staticmethod
    def create_raw_instance(
        vs_manager: SoftLayer.VSManager,
        target_image_global_identifier: str,
        hostname: str,
        flavor: str,
        datacenter: str,
        public_security_group_ids: List[int],
        private_security_group_ids: List[int],
        ssh_key_ids: List[int],
        domain_name: str,
        **kwargs,
    ):
        """
        Verify instance configuration and create instance.

        Args:
            vs_manager: Softlayer VSManager (Virtual Server Manager) instance
            target_image_global_identifier: image global identifier
            hostname: instance hostname
            flavor: instance flavor
            datacenter: datacenter region
            public_security_group_ids: list of public security group ids
            private_security_group_ids: list of private security group ids
            ssh_key_ids: list of ssh key ids
            domain_name: domain name

        """
        logger.debug("Creating raw instance")
        constant_args = {
            "private": False,
            "dedicated": False,  # default
            "hourly": True,  # default
            "local_disk": False,  # default
        }
        instance_specific_args = {
            "domain": domain_name,
            "hostname": hostname,
            "ssh_keys": ssh_key_ids,
            "image_id": target_image_global_identifier,
            "flavor": flavor,
            "datacenter": datacenter,
            "public_security_groups": public_security_group_ids,
            "private_security_groups": private_security_group_ids,
        }
        # check if instance configuration is valid
        try:
            logger.info(
                "Verifying configuration for instance before creating it."
            )
            vs_manager.verify_create_instance(
                **constant_args,
                **instance_specific_args,
                **kwargs,
            )
        except SoftLayer.SoftLayerAPIError as e:
            logger.error("configuration for instance is invalid: %s", e)
            raise IBMClassicException(
                f"Failed to verify instance configuration: {e}"
            ) from e
        except Exception as e:
            logger.error(
                "Unexpected error while verifying instance configuration: %s",
                e,
            )
            raise IBMClassicException(
                f"Unexpected error while verifying instance configuration: {e}"
            ) from e
        logger.info(
            "Configuration for instance is valid. Creating instance now."
        )
        raw_instance = vs_manager.create_instance(
            **constant_args,
            **instance_specific_args,
            **kwargs,
        )
        logger.info("Created instance %s", raw_instance["hostname"])
        full_raw_instance_info = vs_manager.get_instance(raw_instance["id"])
        logger.debug("New instance details: %s", full_raw_instance_info)
        return full_raw_instance_info

    def console_log(self):
        """Return the instance console log.

        Raises NotImplementedError if the cloud does not support fetching the
        console log for this instance.
        """
        raise NotImplementedError("Console log not supported for IBM Classic")

    def delete(self, wait=True) -> List[Exception]:
        """Delete the instance.

        Args:
            wait: wait for instance to be deleted
        """

        def has_no_active_transaction():
            """Check if instance has no active transaction."""
            instance = self._vs_manager.get_instance(self.id)
            return "activeTransaction" not in instance

        if self._deleted:
            logger.debug("Instance %s already deleted", self.name)
            self._deleted = True
            return []
        try:
            if wait:
                logger.info(
                    "Deleting instance %s and waiting for it to delete.",
                    self.name,
                )
                instance = self._vs_manager.get_instance(self.id)
                if "activeTransaction" in instance:
                    at = instance["activeTransaction"]
                    logger.info(
                        "Instance %s has an active transaction. "
                        "Must wait for it to complete "
                        "or else instance cancellation will fail. ",
                        self.name,
                    )
                    t = at["transactionStatus"]["friendlyName"]
                    msg = (
                        f"Instance {self.name} stuck in active transaction:"
                        f" {t}."
                    )
                    _wait_until(
                        has_no_active_transaction,
                        timeout_seconds=60 * 60,
                        timeout_msg_fn=lambda: msg,
                        check_interval=5,
                    )
                    self._wait_for_execute()
                self._vs_manager.cancel_instance(self.id)
                self.wait_for_delete()
            else:
                logger.info("Deleting instance %s without waiting.")
                self._vs_manager.cancel_instance(self.id)
        except Exception as e:  # pylint: disable=broad-except
            return [e]

        self._deleted = True
        return []

    def _do_restart(self, **kwargs):
        self._softlayer_client.call("Virtual_Guest", "rebootSoft", id=self.id)

    def shutdown(self, wait=True, **kwargs):
        """Shutdown the instance.

        Args:
            wait: wait for the instance to shutdown
        """
        if wait:
            logger.info(
                "Shutting down instance %s and waiting for it to stop.",
                self.name,
            )
            self._softlayer_client.call(
                "Virtual_Guest", "powerOff", id=self.id
            )
            self.wait_for_stop()
        else:
            logger.info(
                "Shutting down instance %s without waiting.",
                self.name,
            )
            self._softlayer_client.call(
                "Virtual_Guest", "powerOff", id=self.id
            )

    def start(self, wait=True):
        """Start the instance.

        Args:
            wait: wait for the instance to start.
        """
        if wait:
            logger.info(
                "Starting instance %s and waiting for it to start.",
                self.name,
            )
            self._softlayer_client.call("Virtual_Guest", "powerOn", id=self.id)
            self._wait_for_instance_start()
        else:
            logger.info(
                "Starting instance %s without waiting.",
                self.name,
            )
            self._softlayer_client.call("Virtual_Guest", "powerOn", id=self.id)

    def _wait_for_instance_start(self, **kwargs):
        """Wait for the cloud instance to be up."""

        def is_started():
            instance = self._vs_manager.get_instance(self.id)
            power_state = instance.get("powerState", {}).get("keyName")
            last_transaction = (
                instance.get("lastTransaction", {})
                .get("transactionStatus", {})
                .get("name")
            )
            is_active_transaction = "activeTransaction" in instance
            logger.debug(
                "Instance %s powerState: %s",
                self.name,
                power_state,
            )
            logger.debug(
                "Instance %s lastTransaction: %s",
                self.name,
                last_transaction,
            )
            logger.debug(
                "Instance %s activeTransaction: %s",
                self.name,
                is_active_transaction,
            )
            return (
                power_state == "RUNNING"
                and last_transaction == "COMPLETE"
                and not is_active_transaction
            )

        # wait for 3 hours for the instance to start
        timeout = 60 * 60 * 3
        msg = f"Instance {self.name} did not start after {timeout} seconds"

        _wait_until(
            is_started,
            timeout_seconds=timeout,
            timeout_msg_fn=lambda: msg,
            check_interval=10,
        )
        logger.info("Instance %s started", self.name)
        self._instance = self._vs_manager.get_instance(self.id)

    def wait(self, **kwargs):
        """Wait for instance to be up and cloud-init to be complete."""
        logger.info("Waiting for instance %s to be ready", self.name)
        self._wait_for_instance_start(**kwargs)
        self._wait_for_execute(timeout=180)
        self._wait_for_cloudinit()

    def wait_for_restart(self, old_boot_id):
        """Wait for instance to be restarted and cloud-init to be complete.

        old_boot_id is the boot id prior to restart
        """
        logger.info("Waiting for instance %s to restart", self.name)
        self._wait_for_instance_start()
        self._wait_for_execute(old_boot_id=old_boot_id, timeout=15)
        self._wait_for_cloudinit()

    def wait_for_delete(self, **kwargs):
        """Wait for instance to be deleted."""

        # we need to wait until the instance is deleted
        def is_deleted():
            existing_instances = self._vs_manager.list_instances()
            return self.id not in [
                instance["id"] for instance in existing_instances
            ]

        # wait for 10 minutes for the instance to delete
        timeout = 60 * 10
        msg = f"Instance {self.name} failed to delete after {timeout} seconds"

        _wait_until(
            is_deleted,
            timeout_seconds=timeout,
            timeout_msg_fn=lambda: msg,
            check_interval=5,
        )
        logger.info("Instance %s deleted", self.name)

    def wait_for_stop(self, **kwargs):
        """Wait for instance stop."""

        def is_stopped():
            instance = self._vs_manager.get_instance(self.id)
            power_state = instance.get("powerState", {}).get("keyName")
            last_transaction = (
                instance.get("lastTransaction", {})
                .get("transactionStatus", {})
                .get("name")
            )
            is_active_transaction = "activeTransaction" in instance
            logger.debug(
                "Instance %s powerState: %s",
                self.name,
                power_state,
            )
            logger.debug(
                "Instance %s lastTransaction: %s",
                self.name,
                last_transaction,
            )
            logger.debug(
                "Instance %s activeTransaction: %s",
                self.name,
                is_active_transaction,
            )
            return (
                power_state == "HALTED"
                and last_transaction == "COMPLETE"
                and not is_active_transaction
            )

        # wait for 10 minutes for the instance to stop
        timeout = 60 * 10
        msg = f"Instance {self.name} failed to stop after {timeout} seconds"

        _wait_until(
            is_stopped,
            timeout_seconds=timeout,
            timeout_msg_fn=lambda: msg,
            check_interval=5,
        )
        logger.info("Instance %s stopped", self.name)
