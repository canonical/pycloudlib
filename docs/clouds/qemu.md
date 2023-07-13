# QEMU

The following page documents the QEMU cloud integration in pycloudlib.

## Support

Pycloudlib currently supports launching x86-64 Ubuntu images using
`qemu-system-x86_64` on an x86-64 host.

## Requirements

In addition to requirements specified in `setup.py`, on Ubuntu systems,
the QEMU datasource requires the following packages:

* qemu-system-x86
* qemu-utils  # for qemu-img
* genisoimage  # to create the cloud-init NoCloud seed image

## Configuration and Local Storage

QEMU instances require local directories to store images and instances.
These directories can be configured in the `pycloudlib.toml` file:

`image_dir` - Directory to look for images when launching instances.
  Also the directory to download images to where supported.

`working_dir` - Directory to store temporary instance data. This includes
  instance disks, snapshots, and other metadata.

`qemu_binary` - Path to the `qemu-system-x86_64` binary.

## Obtaining Images

While any x64-64 should be usable, Ubuntu images can be downloaded from the
Ubuntu cloud images website using the cloud `daily_image` and `released_image`
calls.

For example:

```python
cloud = Qemu(...)
cloud.released_image("jammy")
```

will return the path to the latest jammy image that has already been
downloaded by Pycloudlib. If no image exists, it will be downloaded
into the image_dir.

```python
cloud = Qemu(...)
cloud.daily_image("jammy")
```

will return the path to the latest jammy image that has been released.
If the image does not exist, it will be downloaded into the image_dir.

## Launching Instances

Launching instances with QEMU requires an `image_id`.

The `image_id` can either be an absolute path image, or a path relative
to the `image_dir`. It is most easily retrieved using the `daily_image` or
`released_image` calls.

The `instance_type` is in the form of `c<cpus>m<memory>`, where `<cpus>` is
the number of CPUs to allocate to the instance and `<memory>` is the amount
of memory to allocate to the instance in megabytes.

If `kernel_cmdline` is specified, it will be passed to the kernel as the
kernel command line. When specified, `kernel_path` must also be specified.
The `daily_image` and `released_image` calls will automatically download
the kernel for the image, so if these calls have been used to obtain the
image_id, the `kernel_path` is not required.

By default, pycloudlib will create a seed iso for the instance in order
to let cloud-init configure the instance. If `no_seed_iso` is set to
`True`, pycloudlib will not create a seed iso. This may be useful when
using the `kernel_cmdline` behavior or when using an image that already
has keys and/or passwords configured.

### Ports

Pycloudlib will allocate two local ports per instance to handle SSH and
telnet traffic. These ports are allocated in the range 18000-18100. This
information is logged to the console when launching an instance as well
as using the API via the `port` and `telnet_port` instance attributes.

The telnet port allows full serial interaction for cases where SSH is
not available or not working.

## Networking

Pycloudlib does not configure networking outside of mapping ports. By
default, the VM guest default route will be `10.0.2.2` if the VM needs
to access the host.

## QEMU Machine Protocol

Under the hood, Pycloudlib uses the QEMU Machine Protocol (QMP) to interact
with running VMs. While this is generally meant to be an implementation
detail, if needed,the socket file may be found in the `working_dir` with the
name `qmp-socket`.

A `QEMU Monitor` interface is not exposed.
