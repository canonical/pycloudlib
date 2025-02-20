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

    Attributes:
        networking_type: NetworkingType, type of networking configuration
            (ipv4, ipv6, dual-stack, auto). Default: "auto"
        private: bool, whether interface should be private only or not. Default: False

    """

    networking_type: NetworkingType = NetworkingType.AUTO
    private: bool = False

    def __post_init__(self):
        """Post initialization checks for NetworkingConfig."""
        if not isinstance(self.networking_type, NetworkingType):
            raise ValueError("Invalid networking type provided")

    def to_dict(self) -> dict:
        """Convert the NetworkingConfig to a dictionary representation."""
        return {
            "networking_type": self.networking_type.value,
            "private": self.private,
        }
