"""Test types module."""

from pycloudlib.types import NetworkingConfig
import pytest
import re


def test_networking_config_post_init_raises_exceptions():
    """Test NetworkingConfig post init checks."""
    with pytest.raises(
        ValueError,
        match="Invalid networking type provided",
    ):
        NetworkingConfig(networking_type="invalid")
    with pytest.raises(
        ValueError,
        match=re.escape("Invalid private value provided (must be a boolean)"),
    ):
        NetworkingConfig(private="not_a_boolean")
