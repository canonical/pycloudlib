"""Tests related to pycloudlib.lxd.cloud module."""
import contextlib
import io
from unittest import mock

from pycloudlib.lxd.cloud import LXD


class TestProfileCreation:
    """Tests covering pycloudlib.lxd.cloud.create_profile method."""

    @mock.patch("pycloudlib.lxd.cloud.subp")
    def test_create_profile_that_already_exists(self, m_subp):
        """Tests creating a profile that already exists."""
        m_subp.return_value = ["test_profile"]
        instance = LXD(tag="test")

        fake_stdout = io.StringIO()
        with contextlib.redirect_stdout(fake_stdout):
            instance.create_profile(
                profile_name="test_profile",
                profile_config="profile_config"
            )

        expected_msg = "The profile named test_profile already exist"
        assert expected_msg in fake_stdout.getvalue().strip()
        assert m_subp.call_args_list == [
            mock.call(["lxc", "profile", "list"])
        ]

    @mock.patch("pycloudlib.lxd.cloud.subp")
    def test_create_profile_that_already_exists_with_force_creation(
        self, m_subp
    ):
        """Tests creating an existing profile with force_creation parameter."""
        m_subp.return_value = ["test_profile"]
        instance = LXD(tag="test")
        profile_name = "test_profile"
        profile_config = "profile_config"

        instance.create_profile(
            profile_name=profile_name,
            profile_config=profile_config,
            force_creation=True
        )

        assert m_subp.call_args_list == [
            mock.call(["lxc", "profile", "list"]),
            mock.call(["lxc", "profile", "delete", profile_name]),
            mock.call(["lxc", "profile", "create", profile_name]),
            mock.call(
                ["lxc", "profile", "edit", profile_name],
                data=profile_config
            )
        ]

    @mock.patch("pycloudlib.lxd.cloud.subp")
    def test_create_profile_that_does_not_exist(
        self, m_subp
    ):
        """Tests creating a new profile."""
        m_subp.return_value = ["other_profile"]
        instance = LXD(tag="test")
        profile_name = "test_profile"
        profile_config = "profile_config"

        instance.create_profile(
            profile_name=profile_name,
            profile_config=profile_config
        )

        assert m_subp.call_args_list == [
            mock.call(["lxc", "profile", "list"]),
            mock.call(["lxc", "profile", "create", profile_name]),
            mock.call(
                ["lxc", "profile", "edit", profile_name],
                data=profile_config
            )
        ]
