"""Module containing errors specific to gce."""

from pycloudlib.errors import PycloudlibException


class GceException(PycloudlibException):
    """Represents an error from the GCE API."""
