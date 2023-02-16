"""Test the errors.py module."""
import pytest

from pycloudlib.errors import ResourceNotFoundError, ResourceType


class TestResourceType:
    """Tests related to `ResourceType`."""

    @pytest.mark.parametrize(
        "item",
        list(map(lambda item: pytest.param(item, id=item.name), ResourceType)),
    )
    def test_str_representable(self, item):
        """Test that all instances of `ResourceType` are convertible to str."""
        assert str(item)


class TestResourceNotFoundError:
    """Tests related to `ResourceNotFoundError`."""

    @pytest.mark.parametrize(
        ["exception", "expected_msg"],
        [
            (
                ResourceNotFoundError(
                    resource_type=ResourceType.INSTANCE,
                    resource_id="id",
                    resource_name="name",
                    custom_key="custom_key",
                ),
                (
                    "Could not locate the resource type `instance`: "
                    "id=id, name=name, custom_key=custom_key"
                ),
            ),
            (
                ResourceNotFoundError(
                    resource_type=ResourceType.IMAGE,
                    resource_id="id",
                    custom_key="custom_key",
                ),
                (
                    "Could not locate the resource type `image`: "
                    "id=id, custom_key=custom_key"
                ),
            ),
            (
                ResourceNotFoundError(
                    resource_type=ResourceType.NETWORK,
                    resource_name="name",
                    custom_key="custom_key",
                ),
                (
                    "Could not locate the resource type `network`: "
                    "name=name, custom_key=custom_key"
                ),
            ),
            (
                ResourceNotFoundError(
                    resource_type=ResourceType.NETWORK,
                ),
                ("Could not locate the resource type `network`"),
            ),
        ],
    )
    def test_exception_message(self, exception, expected_msg):
        """Test that exceptions have correct error messages."""
        assert expected_msg == str(exception)
