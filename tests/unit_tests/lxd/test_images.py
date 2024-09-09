"""Tests related to lxd._images."""

import json
from unittest import mock

import pytest

from pycloudlib.cloud import ImageType
from pycloudlib.lxd import _images

M_PATH = "pycloudlib.lxd._images."


@mock.patch(M_PATH + "subp")
class TestImages:  # pylint: disable=W0212
    """Test class for _images."""

    @pytest.mark.parametrize(
        "images",
        (
            [],
            [{"properties": {"serial": "s0"}}],
            [
                {"properties": {"serial": "s0"}},
                {"properties": {"serial": "s1"}},
            ],
        ),
    )
    @mock.patch(M_PATH + "_find_images")
    def test_find_image_serial(self, m_find_images, m_subp, images):
        """Test find_image_serial method."""
        image_id = "my:image_id"
        mock.Mock()
        if not images:
            expected_result = None
        else:
            expected_result = "s0"

        m_find_images.return_value = images
        assert expected_result == _images.find_image_serial(image_id)

        assert [
            mock.call("my", (("fingerprint", "image_id"),))
        ] == m_find_images.call_args_list
        assert [] == m_subp.call_args_list

    @pytest.mark.parametrize(
        ["filters", "expected_call"],
        (
            (
                None,
                mock.call(
                    [
                        "lxc",
                        "image",
                        "list",
                        "remote:",
                        "--format=json",
                    ]
                ),
            ),
            (
                (("filter_0", "value_0"), ("f1", "v1")),
                mock.call(
                    [
                        "lxc",
                        "image",
                        "list",
                        "remote:",
                        "--format=json",
                        "filter_0=value_0",
                        "f1=v1",
                    ]
                ),
            ),
        ),
    )
    def test_find_images(self, m_subp, filters, expected_call):
        """Test find_images method."""
        content = ["image_0", "image_1"]
        m_subp.return_value = json.dumps(content)
        remote = "remote"
        assert content == _images._find_images(remote, filters)
        assert [expected_call] == m_subp.call_args_list

    @pytest.mark.parametrize(
        ["remote_in", "remote_out"],
        (
            (None, "ubuntu-daily:"),
            ("remote", "remote:"),
            ("remote:", "remote:"),
            ("remote:fingerprint", "remote:fingerprint"),
        ),
    )
    def test_normalize_remote(self, m_subp, remote_in, remote_out):
        """Test _normalize_remote method."""
        assert remote_out == _images._normalize_remote(remote_in)
        assert [] == m_subp.call_args_list

    @pytest.mark.parametrize(
        ["images", "output"],
        (
            ([{"properties": {"os": "ubuntu", "release": "lunar"}}], "lunar"),
            ([{"properties": {"os": "Ubuntu", "release": "lunar"}}], "lunar"),
            ([], None),
            ([{"x": {"os": "ubuntu", "release": "lunar"}}], None),
            ([{"properties": {"x": "ubuntu", "release": "lunar"}}], None),
            ([{"properties": {"os": "ubuntu", "x": "lunar"}}], None),
        ),
    )
    @mock.patch(M_PATH + "_find_images")
    def test_find_release(self, m_find_images, m_subp, images, output):
        """Test find_release method."""
        m_find_images.return_value = images
        assert output == _images.find_release("remote:image_id")
        assert [] == m_subp.call_args_list

    @pytest.mark.parametrize(
        [
            "images",
            "n_find_images_calls",
            "is_container",
            "daily",
            "is_minimal",
            "expected_label",
            "expected_output",
        ],
        (
            (
                [{"fingerprint": "asdf", "type": "container"}],
                1,
                True,
                True,
                False,
                "daily",
                "ubuntu-daily:asdf",
            ),
            (
                [{"fingerprint": "asdf", "type": "squashfs"}],
                2,
                True,
                True,
                False,
                "daily",
                "ubuntu-daily:asdf",
            ),
            (
                [{"fingerprint": "asdf", "type": "unknown"}],
                2,
                True,
                True,
                False,
                "daily",
                None,
            ),
            (
                [{"fingerprint": "asdf", "type": "virtual-machine"}],
                1,
                False,
                True,
                False,
                "daily",
                "ubuntu-daily:asdf",
            ),
            (
                [{"fingerprint": "asdf", "type": "disk-kvm.img"}],
                2,
                False,
                True,
                False,
                "daily",
                "ubuntu-daily:asdf",
            ),
            (
                [{"fingerprint": "asdf", "type": "disk1.img"}],
                3,
                False,
                True,
                False,
                "daily",
                "ubuntu-daily:asdf",
            ),
            (
                [{"fingerprint": "asdf", "type": "uefi1.img"}],
                4,
                False,
                True,
                False,
                "daily",
                "ubuntu-daily:asdf",
            ),
            (
                [{"fingerprint": "asdf", "type": "uefi1.img"}],
                4,
                False,
                False,
                False,
                "release",
                "ubuntu:asdf",
            ),
            (
                [{"fingerprint": "asdf", "type": "uefi1.img"}],
                4,
                False,
                True,
                True,
                "minimal daily",
                "ubuntu-minimal-daily:asdf",
            ),
            (
                [{"fingerprint": "asdf", "type": "uefi1.img"}],
                4,
                False,
                False,
                True,
                "minimal release",
                "ubuntu-minimal:asdf",
            ),
            (
                [{"fingerprint": "asdf", "type": "unknown"}],
                4,
                False,
                True,
                False,
                "daily",
                None,
            ),
        ),
    )
    @mock.patch(M_PATH + "_find_images")
    def test_find_last_fingerprint(
        self,
        m_find_images,
        m_subp,
        images,
        n_find_images_calls,
        daily,
        is_container,
        is_minimal,
        expected_label,
        expected_output,
    ):
        """Test find_last_fingerprint method."""

        def find_images(remote, filters=None):
            # pylint: disable=unused-argument
            filters_map = dict(filters)
            return list(
                filter(lambda img: img["type"] == filters_map["type"], images)
            )

        m_find_images.side_effect = find_images

        release = "bionic"
        arch = "amd64"
        if is_minimal:
            find_fingerprint_kwargs = {"image_type": ImageType.MINIMAL}
            expected_remote = (
                "ubuntu-minimal-daily:" if daily else "ubuntu-minimal:"
            )
        else:
            find_fingerprint_kwargs = {}
            expected_remote = "ubuntu-daily:" if daily else "ubuntu:"

        expected_find_images_calls = [
            mock.call(
                expected_remote,
                (
                    ("architecture", arch),
                    ("release", release),
                    ("label", expected_label),
                    (
                        "type",
                        "container" if is_container else "virtual-machine",
                    ),
                ),
            )
        ]
        if is_container:
            if n_find_images_calls >= 2:
                expected_find_images_calls.append(
                    mock.call(
                        expected_remote,
                        (
                            ("architecture", arch),
                            ("release", release),
                            ("label", expected_label),
                            ("type", "squashfs"),
                        ),
                    )
                )
        else:
            if n_find_images_calls >= 2:
                expected_find_images_calls.append(
                    mock.call(
                        expected_remote,
                        (
                            ("architecture", arch),
                            ("release", release),
                            ("label", expected_label),
                            ("type", "disk-kvm.img"),
                        ),
                    )
                )
            if n_find_images_calls >= 3:
                expected_find_images_calls.append(
                    mock.call(
                        expected_remote,
                        (
                            ("architecture", arch),
                            ("release", release),
                            ("label", expected_label),
                            ("type", "disk1.img"),
                        ),
                    )
                )
            if n_find_images_calls >= 4:
                expected_find_images_calls.append(
                    mock.call(
                        expected_remote,
                        (
                            ("architecture", arch),
                            ("release", release),
                            ("label", expected_label),
                            ("type", "uefi1.img"),
                        ),
                    )
                )

        assert expected_output == _images.find_last_fingerprint(
            daily, release, is_container, arch, **find_fingerprint_kwargs
        )
        assert expected_find_images_calls == m_find_images.call_args_list
        assert [] == m_subp.call_args_list
