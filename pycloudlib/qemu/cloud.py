# This file is part of pycloudlib. See LICENSE file for license information.
"""Cloud class for QEMU."""

import os
import re
import shutil
import subprocess
from itertools import count
from pathlib import Path
from typing import List, Optional, Tuple

import paramiko
import requests

from pycloudlib.cloud import BaseCloud
from pycloudlib.config import ConfigFile
from pycloudlib.errors import (
    ImageNotFoundError,
    MissingPrerequisiteError,
    PycloudlibError,
)
from pycloudlib.qemu.instance import QemuInstance
from pycloudlib.qemu.util import get_free_port
from pycloudlib.util import UBUNTU_RELEASE_VERSION_MAP, add_key_to_cloud_config


class Qemu(BaseCloud):
    """QEMU Cloud Class."""

    _type = "qemu"

    def __init__(
        self,
        tag: str,
        timestamp_suffix: bool = True,
        config_file: Optional[ConfigFile] = None,
    ):
        """Initialize QemuCloud cloud class.

        Args:
            tag: string used to name and tag resources with
            timestamp_suffix: Append a timestamped suffix to the tag string.
            config_file: path to pycloudlib configuration file
        """
        super().__init__(
            tag=tag,
            timestamp_suffix=timestamp_suffix,
            config_file=config_file,
            required_values=[],
        )
        self.image_dir = Path(os.path.expandvars(self.config["image_dir"]))
        if not self.image_dir.exists():
            raise ValueError(
                f"QEMU image_dir must be a valid path, not '{self.image_dir}'"
            )
        self.working_dir = Path(
            os.path.expandvars(self.config.get("working_dir", "/tmp"))
        )

        if not self.working_dir.exists():
            raise ValueError(
                "QEMU working_dir must be a valid path, "
                f"not '{self.working_dir}'"
            )
        self.qemu_binary = self.config.get("qemu_binary", "qemu-system-x86_64")

        if not all(
            [
                shutil.which(self.qemu_binary),
                shutil.which("qemu-img"),
                shutil.which("genisoimage"),
            ]
        ):
            raise MissingPrerequisiteError(
                "QEMU requires qemu-system-x86_64, qemu-img, and genisoimage "
                "to be installed. On Ubuntu, these can be installed with "
                "'sudo apt install qemu-system-x86 qemu-utils genisoimage'"
            )

        self.parent_dir = self.working_dir / f"pycl-qemu-{self.tag}"
        self.parent_dir.mkdir(parents=True, exist_ok=True)
        self._log.info(
            "Using '%s' as parent directory for all QEMU artifacts created",
            self.parent_dir,
        )
        self.current_count = count()

    def _get_available_file(self, path: Path) -> Path:
        """Get the next available file in a directory.

        Args:
            path: Path, directory to search

        Returns:
            Path, next available file

        """
        if path.is_dir():
            check = f"{path}-%i"
        else:
            check = f"{path.parent}/{path.stem}-%i{path.suffix}"
        while True:
            path = Path(check % next(self.current_count))
            if not path.exists():
                return path

    def delete_image(self, image_id, **kwargs):
        """Delete an image.

        Args:
            image_id: string, id of the image to delete
            **kwargs: dictionary of other arguments to pass to delete_image
        """
        image_file = Path(image_id)
        if image_file.exists():
            image_file.unlink()
        else:
            self._log.debug(
                "Cannot delete image %s as it does not exist", image_file
            )

    def _download_file(self, url: str, dest: Path):
        """Download a file from a url to a destination.

        Args:
            url: string, url to download from
            dest: Path, destination to download to
        """
        resp = requests.get(url, stream=True, timeout=300)
        resp.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

    def _get_kernel_name_from_series(self, release: str) -> str:
        """Get the kernel name for a particular release.

        Args:
            release: Release to use

        Returns:
            A string with the kernel name for the specified release.
        """
        if release in UBUNTU_RELEASE_VERSION_MAP:
            prefix = release
        else:
            prefix = f"ubuntu-{release}"

        return f"{prefix}-server-cloudimg-amd64-vmlinuz-generic"

    def _get_latest_image(self, base_url, release, img_name) -> str:
        """Download the latest image for a particular release.

        Args:
            release: The release to look for

        Returns:
            A string containing the path to the latest released image ID
            for the specified release.
        """
        resp = requests.get(base_url, timeout=5)
        resp.raise_for_status()
        match = re.search(
            r"<title>Ubuntu.*\[(?P<date>[^]]+).*</title>", resp.text
        )
        if not match:
            raise PycloudlibError(f"Could not parse url: {base_url}")
        date = match["date"]

        img_url = f"{base_url}/{img_name}"

        kernel_name = self._get_kernel_name_from_series(release)
        kernel_url = f"{base_url}/unpacked/{kernel_name}"

        download_dir = Path(self.image_dir, release, date)
        try:
            download_dir.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            img_files = sorted(list(download_dir.glob("*.img")))
            if img_files:
                self._log.debug("Image already exists, skipping download")
                return str(img_files[0].absolute())
        self._download_file(img_url, download_dir / img_name)
        self._download_file(kernel_url, download_dir / kernel_name)
        return str(Path(download_dir, img_name).absolute())

    def released_image(self, release, **kwargs):
        """ID of the latest released image for a particular release.

        If an image for this series from any date has been downloaded,
        it will be used.

        Args:
            release: The release to look for

        Returns:
            A single string with the latest released image ID for the
            specified release.

        """
        base_url = (
            f"https://cloud-images.ubuntu.com/releases/{release}/release"
        )
        release_number = UBUNTU_RELEASE_VERSION_MAP[release]
        return self._get_latest_image(
            base_url=base_url,
            release=release_number,
            img_name=f"ubuntu-{release_number}-server-cloudimg-amd64.img",
        )

    def daily_image(self, release: str, **kwargs):
        """ID of the latest daily image for a particular release.

        Download the latest daily image unless it already exists.

        Args:
            release: The release to look for

        Returns:
            A single string with the latest daily image ID for the
            specified release.

        """
        return self._get_latest_image(
            base_url=f"https://cloud-images.ubuntu.com/{release}/current",
            release=release,
            img_name=f"{release}-server-cloudimg-amd64.img",
        )

    def image_serial(self, image_id):
        """Find the image serial of the latest daily image for a release.

        Args:
            image_id: string, Ubuntu image id

        Returns:
            string, serial of latest image

        """
        raise NotImplementedError

    def get_instance(self, instance_id, **kwargs) -> QemuInstance:
        """Get an instance by id.

        Args:
            instance_id: The id for this instance. For QEMU this takes the
                form of <instance_path>::<ssh_port>::<telnet_port>

        Returns:
            An instance object to use to manipulate the instance further.

        """
        return QemuInstance(
            key_pair=self.key_pair,
            instance_id=instance_id,
            handle=None,
            username=kwargs.get("username"),
        )

    def _create_seed_iso(
        self,
        instance_dir: Path,
        user_data: Optional[str],
        meta_data: Optional[str],
        vendor_data: Optional[str] = None,
        network_config: Optional[str] = None,
    ) -> Optional[Path]:
        """Create seed iso for passing cloud-init user data.

        Create a directory (if not exists) using the instance name, and drop
        user-data and meta-data into it. Then create the seed iso at
        `instance-name`.iso

        If the genisoimage dependency is a problem,
        https://github.com/clalancette/pycdlib
        is a pure python library that could be used

        Args:
            instance_dir: directory to create seed iso in
            user_data: cloud-init user data
            meta_data: cloud-init meta data
            vendor_data: cloud-init vendor data
            network_config: cloud-init network config

        Returns:
            Path, path to seed iso
        """
        if not (user_data or meta_data or vendor_data):
            self._log.warning(
                "Not creating seed iso as there is no user data, meta data, "
                "or vendor data."
            )
            return None

        user_data_path = instance_dir / "user-data"
        meta_data_path = instance_dir / "meta-data"
        user_data_path.touch()
        meta_data_path.touch()

        if user_data:
            user_data_path.write_text(user_data, encoding="utf-8")

        if meta_data:
            meta_data_path.write_text(meta_data, encoding="utf-8")

        iso_path = instance_dir / "seed.iso"

        args = [
            "genisoimage",
            "-output",
            str(iso_path),
            "-volid",
            "cidata",
            "-joliet",
            "-rock",
            "-input-charset",
            "UTF-8",
            str(user_data_path),
            str(meta_data_path),
        ]

        # Vendor data is entirely optional, so don't create it automatically
        if vendor_data:
            vendor_data_path = instance_dir / "vendor-data"
            vendor_data_path.write_text(vendor_data, encoding="utf-8")
            args.append(str(vendor_data_path))

        if network_config:
            network_config_path = instance_dir / "network-config"
            network_config_path.write_text(network_config, encoding="utf-8")
            args.append(str(network_config_path))

        subprocess.run(
            args,
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return iso_path

    def _create_qcow_image(self, instance_path: Path, base_image: Path):
        """Create a qcow image from original iso.

        This is so we can make cheap destructive changes without modifying
        the original image. Also add a GB to the image size so we can
        we have enough space to write changes.

        Args:
            instance_path: Path, path to instance image
            base_image: Path, path to base image
        """
        subprocess.run(
            [
                "qemu-img",
                "create",
                "-f",
                "qcow2",
                "-b",
                base_image,
                "-F",
                "qcow2",
                str(instance_path),
                "10G",  # This space is only taken when needed
            ],
            check=True,
        )

    def _get_ubuntu_kernel_from_image_dir(self, image: Path) -> Optional[Path]:
        kernels = list(
            image.parent.glob("*-server-cloudimg-amd64-vmlinuz-generic")
        )
        if len(kernels) != 1:
            self._log.warning("Unable to find kernel for image: %s", image)
            return None
        return kernels[0].absolute()

    def _find_base_image(self, image_id: str) -> Path:
        if Path(image_id).exists():
            base_image = Path(image_id)
        elif Path(self.image_dir, image_id).exists():
            base_image = Path(self.image_dir, image_id)
        else:
            raise ImageNotFoundError(
                resource_id=image_id,
                message=(
                    f"Could not find '{image_id}' as absolute path "
                    f"or in '{self.image_dir}'."
                ),
            )
        self._log.debug("Using base image: %s", base_image)
        return base_image

    def _parse_instance_type(self, instance_type: str) -> Tuple[int, int]:
        cpu_mem = re.search(r"^c(?P<cpus>\d+)m(?P<memory>\d+$)", instance_type)
        if not cpu_mem:
            raise ValueError(
                "instance_type must be in the form of c#m#, not "
                f"{instance_type}"
            )
        return int(cpu_mem["cpus"]), int(cpu_mem["memory"])

    def _get_kernel_path(
        self, kernel_path, kernel_cmdline: str, image_id, base_image
    ) -> Optional[Path]:
        kernel = None
        if kernel_cmdline and not kernel_path:
            kernel = self._get_ubuntu_kernel_from_image_dir(image=base_image)
            if not kernel:
                raise PycloudlibError(
                    f"Could not find kernel for image_id: {image_id}. "
                    "Please specify kernel_path."
                )
        return kernel

    def _update_kernel_cmdline(self, kernel_cmdline: str) -> str:
        default_kernel_args = ""
        if "root=" not in kernel_cmdline:
            default_kernel_args += "root=/dev/sda1 "
        if "console=" not in kernel_cmdline:
            default_kernel_args += "console=ttyS0 "
        return default_kernel_args + kernel_cmdline

    # pylint:disable=R0914
    def launch(
        self,
        image_id: str,
        instance_type="c1m1500",
        user_data=None,
        meta_data=None,
        vendor_data=None,
        network_config=None,
        kernel_cmdline="",
        kernel_path=None,
        no_seed_iso=False,
        username: Optional[str] = None,
        launch_args: Optional[List[str]] = None,
        **kwargs,
    ) -> QemuInstance:
        """Launch an instance.

        If user_data is passed, a seed iso will be created to be used as a
        NoCloud datasource. If user_data is not provided, a seed iso will
        not be created. User data can also be passed within the kernel_cmdline
        parameter.

        Args:
            image_id: image ID to use for the instance.
                Can be either an absolute path to an image, or a path
                relative to the image_dir.
            instance_type: Type of instance to create. For QEMU, this is
                in the form of c#m#, where # is the number of cpus and
                memory in MB.
            user_data: used by cloud-init to run custom scripts/configuration
            meta_data: used by cloud-init for custom metadata
            vendor_data: used by cloud-init for custom vendor data
            network_config: used by cloud-init for custom network data
            kernel_cmdline: kernel command line arguments
            kernel_path: path to kernel to use
            no_seed_iso: if True, do not create a seed iso
            username: username to use for ssh connection
            launch_args: list of additional arguments to pass to qemu


        Returns:
            An instance object to use to manipulate the instance further.

        """
        # Start with early validation of parameters
        base_image = self._find_base_image(image_id=image_id)
        cpus, memory = self._parse_instance_type(instance_type=instance_type)

        # Next create the dir to contain all of the instance artifacts
        instance_dir = self._get_available_file(
            self.parent_dir / Path(image_id).stem
        )
        instance_dir.mkdir()
        self._log.info(
            "Using instance dir '%s' for new instance launched from '%s'",
            instance_dir,
            image_id,
        )

        # We make a QCOW image from the base image so we can make
        # destructive changes without modifying the original image
        instance_path = instance_dir / "inst.qcow2"
        self._create_qcow_image(
            instance_path=instance_path, base_image=base_image
        )

        ssh_port = get_free_port()
        telnet_port = get_free_port()
        socket_path = instance_dir / "qmp-socket"
        qemu_args = [
            self.qemu_binary,
            "-enable-kvm",
            "-cpu",
            "host",
            "-smp",
            f"cpus={cpus}",
            "-m",
            f"size={memory}",
            "-net",
            "nic",
            "-net",
            f"user,hostfwd=tcp::{ssh_port}-:22",
            "-hda",
            str(instance_path),
            "-nographic",
            "-chardev",
            f"socket,id=char0,logfile={instance_dir / 'console.log'},"
            f"host=0.0.0.0,port={telnet_port},telnet=on,server=on,"
            "wait=off,mux=on",
            "-serial",
            "chardev:char0",
            "-qmp",
            f"unix:{socket_path},server,wait=off",
            "-no-shutdown",
        ]

        if not no_seed_iso:
            # By default, even if no user data is passed, we'll need to
            # use NoCloud and create a seed iso, otherwise we have no
            # way of accessing our instance
            seed_path = self._create_seed_iso(
                instance_dir=instance_dir,
                user_data=add_key_to_cloud_config(
                    public_key=self.key_pair.public_key_content,
                    user_data=user_data,
                ),
                meta_data=meta_data,
                vendor_data=vendor_data,
                network_config=network_config,
            )

            if seed_path:
                driver = f"driver=raw,file={str(seed_path)},if=virtio"
                qemu_args.extend(["-drive", driver])

        kernel_path = self._get_kernel_path(
            kernel_path=kernel_path,
            kernel_cmdline=kernel_cmdline,
            image_id=image_id,
            base_image=base_image,
        )

        if kernel_path:
            kernel_cmdline = self._update_kernel_cmdline(
                kernel_cmdline=kernel_cmdline
            )
            qemu_args.extend(
                ["-kernel", str(kernel_path), "-append", kernel_cmdline]
            )

        if launch_args:
            qemu_args.extend(launch_args)

        self._log.info("Launching qemu with args: %s", qemu_args)
        handle = subprocess.Popen(  # pylint: disable=R1732
            qemu_args,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,  # Ensure process can outlive parent
        )
        instance = QemuInstance(
            key_pair=self.key_pair,
            instance_id=f"{instance_path}::{ssh_port}::{telnet_port}",
            handle=handle,
            username=username,
        )
        self.created_instances.append(instance)

        return instance

    def snapshot(self, instance: QemuInstance, clean=True, **kwargs) -> str:
        """Snapshot an instance and generate an image from it.

        Args:
            instance: Instance to snapshot
            clean: run instance clean method before taking snapshot

        Returns:
            An image id

        """
        if clean:
            self._log.debug("Cleaning before snapshot")
            try:
                instance.clean()
            except paramiko.ssh_exception.SSHException as e:
                self._log.warning(
                    "Failed to clean instance before snapshot: %s", e
                )

        self._log.debug("Shutting down before snapshot")
        instance.shutdown()

        snapshot_path = self._get_available_file(
            self.parent_dir / f"{Path(instance.instance_path).stem}-s.qcow2"
        )
        subprocess.run(
            [
                "qemu-img",
                "create",
                "-f",
                "qcow2",
                str(snapshot_path),
                "10G",
            ],
            check=True,
        )
        subprocess.run(
            [
                "qemu-img",
                "convert",
                "-O",
                "qcow2",
                "-p",
                instance.instance_path,
                str(snapshot_path),
                # Since we've shutdown the image, this should be safe
                "--force",
            ],
            check=True,
        )
        self._log.info(
            "Created snapshot '%s' from instance '%s'",
            snapshot_path,
            instance.instance_path,
        )
        self.created_images.append(str(snapshot_path))

        return str(snapshot_path)

    def list_keys(self):
        """List ssh key names present on the cloud for accessing instances.

        Returns:
           A list of strings of key pair names accessible to the cloud.

        """
        raise NotImplementedError

    def clean(self) -> List[Exception]:
        """Cleanup ALL artifacts associated with this Cloud instance.

        This includes all instances, snapshots, resources, etc.
        To ensure cleanup isn't interrupted, any exceptions raised during
        cleanup operations will be collected and returned.
        """
        exceptions = super().clean()
        if not self.parent_dir.exists():
            return exceptions

        # Remove the parent dir including all contents
        self._log.info("Removing parent dir: %s", self.parent_dir)
        try:
            shutil.rmtree(self.parent_dir)
        except Exception as e:  # pylint: disable=broad-except
            exceptions.append(e)

        return exceptions
