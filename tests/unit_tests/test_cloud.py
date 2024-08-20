"""Tests related to pycloudlib.cloud module."""

from io import StringIO
from textwrap import dedent
from typing import List

import mock
import pytest

from pycloudlib.cloud import BaseCloud
from pycloudlib.errors import InvalidTagNameError

# mock module path
MPATH = "pycloudlib.cloud."
CONFIG = """\
[base]

"""


class CloudSubclass(BaseCloud):
    """Create a concrete subclass of BaseCloud for testing."""

    def delete_image(self):
        """Skeletal delete_image."""

    def released_image(self, release, **kwargs):
        """Skeletal released_image."""

    def daily_image(self, release, **kwargs):
        """Skeletal daily_image."""

    def image_serial(self, image_id):
        """Skeletal image_serial."""

    def get_instance(self, instance_id):
        """Skeletal get_instance."""

    def launch(self, image_id, instance_type=None, user_data=None, **kwargs):
        """Skeletal launch."""

    def snapshot(self, instance, clean=True, **kwargs):
        """Skeletal snapshot."""

    def list_keys(self):
        """Skeletal list_keys."""


class TestBaseCloud:
    """Tests covering BaseCloud intialization."""

    def test_base_cloud_is_abstract(self):
        """The BaseCloud needs a concrete subclass to __init__."""
        with pytest.raises(TypeError) as exc_info:
            BaseCloud(  # pylint: disable=E0110
                tag="", config_file=StringIO(CONFIG)
            )
        assert "Can't instantiate abstract class BaseCloud" in str(
            exc_info.value
        )

    @pytest.mark.parametrize(
        "tag,timestamp_suffix,expected_tag",
        (
            ("a", None, "a-timestamp"),
            ("a", True, "a-timestamp"),
            ("a", False, "a"),
        ),
    )
    @mock.patch(MPATH + "get_timestamped_tag", return_value="a-timestamp")
    @mock.patch(MPATH + "getpass.getuser", return_value="crashoverride")
    def test_init_sets_timestamped_tag(
        self,
        _m_getuser,
        _m_get_timestamped_tag,
        tag,
        timestamp_suffix,
        expected_tag,
    ):
        """The timestamp_suffix param of true adds a tag timestamp suffix."""
        args = {"tag": tag}
        if timestamp_suffix in (True, False):
            args["timestamp_suffix"] = timestamp_suffix
        mycloud = CloudSubclass(config_file=StringIO(CONFIG), **args)
        assert expected_tag == mycloud.tag

    @mock.patch(MPATH + "getpass.getuser", return_value="root")
    def test_init_sets_key_pair_based_on_getuser(self, _m_getuser):
        """
        The default key_pair for the cloud is based on the current user.

        The root user is used as it's guaranteed to exist and has a
        well known $HOME. Also its $HOME is not under /home, so this
        verifies that we're not hardcoding /home/<user> paths.
        """
        mycloud = CloudSubclass(
            tag="tag", timestamp_suffix=False, config_file=StringIO(CONFIG)
        )
        assert mycloud.key_pair.name == "root"
        assert mycloud.key_pair.private_key_path == ("/root/.ssh/id_rsa")
        assert mycloud.key_pair.public_key_path == ("/root/.ssh/id_rsa.pub")

    def test_init_sets_key_pair_from_config(self):
        """The key_pair is set from the config file."""
        mycloud = CloudSubclass(
            tag="tag",
            timestamp_suffix=False,
            config_file=StringIO(
                dedent(
                    """
                [base]

                key_name = "some_name"
                public_key_path = "/home/asdf/.ssh/id_rsa.pub"
                private_key_path = "/home/asdf/.ssh/my_key"
                """
                )
            ),
        )
        assert mycloud.key_pair.name == "some_name"
        assert mycloud.key_pair.public_key_path == "/home/asdf/.ssh/id_rsa.pub"
        assert mycloud.key_pair.private_key_path == "/home/asdf/.ssh/my_key"

    def test_missing_private_key_in_ssh_config(self):
        """The key_pair assumes the private key name."""
        mycloud = CloudSubclass(
            tag="tag",
            timestamp_suffix=False,
            config_file=StringIO(
                dedent(
                    """
                [base]

                key_name = "some_name"
                public_key_path = "/home/asdf/.ssh/id_rsa.pub"
                """
                )
            ),
        )
        assert mycloud.key_pair.name == "some_name"
        assert mycloud.key_pair.public_key_path == "/home/asdf/.ssh/id_rsa.pub"
        assert mycloud.key_pair.private_key_path == "/home/asdf/.ssh/id_rsa"

    rule1 = "All letters must be lowercase"
    rule2 = "Must be between 1 and 63 characters long"
    rule3 = "Must not start or end with a hyphen"
    rule4 = "Must be alphanumeric and hyphens only"

    @pytest.mark.parametrize(
        "tag, rules_failed",
        [
            ("tag123", []),
            ("TAG", [rule1]),
            ("TAG-", [rule1, rule3]),
            ("-tag_", [rule3, rule4]),
            ("-", [rule3]),
            ("x" * 64, [rule2]),
            ("", [rule2]),
            ("x" * 63, []),
            ("x", []),
            ("t a_g", [rule4]),
        ],
    )
    def test_validate_tag(self, tag: str, rules_failed: List[str]):
        if len(rules_failed) == 0:
            # test that no exception is raised
            BaseCloud._validate_tag(tag)
        else:
            with pytest.raises(InvalidTagNameError) as exc_info:
                BaseCloud._validate_tag(tag)
            assert tag in str(exc_info.value)
            for rule in rules_failed:
                assert rule in str(exc_info.value)
