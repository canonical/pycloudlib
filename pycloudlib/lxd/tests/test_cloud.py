"""Tests related to pycloudlib.lxd.cloud module."""
import io
import logging
from unittest import mock

import pytest
import yaml

from pycloudlib.lxd.cloud import LXDContainer, LXDVirtualMachine
from pycloudlib.result import Result

CONFIG = """\
[lxd]

"""


class TestProfileCreation:
    """Tests covering pycloudlib.lxd.cloud.create_profile method."""

    @mock.patch("pycloudlib.lxd.cloud.subp")
    def test_create_profile_that_already_exists(self, m_subp, caplog):
        """Tests creating a profile that already exists."""
        m_subp.return_value = """
            - name: test_profile
        """
        cloud = LXDContainer(tag="test", config_file=io.StringIO(CONFIG))

        expected_msg = "The profile named test_profile already exists"
        with caplog.at_level(logging.DEBUG):
            cloud.create_profile(
                profile_name="test_profile", profile_config="profile_config"
            )
            assert expected_msg in caplog.text
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


SAMPLE_METADATA_CFG = {
    "architecture": "x86_64",
    "properties": {
        "os": "ubuntu",
        "release": "bionic",
    },
    "templates": {
        "/etc/hostname": {
            "when": ["create", "copy"],
            "create_only": False,
            "template": "hostname.tpl",
            "properties": {},
        },
    },
}


class TestSetInstanceMetadataConfig:
    """Test LXD.set_instance_metadata_config."""

    @mock.patch("pycloudlib.lxd.cloud.subp")
    def test_set_instance_metadata_logs_cmd(self, subp, caplog):
        """set_instance_metadata invokes CLI: lxc config metadata edit."""
        cloud = LXDVirtualMachine(tag="test", config_file=io.StringIO(CONFIG))
        with caplog.at_level(logging.DEBUG):
            cloud.set_instance_metadata_config("inst1", SAMPLE_METADATA_CFG)
        cmd = ["lxc", "config", "metadata", "edit", "inst1"]
        assert subp.call_args_list == [
            mock.call(cmd, data=yaml.safe_dump(SAMPLE_METADATA_CFG))
        ]
        assert f"Setting instance metadata: {' '.join(cmd)}\n" in caplog.text


class TestCreateInstanceTemplate:
    """Test LXD.create_instance_template."""

    @pytest.mark.parametrize(
        "profile_list,create_template",
        (
            ("- sometmpl\n", True),
            ("- tmpl1\n", False),
        ),
    )
    @mock.patch("pycloudlib.lxd.cloud.subp")
    def test_create_instance_template_calls_create_template_when_absent(
        self, subp, profile_list, create_template, caplog
    ):
        """Call lxc config create template only when named template absent."""
        subp.side_effect = (
            profile_list,
            "",
            "",
            RuntimeError("Too many subp calls"),
        )
        cloud = LXDVirtualMachine(tag="test", config_file=io.StringIO(CONFIG))
        with caplog.at_level(logging.DEBUG):
            cloud.create_instance_template("inst1", "tmpl1", "tmpl-content")
        create_cmd = ["lxc", "config", "template", "create", "inst1", "tmpl1"]
        edit_cmd = ["lxc", "config", "template", "edit", "inst1", "tmpl1"]
        expected_calls = [
            mock.call(
                [
                    "lxc",
                    "config",
                    "template",
                    "list",
                    "inst1",
                    "--format",
                    "yaml",
                ]
            ),
            mock.call(edit_cmd, data="tmpl-content"),
        ]
        expected_logs = [f"Setting template content for instance: {edit_cmd}"]
        if create_template:
            # Only lxc config template create if it does not exist
            expected_calls.insert(1, mock.call(create_cmd))
            expected_logs.append(
                f"Creating template for instance: {create_cmd}"
            )

        assert subp.call_args_list == expected_calls
        for log in expected_logs:
            assert log in caplog.text


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
