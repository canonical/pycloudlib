"""LXD/LXD images' related functionalities."""
import functools
import itertools
import json
from typing import Any, List, Optional, Sequence, Tuple

from pycloudlib.util import subp

_REMOTE_DAILY = "ubuntu-daily"
_REMOTE_RELEASE = "ubuntu"


def find_last_fingerprint(
    daily: bool,
    release: str,
    is_container: bool,
    arch: str,
) -> Optional[str]:
    """Find last LXD image fingerprint.

    Args:
        daily: boolean, search on daily remote
        release: string, Ubuntu release to look for
        is_container: boolean, indicating whether it is container or not
        arch: string, architecture to use

    Returns:
        string, LXD fingerprint of latest image if found
    """
    remote = _REMOTE_DAILY if daily else _REMOTE_RELEASE
    remote += ":"
    base_filters = (
        ("architecture", arch),
        ("release", release),
        ("label", "daily" if daily else "release"),
    )
    filters = (
        *base_filters,
        ("type", "container" if is_container else "virtual-machine"),
    )
    find_images = functools.partial(_find_images, remote)
    found_images: Any = find_images(filters)

    # Note: This block is needed to support lxd <= 4
    if not found_images:
        if is_container:
            filters = (*base_filters, ("type", "squashfs"))
            found_images = iter(find_images(filters))
        else:
            filters_kvm = (*base_filters, ("type", "disk-kvm.img"))
            filters_disk1 = (*base_filters, ("type", "disk1.img"))
            filters_uefi1 = (*base_filters, ("type", "uefi1.img"))
            found_images = itertools.chain.from_iterable(
                map(
                    find_images,
                    (filters_kvm, filters_disk1, filters_uefi1),
                )
            )
    try:
        image = next(iter(found_images))
    except StopIteration:
        return None
    return "%s%s" % (remote, image["fingerprint"])


def find_release(image_id: str) -> Optional[str]:
    """Extract the base release from the image_id.

    Args:
        image_id: string, [<remote>:]<image identifier>, the image to
                  determine the release of

    Returns:
        A string containing the base release from the image_id or None if
        not found.
    """
    release = None
    images = _find_images(image_id)
    if not images:
        return release
    image_info = images[0]

    properties = image_info.get("properties")
    if not properties:
        return release

    os = properties.get("os")
    if not os:
        return release
    # images: images have "Ubuntu", ubuntu: images have "ubuntu"
    if os.lower() == "ubuntu":
        release = properties.get("release")

    return release


def find_image_serial(image_id: str) -> Optional[str]:
    """Find the image serial of a given LXD image.

    Args:
        image_id: LXD image fingerprint

    Returns:
        serial of latest image
    """
    if ":" not in image_id:
        remote = _REMOTE_DAILY
    else:
        remote, image_id = image_id.split(":", 1)
    filters = (("fingerprint", image_id),)
    image = _find_images(remote, filters)
    if not image:
        return None
    return image[0]["properties"]["serial"]


def _normalize_remote(remote: Optional[str] = None) -> str:
    if not remote:
        remote = _REMOTE_DAILY
    if ":" not in remote:
        remote += ":"
    return remote


def _find_images(
    remote: str, filters: Optional[Sequence[Tuple[str, str]]] = None
) -> List[dict]:
    """Find the images filtered by filters criteria.

    Args:
        remote: LXD's remote
        filters: Key-value filters to match on

    Returns:
        list of dictionaries with image's info
    """
    remote = _normalize_remote(remote)
    cmd = [
        "lxc",
        "image",
        "list",
        remote,
        "--format=json",
    ]
    if filters is not None:
        compiled_filters = map(lambda f: f"{f[0]}={f[1]}", filters)
        cmd.extend(compiled_filters)
    return json.loads(subp(cmd))
