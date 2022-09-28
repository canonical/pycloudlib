"""Tests related to pycloudlib.lxd.cloud module."""
import contextlib
import io
from unittest import mock

import pytest
import yaml

from pycloudlib.lxd.cloud import LXDContainer, LXDVirtualMachine
from pycloudlib.result import Result

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
    @mock.patch("pycloudlib.lxd.cloud._BaseLXD._extract_release_from_image_id")
    def test_launch_validates_image_id(
        self, extract_release, image_id, expectation
    ):
        """Validate image_id or raise exceptions before calling init/start."""
        extract_release.return_value = "bionic"
        cloud = LXDContainer(tag="test", config_file=io.StringIO(CONFIG))
        init_kwargs = {
            "image_id": image_id,
            "instance_type": "inst_type",
            "user_data": "ud",
            "wait": False,
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
                wait_val = init_kwargs.pop("wait")
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
                    )
                ]
                # pylint: disable=no-member
                assert inst.start.call_args_list == [mock.call(wait_val)]
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


@mock.patch("pycloudlib.lxd.cloud.subp")
class Test_LxcImageInfo:  # pylint: disable=W0212
    """Tests LXDVirtualMachine._lxc_image_info."""

    def test_happy_path(self, m_subp):
        """Command succeeds and returns valid YAML."""
        image_id = "my:image_id"
        content = {"my": "data"}
        m_subp.return_value = Result(yaml.dump(content), "", 0)

        ret = LXDVirtualMachine(
            tag="test", config_file=io.StringIO(CONFIG)
        )._lxc_image_info(image_id)

        assert content == ret
        expected_call = mock.call(["lxc", "image", "info", image_id], rcs=())
        assert [expected_call] == m_subp.call_args_list

    def test_command_failure_returns_empty_dict(self, m_subp):
        """Command failure even with valid YAML returns empty dict."""
        content = {"my": "data"}
        m_subp.return_value = Result(yaml.dump(content), "", 1)

        assert {} == LXDVirtualMachine(
            tag="test", config_file=io.StringIO(CONFIG)
        )._lxc_image_info("image_id")

    def test_invalid_yaml_returns_empty_dict(self, m_subp):
        """Invalid YAML even with command success returns empty dict."""
        m_subp.return_value = Result("{:a}", "", 0)

        assert {} == LXDVirtualMachine(
            tag="test", config_file=io.StringIO(CONFIG)
        )._lxc_image_info("image_id")


class TestExtractReleaseFromImageId:
    """Test LXDVirtualMachine _extract_release_from_image_id method.

    This method should only be executed by LXDVirtualMachine instances.
    """

    @pytest.mark.parametrize(
        "expected_release,lxc_image_info",
        [
            # Test the various cases in which we expect to fallthrough
            ("fallthrough", {}),
            ("fallthrough", {"Properties": {}}),
            ("fallthrough", {"Properties": {"os": "ubuntu"}}),
            ("fallthrough", {"Properties": {"os": "Ubuntu"}}),
            ("fallthrough", {"Properties": {"release": "bionic"}}),
            (
                "fallthrough",
                {"Properties": {"os": "notubuntu", "release": "bionic"}},
            ),
            # Test the two spelling of Ubuntu which we accept
            (
                "our_release",
                {"Properties": {"os": "ubuntu", "release": "our_release"}},
            ),
            (
                "our_release",
                {"Properties": {"os": "Ubuntu", "release": "our_release"}},
            ),
        ],
    )
    @mock.patch.object(
        LXDVirtualMachine,
        "_image_info",
        return_value=[{"release": "fallthrough"}],
    )
    def test_correct_paths_taken(
        self, m__image_info, expected_release, lxc_image_info
    ):
        """Test that we fallthrough when the image is missing required info."""
        image_id = mock.sentinel.image_id
        cloud = LXDVirtualMachine(tag="test", config_file=io.StringIO(CONFIG))
        with mock.patch.object(
            cloud, "_lxc_image_info", return_value=lxc_image_info
        ) as m__lxc_image_info:
            # pylint: disable=W0212
            assert expected_release == cloud._extract_release_from_image_id(
                image_id
            )

        assert [mock.call(image_id)] == m__lxc_image_info.call_args_list

        if expected_release == "fallthrough":
            assert [mock.call(image_id)] == m__image_info.call_args_list
