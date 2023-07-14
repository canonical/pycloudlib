# This file is part of pycloudlib. See LICENSE file for license information.
"""VMWare Cloud type."""

import base64
import os
import shutil
import subprocess
from itertools import count
from typing import Optional

from pycloudlib.cloud import BaseCloud
from pycloudlib.config import ConfigFile
from pycloudlib.util import add_key_to_cloud_config
from pycloudlib.vmware.instance import VMWareInstance

SERIES_TO_TEMPLATE = {
    "focal": "TEMPLATE-cloud-init-focal",
    "jammy": "TEMPLATE-cloud-init-jammy",
}

METADATA = "instance-id: pycloudlib-vm"


class VMWare(BaseCloud):
    """VMWare Cloud class."""

    _type = "vmware"
    _instance_counter = count()

    def __init__(
        self,
        tag: str,
        timestamp_suffix: bool = True,
        config_file: Optional[ConfigFile] = None,
        *,
        server=None,
        username=None,
        password=None,
        datacenter=None,
        datastore=None,
        folder=None,
        insecure_transport=None,
    ):
        """Initialize VMWare cloud class.

        Args:
            tag: string used to name and tag resources with
            timestamp_suffix: Append a timestamped suffix to the tag string.
            config_file: path to pycloudlib configuration file
        """
        super().__init__(
            tag=tag,
            timestamp_suffix=timestamp_suffix,
            config_file=config_file,
            required_values=[
                server,
                username,
                password,
                datacenter,
                datastore,
                folder,
                insecure_transport,
            ],
        )
        server = server or self.config.get("server")
        username = username or self.config.get("username")
        password = password or self.config.get("password")
        datacenter = datacenter or self.config.get("datacenter")
        datastore = datastore or self.config.get("datastore")
        folder = folder or self.config.get("folder")
        insecure_transport = insecure_transport or self.config.get(
            "insecure_transport"
        )

        self.govc = shutil.which("govc")
        if not self.govc:
            raise ValueError(
                "'govc' must be installed and added to PATH. See "
                "https://github.com/vmware/govmomi/tree/main/govc#installation"
            )
        self.env = {
            "GOVC_INSECURE": "1" if insecure_transport else "0",
            "GOVC_URL": server,
            "GOVC_USERNAME": username,
            "GOVC_PASSWORD": password,
            "GOVC_DATACENTER": datacenter,
            "GOVC_DATASTORE": datastore,
            "GOVC_FOLDER": folder,
            "PATH": os.environ.get("PATH"),
        }

    def delete_image(self, image_id, **kwargs):
        """Delete an image.

        Args:
            image_id: string, id of the image to delete
        """
        if image_id in SERIES_TO_TEMPLATE.values():
            raise ValueError(
                f"{image_id} is a core template and cannot be deleted."
            )
        try:
            subprocess.run(
                ["govc", "vm.destroy", image_id], env=self.env, check=True
            )
        except subprocess.CalledProcessError as e:
            if "not found" not in str(e):
                raise

    def daily_image(self, release: str, **kwargs):
        """Return released_image for VMWare.

        We're relying on whatever has been created/uploaded, so the
        distinction between daily and released doesn't make sense.
        """
        return self.released_image(release, **kwargs)

    def released_image(self, release, **kwargs):
        """ID of the uploaded image for a particular release.

        Args:
            release: The release to look for

        Returns:
            A single string with the latest image ID for the specified release.

        """
        try:
            return SERIES_TO_TEMPLATE[release]
        except KeyError as e:
            raise ValueError(
                f"Could not find image for '{release}' release"
            ) from e

    def image_serial(self, image_id):
        """Find the image serial of the latest daily image for a release.

        Args:
            image_id: string, Ubuntu image id

        Returns:
            string, serial of latest image

        """
        raise NotImplementedError

    def get_instance(self, instance_id, **kwargs) -> VMWareInstance:
        """Get an instance by id.

        Args:
            instance_id:

        Returns:
            An instance object to use to manipulate the instance further.

        """
        return VMWareInstance(
            key_pair=self.key_pair, vm_id=instance_id, env=self.env
        )

    def launch(
        self,
        image_id: str,
        instance_type=None,
        user_data=None,
        **kwargs,
    ) -> VMWareInstance:
        """Launch an instance.

        Args:
            image_id: string, image ID to use for the instance
            instance_type: string, type of instance to create
            user_data: used by cloud-init to run custom scripts/configuration
            wait: wait for instance to be live
            **kwargs: dictionary of other arguments to pass to launch

        Returns:
            An instance object to use to manipulate the instance further.
        """
        if instance_type:
            self._log.warning("'instance_type' ignored on VMWare")

        instance_name = f"{self.tag}-{next(self._instance_counter)}"

        # VMWare does provide the option to pass a public key through the
        # mounted cdrom device using ovf xml, but then cloud-init will
        # detect the ovf datasource rather than the VMWare datasource.
        # If we want to use the VMWare datasource, there is no other
        # way to provide a public key other than through the userdata.
        user_data = add_key_to_cloud_config(
            self.key_pair.public_key_content, user_data
        )

        b64_metadata = base64.b64encode(METADATA.encode()).decode()
        b64_userdata = base64.b64encode(user_data.encode()).decode()

        subprocess.run(
            [
                "govc",
                "vm.clone",
                f"-vm={self.env['GOVC_FOLDER']}/{image_id}",
                "-on=false",
                f"-ds={self.env['GOVC_DATASTORE']}",
                instance_name,
            ],
            env=self.env,
            check=True,
        )

        instance = VMWareInstance(self.key_pair, instance_name, env=self.env)
        self.created_instances.append(instance)

        subprocess.run(
            [
                "govc",
                "vm.change",
                "-vm",
                instance_name,
                "-e",
                f"guestinfo.metadata={b64_metadata}",
                "-e",
                "guestinfo.metadata.encoding=base64",
                "-e",
                f"guestinfo.userdata={b64_userdata}",
                "-e",
                "guestinfo.userdata.encoding=base64",
            ],
            env=self.env,
            check=True,
        )

        instance.start()
        return instance

    def snapshot(self, instance, clean=True, **kwargs):
        """Snapshot an instance and generate an image from it.

        Args:
            instance: Instance to snapshot
            clean: run instance clean method before taking snapshot

        Returns:
            An image id
        """
        if clean:
            instance.clean()
        image_name = f"{instance.vm_id}-image"
        subprocess.run(
            [
                "govc",
                "vm.clone",
                f"-vm={self.env['GOVC_FOLDER']}/{instance.vm_id}",
                "-on=false",
                f"-ds={self.env['GOVC_DATASTORE']}",
                image_name,
            ],
            env=self.env,
            check=True,
        )

        self.created_images.append(image_name)

        return image_name
