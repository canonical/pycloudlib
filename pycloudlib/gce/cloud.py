# This file is part of pycloudlib. See LICENSE file for license information.
"""GCE Cloud type.

This is an initial implimentation of the GCE class. It enables
authentication into the cloud, finding an image, and launching an
instance. It however, does not allow any further actions from occuring.
"""

import logging
import os
import re
import time
from itertools import count

import googleapiclient.discovery

from pycloudlib.cloud import BaseCloud, ImageType
from pycloudlib.config import ConfigFile
from pycloudlib.gce.instance import GceInstance
from pycloudlib.gce.util import get_credentials, raise_on_error
from pycloudlib.util import LTS_RELEASES, UBUNTU_RELEASE_VERSION_MAP, subp

logging.getLogger("googleapiclient.discovery").setLevel(logging.WARNING)


class GCE(BaseCloud):
    """GCE Cloud Class."""

    _type = "gce"

    def __init__(
        self,
        tag,
        timestamp_suffix=True,
        config_file: ConfigFile = None,
        *,
        credentials_path=None,
        project=None,
        region=None,
        zone=None,
        service_account_email=None,
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
        super().__init__(tag, timestamp_suffix, config_file)
        self._log.debug("logging into GCE")

        self.credentials_path = ""
        if credentials_path:
            self.credentials_path = credentials_path
        elif "GOOGLE_APPLICATION_CREDENTIALS" in os.environ:
            self.credentials_path = os.environ[
                "GOOGLE_APPLICATION_CREDENTIALS"
            ]
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
                    raise Exception(exception_text) from e
                if not result.ok:
                    exception_text += "\nstdout: {}\nstderr: {}".format(
                        result.stdout, result.stderr
                    )
                    raise Exception(exception_text)
                project = result.stdout

        # disable cache_discovery due to:
        # https://github.com/google/google-api-python-client/issues/299
        self.compute = googleapiclient.discovery.build(
            "compute",
            "v1",
            cache_discovery=False,
            credentials=credentials,
        )
        region = region or self.config.get("region") or "us-west2"
        zone = zone or self.config.get("zone") or "a"
        self.project = project
        self.region = region
        self.zone = "%s-%s" % (region, zone)
        self.instance_counter = count()
        self.service_account_email = service_account_email or self.config.get(
            "service_account_email"
        )

    def released_image(
        self, release, image_type: ImageType = ImageType.GENERIC
    ):
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
            if image_type == ImageType.GENERIC
            else "ubuntu-os-pro-cloud"
        )

    def _get_name_regex(self, release: str, image_type: ImageType):
        if image_type == ImageType.GENERIC:
            return "daily-ubuntu-{}-{}(-amd64)?-v\d+\w*".format(
                UBUNTU_RELEASE_VERSION_MAP[release].replace(".", ""), release
            )

        if image_type == ImageType.PRO:
            return "ubuntu-pro-{}-{}(-amd64)?-v\d+\w*".format(
                UBUNTU_RELEASE_VERSION_MAP[release].replace(".", ""), release
            )

        if image_type == ImageType.PRO_FIPS:
            return "ubuntu-pro-fips-{}-{}(-amd64)?-v\d+\w*".format(
                UBUNTU_RELEASE_VERSION_MAP[release].replace(".", ""), release
            )

        raise ValueError("Invalid image_type: {}".format(image_type.value))

    def _find_latest_image(self, release: str, image_type: ImageType):
        project = self._get_project(image_type=image_type)
        name_regex = self._get_name_regex(
            release=release, image_type=image_type
        )

        page = 1
        max_results = 500
        page_token = ""
        while True:
            image_list_result = (
                self.compute.images()
                .list(
                    project=project,
                    maxResults=max_results,
                    orderBy="creationTimestamp desc",
                    pageToken=page_token,
                )
                .execute()
            )

            image_list = image_list_result.get("items", [])

            if len(image_list) == 0:
                break

            for image in image_list:
                if re.match(name_regex, image["name"]):
                    self._log.debug("Found image name: {}".format(image["name"]))
                    return "projects/{}/global/images/{}".format(project, image["id"])

            page_token = image_list_result.get("nextPageToken", None)
            if page_token is None:
                break
            self._log.debug("Not found in the most recent {} images. Fetching next page...".format(page * max_results))
            page += 1

        raise Exception(
            "Could not find {} image for {} release".format(
                image_type.value,
                release,
            )
        )


    def daily_image(self, release, image_type: ImageType = ImageType.GENERIC):
        """Find the id of the latest image for a particular release.

        Args:
            release: string, Ubuntu release to look for

        Returns:
            string, path to latest daily image

        """
        self._log.debug("finding daily Ubuntu image for %s", release)
        return self._find_latest_image(release=release, image_type=image_type)

    def image_serial(self, image_id):
        """Find the image serial of the latest daily image for a particular release.

        Args:
            image_id: string, Ubuntu image id

        Returns:
            string, serial of latest image

        """
        raise NotImplementedError

    def delete_image(self, image_id):
        """Delete an image.

        Args:
            image_id: string, id of the image to delete
        """
        api_image_id = (
            self.compute.images()
            .get(project=self.project, image=os.path.basename(image_id))
            .execute()["id"]
        )
        response = (
            self.compute.images()
            .delete(
                project=self.project,
                image=api_image_id,
            )
            .execute()
        )

        raise_on_error(response)

    def get_instance(self, instance_id, name=None):
        """Get an instance by id.

        Args:
            instance_id: The instance ID returned upon creation

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
        )

    def launch(
        self,
        image_id,
        instance_type="n1-standard-1",
        user_data=None,
        wait=True,
        **kwargs,
    ):
        """Launch instance on GCE and print the IP address.

        Args:
            image_id: string, image ID for instance to use
            instance_type: string, instance type to launch
            user_data: string, user-data to pass to instance
            wait: boolean, wait for instance to come up
            kwargs: other named arguments to add to instance JSON

        """
        instance_name = "i{}-{}".format(next(self.instance_counter), self.tag)
        config = {
            "name": instance_name,
            "machineType": "zones/%s/machineTypes/%s"
            % (self.zone, instance_type),
            "disks": [
                {
                    "boot": True,
                    "autoDelete": True,
                    "initializeParams": {
                        "sourceImage": image_id,
                    },
                }
            ],
            "networkInterfaces": [
                {
                    "network": "global/networks/default",
                    "accessConfigs": [
                        {"type": "ONE_TO_ONE_NAT", "name": "External NAT"}
                    ],
                }
            ],
            "metadata": {
                "items": [
                    {
                        "key": "ssh-keys",
                        "value": "ubuntu:%s"
                        % self.key_pair.public_key_content,
                    }
                ]
            },
        }

        if self.service_account_email:
            config["serviceAccounts"] = [{"email": self.service_account_email}]

        if user_data:
            user_metadata = {"key": "user-data", "value": user_data}
            config["metadata"]["items"].append(user_metadata)

        operation = (
            self.compute.instances()
            .insert(project=self.project, zone=self.zone, body=config)
            .execute()
        )
        raise_on_error(operation)

        result = (
            self.compute.instances()
            .get(
                project=self.project,
                zone=self.zone,
                instance=instance_name,
            )
            .execute()
        )
        raise_on_error(result)

        instance = self.get_instance(result["id"], name=result["name"])
        if wait:
            self._wait_for_operation(operation, operation_type="zone")
            instance.wait()

        return instance

    def snapshot(self, instance: GceInstance, clean=True, **kwargs):
        """Snapshot an instance and generate an image from it.

        Args:
            instance: Instance to snapshot
            clean: run instance clean method before taking snapshot

        Returns:
            An image id
        """
        response = (
            self.compute.disks()
            .list(project=self.project, zone=self.zone)
            .execute()
        )

        instance_disks = [
            disk for disk in response["items"] if disk["name"] == instance.name
        ]

        if len(instance_disks) > 1:
            raise Exception(
                "Snapshotting an image with multiple disks not supported"
            )

        instance.shutdown()

        snapshot_name = "{}-image".format(instance.name)
        operation = (
            self.compute.images()
            .insert(
                project=self.project,
                body={
                    "name": snapshot_name,
                    "sourceDisk": instance_disks[0]["selfLink"],
                },
            )
            .execute()
        )
        raise_on_error(operation)
        self._wait_for_operation(operation)

        return "projects/{}/global/images/{}".format(
            self.project, snapshot_name
        )

    def _wait_for_operation(
        self, operation, operation_type="global", sleep_seconds=300
    ):
        response = None
        kwargs = {"project": self.project, "operation": operation["name"]}
        if operation_type == "zone":
            kwargs["zone"] = self.zone
            api = self.compute.zoneOperations()
        else:
            api = self.compute.globalOperations()
        for _ in range(sleep_seconds):
            try:
                response = api.get(**kwargs).execute()
            except ConnectionResetError:
                # This exception is known to be raised by GCE every so often:
                # https://github.com/canonical/pycloudlib/issues/101.
                response = {
                    "status": "ConnectionResetError",
                    "statusMessage": "n/a",
                }
            else:
                if response["status"] == "DONE":
                    break
            time.sleep(1)
        else:
            raise Exception(
                "Expected DONE state, but found {} after waiting {} seconds. "
                "Check GCE console for more details. \n"
                "Status message: {}".format(
                    response["status"],
                    sleep_seconds,
                    response["statusMessage"],
                )
            )
