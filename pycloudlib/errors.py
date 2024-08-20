"""Module containing pycloudlib errors.

Each cloud can have specific errors, please refer to each
`pycloudlib.<cloud>.errors` module.
"""

import enum
from typing import List, Optional


class PycloudlibException(Exception):
    """Root pycloudlib exception.

    This exception is not meant to be raised by pycloudlib. The intention
    is that every custom pycloudlib exception will inherit from this one,
    allowing client code to catch any exception by catching this one.
    """


class PycloudlibError(PycloudlibException):
    """Error that doesn’t fall in any of the other categories."""


class ResourceType(enum.Enum):
    """Represent types of resources."""

    IMAGE = enum.auto()
    INSTANCE = enum.auto()
    NETWORK = enum.auto()

    def __str__(self) -> str:  # noqa: D105
        if self == self.INSTANCE:
            return "instance"
        if self == self.IMAGE:
            return "image"
        if self == self.NETWORK:
            return "network"
        raise NotImplementedError


class ResourceNotFoundError(PycloudlibException):
    """Raised when a resource is not found.

    Examples:
    ---------
    >>> e = ResourceNotFoundError(ResourceType.IMAGE, "id-123")
    >>> e.resource_id
    'id-123'
    >>> raise e  # doctest: +ELLIPSIS
    Traceback (most recent call last):
        ...
    pycloudlib.errors.ResourceNotFoundError: \
Could not locate the resource type `image`: id=id-123
    """

    def __init__(
        self,
        resource_type: ResourceType,
        resource_id: Optional[str] = None,
        resource_name: Optional[str] = None,
        **kwargs,
    ):
        """Init method.

        :param resource_type: Instance of `ResourceType`
        :param resource_id: Resource's id
        :param resource_type: Resource's name
        """
        super().__init__()
        self.resource_type = resource_type
        self.resource_id = resource_id
        self.resource_name = resource_name
        self._extra_info = kwargs

    def __str__(self) -> str:  # noqa: D105
        resource_info = self.__render_resource()
        msg = f"Could not locate the resource type `{self.resource_type}`"
        if resource_info:
            msg += f": {resource_info}"
        return msg

    def __render_resource(self) -> str:
        parts = []
        if self.resource_id:
            parts.append(f"id={self.resource_id}")
        if self.resource_name:
            parts.append(f"name={self.resource_name}")
        if self._extra_info:
            parts.extend(
                map(
                    lambda item: f"{item[0]}={item[1]}",
                    self._extra_info.items(),
                )
            )
        return ", ".join(parts)


class ImageNotFoundError(ResourceNotFoundError):
    """Sepecialized's `ResourceNotFoundError` for images."""

    def __init__(self, *args, **kwargs):  # noqa: D107
        super().__init__(ResourceType.IMAGE, *args, **kwargs)


class InstanceNotFoundError(ResourceNotFoundError):
    """Sepecialized's `ResourceNotFoundError` for instances."""

    def __init__(self, *args, **kwargs):  # noqa: D107
        super().__init__(ResourceType.INSTANCE, *args, **kwargs)


class NetworkNotFoundError(ResourceNotFoundError):
    """Sepecialized's `ResourceNotFoundError` for networks."""

    def __init__(self, *args, **kwargs):  # noqa: D107
        super().__init__(ResourceType.NETWORK, *args, **kwargs)


class CloudSetupError(PycloudlibException):
    """Raised if there is some problem with a pycloudlib's Cloud set up."""


class CloudError(PycloudlibException):
    """Represents errors coming from Cloud's SDKs."""


class PycloudlibTimeoutError(PycloudlibException):
    """Timeout error."""


class CleanupError(PycloudlibException):
    """Represents a list of exceptions that happen on resource cleanup.

    Don't be too eager to handle this one. If it gets caught and silently
    handled, you're likely to be leaking resources without realizing it.
    """


class MissingPrerequisiteError(PycloudlibException):
    """Raised when a prerequisite is missing."""


class InvalidTagNameError(PycloudlibException):
    """Raised when a tag for a cloud is invalid."""

    def __init__(self, tag: str, rules_failed: List[str]):
        """Init method.

        :param tag: The tag that failed validation
        :param rules_failed: List of rules that the tag failed
        """
        super().__init__()
        self.tag = tag
        self.rules_failed = rules_failed

    def __str__(self) -> str:
        """Return string representation of the error."""
        return f"Tag '{self.tag}' failed the following rules: {', '.join(self.rules_failed)}"
