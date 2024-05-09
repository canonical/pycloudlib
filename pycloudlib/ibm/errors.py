"""Module containing errors specific to ibm."""

from pycloudlib.errors import PycloudlibException


class IBMException(PycloudlibException):
    """IBM exception root."""


class IBMCapacityException(IBMException):
    """Exception when there is not enough capacity to create a resource."""
