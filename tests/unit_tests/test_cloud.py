"""Tests related to pycloudlib.cloud module."""

from io import StringIO
import logging
from textwrap import dedent
from typing import List, Optional

import mock
import pytest

from pycloudlib.cloud import BaseCloud
from pycloudlib.errors import InvalidTagNameError, UnsetSSHKeyError

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

    def snapshot(self, instance, *, clean=True, keep=False, **kwargs):
        """Skeletal snapshot."""

    def list_keys(self):
        """Skeletal list_keys."""


@pytest.mark.mock_ssh_keys
class TestBaseCloud:
    """Tests covering BaseCloud intialization."""

    def test_base_cloud_is_abstract(self):
        """The BaseCloud needs a concrete subclass to __init__."""
        with pytest.raises(TypeError) as exc_info:
            BaseCloud(  # pylint: disable=E0110
                tag="", config_file=StringIO(CONFIG)
            )
        assert "Can't instantiate abstract class BaseCloud" in str(exc_info.value)

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

    @pytest.mark.dont_mock_ssh_keys
    @mock.patch(MPATH + "getpass.getuser", return_value="root")
    @mock.patch("os.path.expanduser", side_effect=lambda x: x.replace("~", "/root"))
    @mock.patch("os.path.exists", side_effect=lambda x: "/.ssh/id_rsa" in x)
    def test_init_sets_key_pair_based_on_getuser(
        self,
        _m_getuser,
        _m_expanduser,
        _m_exists,
    ):
        """
        The default key_pair for the cloud is based on the current user.

        The root user is used as it's guaranteed to exist and has a
        well known $HOME. Also its $HOME is not under /home, so this
        verifies that we're not hardcoding /home/<user> paths.
        """
        mycloud = CloudSubclass(tag="tag", timestamp_suffix=False, config_file=StringIO(CONFIG))
        assert mycloud.key_pair.name == "root"
        assert mycloud.key_pair.private_key_path == ("/root/.ssh/id_rsa")
        assert mycloud.key_pair.public_key_path == ("/root/.ssh/id_rsa.pub")

    @pytest.mark.dont_mock_ssh_keys
    @mock.patch("os.path.expanduser", side_effect=lambda x: x.replace("~", "/root"))
    @mock.patch("os.path.exists", side_effect=lambda x: "/.ssh/id_ed25519" in x)
    @mock.patch(MPATH + "getpass.getuser", return_value="root")
    def test_init_can_use_id_ed25519_key(
        self,
        _m_getuser,
        _m_expanduser,
        _m_exists,
    ):
        """
        Validates that key_pair uses the id_ed25519 key if id_rsa doesn't exist

        To do this, we mock the os.path.exists function to return True ONLY
        for the id_ed25519 key to simulate the absence of the id_rsa key.

        """
        mycloud = CloudSubclass(
            tag="tag",
            timestamp_suffix=False,
            config_file=StringIO(CONFIG),
        )

        id_ed25519_path = "/root/.ssh/id_ed25519.pub"

        assert mycloud.key_pair.name == "root"
        assert mycloud.key_pair.public_key_path == id_ed25519_path
        assert mycloud.key_pair.private_key_path == id_ed25519_path.replace(".pub", "")

    @pytest.mark.dont_mock_ssh_keys
    @mock.patch("os.path.expanduser", side_effect=lambda x: x.replace("~", "/root"))
    @mock.patch("os.path.exists", side_effect=lambda x: "/.ssh/id_rsa" in x)
    def test_init_sets_key_pair_from_config(self, _m_expanduser, _m_exists):
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

    @pytest.mark.dont_mock_ssh_keys
    @mock.patch("os.path.expanduser", side_effect=lambda x: x.replace("~", "/root"))
    @mock.patch("os.path.exists", side_effect=lambda x: "/.ssh/id_rsa" in x)
    def test_missing_private_key_in_ssh_config(self, _m_expanduser, _m_exists):
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

    @pytest.mark.dont_mock_ssh_keys
    @mock.patch("os.path.expanduser", side_effect=lambda x: x.replace("~", "/root"))
    @mock.patch("os.path.exists", return_value=False)
    def test_init_raises_error_when_no_ssh_keys_found(
        self,
        _m_expanduser,
        _m_exists,
        caplog,
    ):
        """
        Test that an error is raised when no SSH keys can be found.

        This test verifies that an error is raised when no SSH keys can be found in the default
        locations and no public key path is provided in the config file.
        """
        # set log level to Warning to ensure warning gets logged
        caplog.set_level(logging.WARNING)
        with pytest.raises(UnsetSSHKeyError) as exc_info:
            cloud = CloudSubclass(tag="tag", timestamp_suffix=False, config_file=StringIO(CONFIG))
            # now we try to access the public key content to trigger the exception
            cloud.key_pair.public_key_content
        assert "No public key path provided and no key found in default locations" in caplog.text
        assert "No public key content available for unset key pair." in str(exc_info.value)

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
            ("t.a.g", [rule4]),
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


class TestSnapshotHelpers:
    """
    Tests covering both the _store_snapshot_info and _record_image_deletion methods of BaseCloud.
    """

    @pytest.fixture
    def cloud(self):
        """Fixture to create a CloudSubclass instance for testing."""
        return CloudSubclass(tag="tag", timestamp_suffix=False, config_file=StringIO(CONFIG))

    def test_store_snapshot_info_temporary(self, cloud, caplog):
        """Test storing snapshot info as temporary."""
        snapshot_id = "snap-123"
        snapshot_name = "snapshot-temp"
        keep_snapshot = False

        caplog.set_level(logging.DEBUG)
        image_info = cloud._store_snapshot_info(snapshot_id, snapshot_name, keep_snapshot)

        assert image_info.image_id == snapshot_id
        assert image_info.image_name == snapshot_name
        assert image_info in cloud.created_images
        assert image_info not in cloud.preserved_images
        assert f"Created temporary snapshot {image_info}" in caplog.text

    def test_store_snapshot_info_permanent(self, cloud, caplog):
        """Test storing snapshot info as permanent."""
        snapshot_id = "snap-456"
        snapshot_name = "snapshot-perm"
        keep_snapshot = True

        caplog.set_level(logging.DEBUG)
        image_info = cloud._store_snapshot_info(snapshot_id, snapshot_name, keep_snapshot)

        assert image_info.image_id == snapshot_id
        assert image_info.image_name == snapshot_name
        assert image_info not in cloud.created_images
        assert image_info in cloud.preserved_images
        assert f"Created permanent snapshot {image_info}" in caplog.text

    def test_record_image_deletion_created_image(self, cloud, caplog):
        """Test recording deletion of a created image."""
        snapshot_id = "snap-789"
        snapshot_name = "snapshot-created"
        keep_snapshot = False

        image_info = cloud._store_snapshot_info(snapshot_id, snapshot_name, keep_snapshot)
        caplog.set_level(logging.DEBUG)
        cloud._record_image_deletion(snapshot_id)

        assert image_info not in cloud.created_images
        assert image_info not in cloud.preserved_images
        assert (
            f"Snapshot {image_info} has been deleted. Will no longer need to be cleaned up later."
            in caplog.text
        )

    def test_record_image_deletion_preserved_image(self, cloud, caplog):
        """Test recording deletion of a preserved image."""
        snapshot_id = "snap-101"
        snapshot_name = "snapshot-preserved"
        keep_snapshot = True

        image_info = cloud._store_snapshot_info(snapshot_id, snapshot_name, keep_snapshot)
        caplog.set_level(logging.DEBUG)
        cloud._record_image_deletion(snapshot_id)

        assert image_info not in cloud.created_images
        assert image_info not in cloud.preserved_images
        assert (
            f"Snapshot {image_info} has been deleted. This snapshot was taken with keep=True, "
            "but since it has been manually deleted, it will not be preserved."
        ) in caplog.text

    def test_record_image_deletion_nonexistent_image(self, cloud, caplog):
        """Test recording deletion of a non-existent image."""
        snapshot_id = "snap-999"
        caplog.set_level(logging.DEBUG)
        cloud._record_image_deletion(snapshot_id)
        assert f"Deleted image {snapshot_id}" in caplog.text
