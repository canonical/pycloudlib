# This file is part of pycloudlib. See LICENSE file for license information.
"""GCE Cloud type.

This is an initial implementation of the GCE class. It enables
authentication into the cloud, finding an image, and launching an
instance. It however, does not allow any further actions from occurring.
"""

import logging
import os
import time
from itertools import count
from typing import Any, MutableMapping, Optional

from google.api_core.exceptions import GoogleAPICallError
from google.api_core.extended_operation import ExtendedOperation
from google.cloud import compute_v1

from pycloudlib.cloud import BaseCloud, ImageType
from pycloudlib.config import ConfigFile
from pycloudlib.errors import (
    CloudSetupError,
    ImageNotFoundError,
    PycloudlibError,
)
from pycloudlib.gce.instance import GceInstance
from pycloudlib.gce.util import get_credentials, raise_on_error
from pycloudlib.util import UBUNTU_RELEASE_VERSION_MAP, subp

logging.getLogger("google.cloud").setLevel(logging.WARNING)


class GCE(BaseCloud):
    """GCE Cloud Class."""

    _type = "gce"

    def __init__(
        self,
        tag: str,
        timestamp_suffix: bool = True,
        config_file: Optional[ConfigFile] = None,
        *,
        credentials_path: Optional[str] = None,
        project: Optional[str] = None,
        region: Optional[str] = None,
        zone: Optional[str] = None,
        service_account_email: Optional[str] = None,
    ):
        """Initialize the connection to GCE.

        Args:
            tag: string used to name and tag resources with
            timestamp_suffix: bool set True to append a timestamp suffix to the
                tag
            config_file: path to pycloudlib configuration file
            credentials_path: path to credentials file for GCE
            project: GCE project
            region: GCE region
            zone: GCE zone
            service_account_email: service account to bind launched
                                   instances to
        """
        super().__init__(
            tag,
            timestamp_suffix,
            config_file,
            required_values=[credentials_path, project],
        )

        self._log.debug("logging into GCE")

        self.credentials_path = ""
        if credentials_path:
            self.credentials_path = credentials_path
        elif "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
            self.credentials_path = os.environ["GOOGLE_APPLICATION_CREDENTIALS"]
        elif "credentials_path" in self.config:
            self.credentials_path = os.path.expandvars(
                os.path.expanduser(self.config["credentials_path"])
            )

        credentials = get_credentials(self.credentials_path)

        if not project:
            if "project" in self.config:
                project = self.config["project"]
            elif "GOOGLE_CLOUD_PROJECT" in os.environ:
                project = os.environ["GOOGLE_CLOUD_PROJECT"]
            else:
                command = ["gcloud", "config", "get-value", "project"]
                exception_text = (
                    "Could not obtain GCE project id. Set it in the "
                    "pycloudlib config or setup the gcloud cli."
                )
                try:
                    result = subp(command, rcs=())
                except FileNotFoundError as e:
                    raise CloudSetupError(exception_text) from e
                if not result.ok:
                    exception_text += "\nstdout: {}\nstderr: {}".format(
                        result.stdout, result.stderr
                    )
                    raise CloudSetupError(exception_text)
                project = result.stdout

        self._images_client = compute_v1.ImagesClient(credentials=credentials)
        self._disks_client = compute_v1.DisksClient(credentials=credentials)
        self._instances_client = compute_v1.InstancesClient(credentials=credentials)
        self._zone_operations_client = compute_v1.ZoneOperationsClient(credentials=credentials)
        self._global_operations_client = compute_v1.GlobalOperationsClient(credentials=credentials)
        region = region or self.config.get("region") or "us-west2"
        zone = zone or self.config.get("zone") or "a"
        self.project = project
        self.region = region
        self.zone = "%s-%s" % (region, zone)
        self.instance_counter = count()
        # Prefer service_account_email from pycloudlib.toml and fallback to
        # the credentials listed in GOOGLE_APPLICATION_CREDENTIALS otherwise
        self.service_account_email = (
            service_account_email
            or self.config.get("service_account_email")
            or getattr(credentials, "service_account_email", None)
        )

    def released_image(self, release, *, image_type: ImageType = ImageType.GENERIC, **kwargs):
        """ID of the latest released image for a particular release.

        Args:
            release: The release to look for

        Returns:
            A single string with the latest released image ID for the
            specified release.
        """
        return self.daily_image(release=release, image_type=image_type)

    def _get_project(self, image_type: ImageType):
        return (
            "ubuntu-os-cloud-devel"
            if image_type in (ImageType.GENERIC, ImageType.MINIMAL)
            else "ubuntu-os-pro-cloud"
        )

    def _get_name_filter(self, release: str, image_type: ImageType):
        if image_type == ImageType.GENERIC:
            return "daily-ubuntu-{}-{}-*".format(
                UBUNTU_RELEASE_VERSION_MAP[release].replace(".", ""), release
            )

        if image_type == ImageType.MINIMAL:
            return "daily-ubuntu-minimal-{}-{}-*".format(
                UBUNTU_RELEASE_VERSION_MAP[release].replace(".", ""), release
            )

        if image_type == ImageType.PRO:
            return "ubuntu-pro-{}-{}-*".format(
                UBUNTU_RELEASE_VERSION_MAP[release].replace(".", ""), release
            )

        if image_type == ImageType.PRO_FIPS:
            return "ubuntu-pro-fips-{}-{}-*".format(
                UBUNTU_RELEASE_VERSION_MAP[release].replace(".", ""), release
            )

        if image_type == ImageType.PRO_FIPS_UPDATES:
            return "ubuntu-pro-fips-updates-{}-{}-*".format(
                UBUNTU_RELEASE_VERSION_MAP[release].replace(".", ""), release
            )

        raise ValueError("Invalid image_type: {}".format(image_type.value))

    def _query_image_list(self, release: str, project: str, name_filter: str, arch: str):
        """Query full list of images.

        image list API docs:
        https://googleapis.github.io/google-api-python-client/docs/dyn/compute_v1.images.html#list

        The image list API doesn't allow filtering and sorting in one request
        so we need to do one of those locally.
        Filtering via the API results in fewer requests on average than
        sorting via the API.
        So we filter via the API and loop through all pages to get the full
        image list matching that filter.
        500 is the maximum allowed page size
        Then we can sort locally and grab the latest image.

        Args:
            release: string, Ubuntu release to look for
            project: GCE project
            name_filter: name to filter with
            arch: images' architecture

        Returns:
            list of images matching the given filters
        """
        filter_string = "(name={}) AND (architecture={})".format(name_filter, arch.upper())

        # SPECIAL CASE
        # Google didn't start including architecture in image descriptions
        # until after xenial stopped getting published
        # All xenial images are x86_64, so:
        #   1. we can return early for non-x86_64 xenial queries
        #   2. for xenial + x86_64 we don't include the architecture in the
        #      filter
        if release == "xenial":
            if arch != "x86_64":
                return []
            filter_string = "name={}".format(name_filter)

        image_list = []
        page_token = ""
        reqs = 0
        while page_token is not None:
            try:
                image_list_request = compute_v1.ListImagesRequest(
                    project=project,
                    filter=filter_string,
                    max_results=500,
                    page_token=page_token,
                )
                image_list_result = self._images_client.list(image_list_request)
            except GoogleAPICallError as e:
                raise_on_error(e)
            reqs += 1
            image_list += image_list_result.items
            page_token = image_list_result.next_page_token
            if page_token == "":
                break

        self._log.debug(
            ("Fetched entire image list (%i results) matching '%s' in %i requests"),
            len(image_list),
            filter_string,
            reqs,
        )

        return image_list

    def daily_image(
        self,
        release: str,
        *,
        arch: str = "x86_64",
        image_type: ImageType = ImageType.GENERIC,
        **kwargs,
    ):
        """Find the id of the latest image for a particular release.

        Args:
            release: string, Ubuntu release to look for

        Returns:
            string, path to latest daily image

        """
        self._log.debug(
            "finding daily Ubuntu image for arch: %s and release: %s",
            arch,
            release,
        )
        project = self._get_project(image_type=image_type)
        name_filter = self._get_name_filter(release=release, image_type=image_type)

        image_list = self._query_image_list(release, project, name_filter, arch)

        if not image_list:
            msg = "Could not find {} image for arch: {} and release: {}".format(
                image_type.value,
                arch,
                release,
            )
            self._log.warning(msg)
            raise ImageNotFoundError(image_type=image_type.value, arch=arch, release=release)

        image = sorted(image_list, key=lambda x: x.creation_timestamp)[-1]
        self._log.debug(
            'Found image name "%s" for arch "%s"',
            image.name,
            arch,
        )
        return "projects/{}/global/images/{}".format(project, image.id)

    def image_serial(self, image_id):
        """Find the image serial of the latest daily image for a particular release.

        Args:
            image_id: string, Ubuntu image id

        Returns:
            string, serial of latest image

        """
        raise NotImplementedError

    def delete_image(self, image_id, **kwargs):
        """Delete an image.

        Args:
            image_id: string, id of the image to delete
        """
        try:
            images_get_request = compute_v1.GetImageRequest(
                project=self.project,
                image=os.path.basename(image_id),
            )
            api_image_id = str(self._images_client.get(images_get_request).id)
        except GoogleAPICallError as e:
            if "was not found" not in str(e):
                raise
            return

        try:
            delete_image_request = compute_v1.DeleteImageRequest(
                project=self.project,
                image=api_image_id,
            )
            operation: ExtendedOperation = self._images_client.delete(delete_image_request)
            raise_on_error(operation)
        except GoogleAPICallError as e:
            raise_on_error(e)

    def get_instance(
        self,
        instance_id,
        name=None,
        *,
        username: Optional[str] = None,
        **kwargs,
    ):
        """Get an instance by id.

        Args:
            instance_id: The instance ID returned upon creation
            username: username to use when connecting via SSH

        Returns:
            An instance object to use to manipulate the instance further.

        """
        return GceInstance(
            self.key_pair,
            instance_id,
            self.project,
            self.zone,
            self.credentials_path,
            name=name,
            username=username,
        )

    def launch(
        self,
        image_id,
        instance_type="n1-standard-1",
        user_data=None,
        *,
        username: Optional[str] = None,
        **kwargs,
    ):
        """Launch instance on GCE and print the IP address.

        Args:
            image_id: string, image ID for instance to use
            instance_type: string, instance type to launch
            user_data: string, user-data to pass to instance
            username: username to use when connecting via SSH
            kwargs: other named arguments to add to instance JSON
        Raises: ValueError on invalid image_id
        """
        if not image_id:
            raise ValueError(f"{self._type} launch requires image_id param. Found: {image_id}")
        instance_name = "i{}-{}".format(next(self.instance_counter), self.tag)
        config: MutableMapping[str, Any] = {
            "name": instance_name,
            "machine_type": "zones/%s/machineTypes/%s" % (self.zone, instance_type),
            "disks": [
                {
                    "boot": True,
                    "auto_delete": True,
                    "initialize_params": {
                        "source_image": image_id,
                    },
                }
            ],
            "network_interfaces": [
                {
                    "network": "global/networks/default",
                    "access_configs": [{"type_": "ONE_TO_ONE_NAT", "name": "External NAT"}],
                }
            ],
            "metadata": {
                "items": [
                    {
                        "key": "ssh-keys",
                        "value": "ubuntu:%s" % self.key_pair.public_key_content,
                    }
                ]
            },
        }

        config.update(kwargs)

        if self.service_account_email:
            config["service_accounts"] = [{"email": self.service_account_email}]

        if user_data:
            user_metadata = {"key": "user-data", "value": user_data}
            config["metadata"]["items"].append(user_metadata)

        try:
            insert_instance_request = compute_v1.InsertInstanceRequest(
                project=self.project,
                zone=self.zone,
                instance_resource=config,
            )
            operation: ExtendedOperation = self._instances_client.insert(insert_instance_request)
            raise_on_error(operation)
        except GoogleAPICallError as e:
            raise_on_error(e)

        try:
            instance_get_request = compute_v1.GetInstanceRequest(
                project=self.project,
                zone=self.zone,
                instance=instance_name,
            )
            result = self._instances_client.get(instance_get_request)
        except GoogleAPICallError as e:
            raise_on_error(e)

        instance = self.get_instance(result.id, name=result.name, username=username)
        self.created_instances.append(instance)
        return instance

    def snapshot(self, instance: GceInstance, clean=True, **kwargs):
        """Snapshot an instance and generate an image from it.

        Args:
            instance: Instance to snapshot
            clean: run instance clean method before taking snapshot

        Returns:
            An image id
        """
        try:
            list_disks_request = compute_v1.ListDisksRequest(
                project=self.project,
                zone=self.zone,
            )
            response = self._disks_client.list(list_disks_request)
        except GoogleAPICallError as e:
            raise_on_error(e)

        instance_disks = [disk for disk in response.items if disk.name == instance.name]

        if len(instance_disks) > 1:
            raise PycloudlibError("Snapshotting an image with multiple disks not supported")

        instance.shutdown()

        snapshot_name = "{}-image".format(instance.name)
        try:
            image_resource = compute_v1.Image(
                name=snapshot_name,
                source_disk=instance_disks[0].self_link,
            )
            insert_image_request = compute_v1.InsertImageRequest(
                project=self.project,
                image_resource=image_resource,
            )
            operation: ExtendedOperation = self._images_client.insert(insert_image_request)
            raise_on_error(operation)
        except GoogleAPICallError as e:
            raise_on_error(e)
        self._wait_for_operation(operation)

        image_id = "projects/{}/global/images/{}".format(self.project, snapshot_name)
        self.created_images.append(image_id)
        return image_id

    def _wait_for_operation(self, operation, operation_type="global", sleep_seconds=300):
        if operation_type == "zone":
            api = self._zone_operations_client
            request = compute_v1.GetZoneOperationRequest(
                project=self.project, zone=self.zone, operation=operation.name
            )
        else:
            api = self._global_operations_client
            request = compute_v1.GetGlobalOperationRequest(
                project=self.project, operation=operation.name
            )
        for _ in range(sleep_seconds):
            try:
                response = api.get(request)
            except GoogleAPICallError as e:
                raise_on_error(e)
            else:
                if response.status == compute_v1.types.Operation.Status.DONE:
                    break
            time.sleep(1)
        else:
            raise PycloudlibError(
                "Expected DONE state, but found {} after waiting {} seconds. "
                "Check GCE console for more details. \n".format(response.status, sleep_seconds)
            )
