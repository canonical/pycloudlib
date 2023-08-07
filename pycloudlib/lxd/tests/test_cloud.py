"""Tests related to pycloudlib.lxd.cloud module."""
import contextlib
import io
from unittest import mock

import pytest

from pycloudlib.lxd.cloud import LXDContainer

M_PATH = "pycloudlib.lxd.cloud."

CONFIG = """\
[lxd]

"""


@contextlib.contextmanager
def does_not_raise():
    """Provide alternate contextmanager to use where no errors are raised."""
    yield


class TestLaunch:
    """Tests covering pycloudlib.lxd.cloud.launch method."""

    @pytest.mark.parametrize(
        "image_id,expectation",
        (
            ("some-img", does_not_raise()),
            ("", pytest.raises(ValueError)),
            (None, pytest.raises(ValueError)),
        ),
    )
    @mock.patch(M_PATH + "_images.find_release")
    def test_launch_validates_image_id(
        self, m_find_release, image_id, expectation
    ):
        """Validate image_id or raise exceptions before calling init/start."""
        m_find_release.return_value = "bionic"
        cloud = LXDContainer(tag="test", config_file=io.StringIO(CONFIG))
        init_kwargs = {
            "image_id": image_id,
            "instance_type": "inst_type",
            "user_data": "ud",
            "name": "name",
            "ephemeral": True,
            "network": "netname",
            "storage": "storagename",
            "profile_list": ["profile1"],
            "config_dict": {"user.custom": "val"},
            "execute_via_ssh": True,
        }
        inst = mock.MagicMock()
        with expectation:
            with mock.patch.object(cloud, "init") as lxd_init:
                lxd_init.return_value = inst
                inst = cloud.launch(**init_kwargs)
                assert lxd_init.call_args_list == [
                    mock.call(
                        name="name",
                        image_id="some-img",
                        ephemeral=True,
                        network="netname",
                        storage="storagename",
                        inst_type="inst_type",
                        profile_list=["profile1"],
                        user_data="ud",
                        config_dict={"user.custom": "val"},
                        execute_via_ssh=True,
                        username=None,
                    )
                ]
                # pylint: disable=no-member
                assert inst.start.call_args_list == [mock.call(wait=False)]
                # pylint: disable=no-member

        if not image_id:
            assert lxd_init.call_count == 0
            assert inst.start.call_count == 0


class TestProfileCreation:
    """Tests covering pycloudlib.lxd.cloud.create_profile method."""

    @mock.patch("pycloudlib.lxd.cloud.subp")
    def test_create_profile_that_already_exists(self, m_subp):
        """Tests creating a profile that already exists."""
        m_subp.return_value = """
            - name: test_profile
        """
        cloud = LXDContainer(tag="test", config_file=io.StringIO(CONFIG))

        fake_stdout = io.StringIO()
        with contextlib.redirect_stdout(fake_stdout):
            cloud.create_profile(
                profile_name="test_profile", profile_config="profile_config"
            )

        expected_msg = "The profile named test_profile already exists"
        assert expected_msg in fake_stdout.getvalue().strip()
        assert m_subp.call_args_list == [
            mock.call(["lxc", "profile", "list", "--format", "yaml"])
        ]

    @mock.patch("pycloudlib.lxd.cloud.subp")
    def test_create_profile_that_already_exists_with_force(self, m_subp):
        """Tests creating an existing profile with force parameter."""
        m_subp.return_value = """
            - name: test_profile
        """
        cloud = LXDContainer(tag="test", config_file=io.StringIO(CONFIG))
        profile_name = "test_profile"
        profile_config = "profile_config"

        cloud.create_profile(
            profile_name=profile_name,
            profile_config=profile_config,
            force=True,
        )

        assert m_subp.call_args_list == [
            mock.call(["lxc", "profile", "list", "--format", "yaml"]),
            mock.call(["lxc", "profile", "delete", profile_name]),
            mock.call(["lxc", "profile", "create", profile_name]),
            mock.call(
                ["lxc", "profile", "edit", profile_name], data=profile_config
            ),
        ]

    @mock.patch("pycloudlib.lxd.cloud.subp")
    def test_create_profile_that_does_not_exist(self, m_subp):
        """Tests creating a new profile."""
        m_subp.return_value = """
            - name: other_profile
        """
        cloud = LXDContainer(tag="test", config_file=io.StringIO(CONFIG))
        profile_name = "other_profile_v1"
        profile_config = "profile_config"

        cloud.create_profile(
            profile_name=profile_name, profile_config=profile_config
        )

        assert m_subp.call_args_list == [
            mock.call(["lxc", "profile", "list", "--format", "yaml"]),
            mock.call(["lxc", "profile", "create", profile_name]),
            mock.call(
                ["lxc", "profile", "edit", profile_name], data=profile_config
            ),
        ]
