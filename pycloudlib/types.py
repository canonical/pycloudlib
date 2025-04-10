# This file is part of pycloudlib. See LICENSE file for license information.
"""This module contains types and enums used by pycloudlib."""

import enum
from dataclasses import dataclass


@enum.unique
class ImageType(enum.Enum):
    """Allowed image types when launching cloud images."""

    GENERIC = "generic"
    MINIMAL = "minimal"
    PRO = "Pro"
    PRO_FIPS = "Pro FIPS"


@enum.unique
class NetworkingType(enum.Enum):
    """Allowed networking configurations for instances."""

    IPV4 = "ipv4"
    IPV6 = "ipv6"
    DUAL_STACK = "dual-stack"
    AUTO = "auto"

    def __str__(self):
        """Return the string representation of NetworkingType enum."""
        return self.value


@dataclass
class NetworkingConfig:
    """
    Dataclass for specifying or representing networking configuration.

    By default, networking_type is set to AUTO and private is set to False to allow for a publicly
    accessible instance.

    Descriptions of possible configurations:
    - If private is set to True, the instance will be accessible only within the cloud network.
    - If networking_type is set to AUTO, the cloud provider will automatically choose the
    networking configuration (default/current behavior).
    - If networking_type is set to IPV4, the instance will only be assigned IPv4 addresses
    (if private is False, the instance will have a public IPv4 address).
    - If networking_type is set to IPV6, the instance will only be assigned IPv6 addresses
    (if private is False, the instance will have a public IPv6 address).
    - If networking_type is set to DUAL_STACK, the instance will be assigned both IPv4 and IPv6
    addresses (if private is False, the instance will have both public IPv4 and IPv6 addresses).
    """

    networking_type: NetworkingType = NetworkingType.AUTO
    private: bool = False

    def __post_init__(self):
        """Post initialization checks for NetworkingConfig."""
        if not isinstance(self.networking_type, NetworkingType):
            raise ValueError("Invalid networking type provided")
        if not isinstance(self.private, bool):
            raise ValueError("Invalid private value provided (must be a boolean)")

    def to_dict(self) -> dict:
        """Convert the NetworkingConfig to a dictionary representation."""
        return {
            "networking_type": self.networking_type.value,
            "private": self.private,
        }


@dataclass
class ImageInfo:
    """Dataclass that represents an image on any given cloud."""

    image_id: str
    image_name: str

    def __str__(self):
        """Return a human readable string representation of the image."""
        return f"{self.image_name} [id: {self.image_id}]"

    def __repr__(self):
        """Return a string representation of the image."""
        return f"ImageInfo(id={self.image_id}, name={self.image_name})"

    def __eq__(self, other):
        """
        Check if two ImageInfo objects represent the same image.

        Only the id is used for comparison since this should be the unique identifier for an image.
        """
        # Allow for comparing an ImageInfo object with just an ID string
        if isinstance(other, str):
            return self.image_id == other
        # Do not allow for comparing with other types
        if not isinstance(other, ImageInfo):
            return False
        # Check if the image IDs are the same when comparing two ImageInfo objects
        return self.image_id == other.image_id

    def __dict__(self):
        """Return a dictionary representation of the image."""
        return {"image_id": self.image_id, "image_name": self.image_name}
