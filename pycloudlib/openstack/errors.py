"""Module containing errors specific to openstack."""

from pycloudlib.errors import PycloudlibException


class OpenStackError(PycloudlibException):
    """OpenStack exception root."""


class OpenStackFlavorNotFound(OpenStackError):
    """Raised when an OpenStack's flavor is not found."""
