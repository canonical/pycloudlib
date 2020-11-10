"""Tests related to pycloudlib.lxd.cloud module."""
import contextlib
import io
from unittest import mock
import pytest

from pycloudlib.lxd.cloud import LXD, UnsupportedReleaseException


class TestProfileCreation:
    """Tests covering pycloudlib.lxd.cloud.create_profile method."""

    @mock.patch("pycloudlib.lxd.cloud.subp")
    def test_create_profile_that_already_exists(self, m_subp):
        """Tests creating a profile that already exists."""
        m_subp.return_value = ["test_profile"]
        cloud = LXD(tag="test")

        fake_stdout = io.StringIO()
        with contextlib.redirect_stdout(fake_stdout):
            cloud.create_profile(
                profile_name="test_profile",
                profile_config="profile_config"
            )

        expected_msg = "The profile named test_profile already exists"
        assert expected_msg in fake_stdout.getvalue().strip()
        assert m_subp.call_args_list == [
            mock.call(["lxc", "profile", "list"])
        ]

    @mock.patch("pycloudlib.lxd.cloud.subp")
    def test_create_profile_that_already_exists_with_force(
        self, m_subp
    ):
        """Tests creating an existing profile with force parameter."""
        m_subp.return_value = ["test_profile"]
        cloud = LXD(tag="test")
        profile_name = "test_profile"
        profile_config = "profile_config"

        cloud.create_profile(
            profile_name=profile_name,
            profile_config=profile_config,
            force=True
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
        cloud = LXD(tag="test")
        profile_name = "test_profile"
        profile_config = "profile_config"

        cloud.create_profile(
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


class TestExtractReleaseFromImageId:
    """Test pycloudlib.lxd.cloud._extract_release_from_image_id method."""

    @pytest.mark.parametrize(
        "image_id, expected_release",
        (
            ("images:ubuntu/16.04/cloud", "xenial"),
            ("ubuntu-daily:bionic", "bionic"),
            ("ubuntu:focal", "focal"),
        ),
    )
    def test_extract_release_from_non_hashed_image_id(
        self, image_id, expected_release
    ):  # pylint: disable=W0212
        """Tests extracting release from non hashed image id."""
        cloud = LXD(tag="test")
        assert expected_release == cloud._extract_release_from_image_id(
            image_id)

    @mock.patch.object(LXD, "_image_info")
    def test_extract_release_from_hashed_image_id(
        self, m_image_info
    ):  # pylint: disable=W0212
        """Tests extracting release from a non hashed image id."""
        cloud = LXD(tag="test")

        m_image_info.return_value = [
            {
                "release": "focal"
            }
        ]

        expected_release = "focal"
        image_id = "ubuntu:ef539de92ef7b12cc1967bc0dbbe0ad8a231e9295aeab1b953"
        assert expected_release == cloud._extract_release_from_image_id(
            image_id)

        assert m_image_info.call_args_list == [
            mock.call(image_id, False)
        ]


class TestSearchForImage:
    """Tests covering pycloudlib.lxd.cloud._search_for_image method."""

    def test_trusty_image_not_supported_when_launching_vms(
        self
    ):  # pylint: disable=W0212
        """Tests searching for trusty image for launching LXD vms."""
        cloud = LXD(tag="test")

        with pytest.raises(UnsupportedReleaseException) as excinfo:
            cloud._search_for_image(
                remote="remote",
                daily=False,
                release="trusty",
                is_vm=True
            )

        assert "Release trusty is not supported for LXD vms" == str(
            excinfo.value)
