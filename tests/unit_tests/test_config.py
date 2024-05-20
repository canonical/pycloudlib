"""Test the config.py module."""

import os
from io import StringIO

import mock
import pytest

from pycloudlib.config import parse_config


def test_get_item_override():
    """Test the __getitem__ method override."""
    config = parse_config(StringIO(""))
    try:
        config["not_there"]
    except KeyError as e:
        assert str(e) == (
            "'not_there must be defined in pycloudlib.toml to make this call'"
        )


class TestParseConfig:
    """Test the parse_config function in config.py."""

    @mock.patch("toml.load")
    def test_argument_priority(self, m_load):
        """Test that config argument gets evaluated over files."""
        parse_config(StringIO(""))
        assert len(m_load.call_args_list) == 1
        assert "StringIO" in str(m_load.call_args_list)

    @mock.patch("toml.load")
    def test_env_var_priority(self, m_load):
        """Test that env var argument gets evaluated over files."""
        os.environ["PYCLOUDLIB_CONFIG"] = "/some/path"
        parse_config()
        assert len(m_load.call_args_list) == 1
        assert "/some/path" in str(m_load.call_args_list)

    @mock.patch("toml.load", side_effect=FileNotFoundError)
    def test_try_order(self, m_load):
        """Test order of config file checking."""
        os.environ["PYCLOUDLIB_CONFIG"] = "/some/path"
        with pytest.raises(ValueError):
            parse_config(StringIO(""))
        expected_order = [
            "StringIO",
            "/some/path",
            ".config/pycloudlib.toml",
            "/etc/pycloudlib.toml",
        ]
        for expected, actual in zip(expected_order, m_load.call_args_list):
            assert expected in str(actual)
