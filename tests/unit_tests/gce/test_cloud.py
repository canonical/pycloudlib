"""Tests related to pycloudlib.gce.cloud module."""
import mock
import pytest

from pycloudlib.cloud import ImageType
from pycloudlib.gce.cloud import GCE

# mock module path
MPATH = "pycloudlib.gce.cloud."


class FakeGCE(GCE):
    """GCE Class that doesn't load config or make requests during __init__."""

    # pylint: disable=super-init-not-called
    def __init__(self, *_, **__):
        """Fake __init__ that sets mocks for needed variables."""
        self._log = mock.MagicMock()
        self.compute = mock.MagicMock()


# pylint: disable=protected-access,missing-function-docstring
class TestGCE:
    """General GCE testing."""

    @pytest.mark.parametrize(
        [
            "release",
            "arch",
            "api_side_effects",
            "expected_filter_calls",
            "expected_image_list",
        ],
        [
            pytest.param(
                "xenial",
                "arm64",
                Exception(),
                [],
                [],
                id="xenial_no_arm64_support_zero_sdk_list_calls",
            ),
            pytest.param(
                "xenial",
                "x86_64",
                [{"items": [1, 2, 3]}, Exception()],
                [
                    mock.call(
                        project="project-name",
                        filter="name=name-filter",
                        maxResults=500,
                        pageToken="",
                    )
                ],
                [1, 2, 3],
                id="xenial_x86_64_suppport_one_sdk_list_call_empty_pagetoken",
            ),
            pytest.param(
                "kinetic",
                "arm64",
                [
                    {"items": [1, 2, 3], "nextPageToken": "something"},
                    {"items": [4, 5, 6]},
                    Exception(),
                ],
                [
                    mock.call(
                        project="project-name",
                        filter="(name=name-filter) AND (architecture=ARM64)",
                        maxResults=500,
                        pageToken="",
                    ),
                    mock.call(
                        project="project-name",
                        filter="(name=name-filter) AND (architecture=ARM64)",
                        maxResults=500,
                        pageToken="something",
                    ),
                ],
                [1, 2, 3, 4, 5, 6],
                id="non_xenial_arm64_suppport_one_sdk_list_call_per_page",
            ),
        ],
    )
    def test_query_image_list(  # noqa: D102
        self,
        release,
        arch,
        api_side_effects,
        expected_filter_calls,
        expected_image_list,
    ):
        gce = FakeGCE(tag="tag")
        with mock.patch.object(gce, "compute") as m_compute:
            m_execute = mock.MagicMock(
                name="m_execute", side_effect=api_side_effects
            )
            m_executor = mock.MagicMock(name="m_executor")
            m_executor.execute = m_execute
            m_list = mock.MagicMock(name="m_list", return_value=m_executor)
            m_lister = mock.MagicMock(name="m_lister")
            m_lister.list = m_list
            m_images = mock.MagicMock(name="m_images", return_value=m_lister)
            m_compute.images = m_images

            assert expected_image_list == gce._query_image_list(
                release, "project-name", "name-filter", arch
            )
            assert m_list.call_args_list == expected_filter_calls

    @mock.patch(
        MPATH + "GCE._query_image_list",
        return_value=[
            {
                "id": "2",
                "name": "2",
                "creationTimestamp": "2",
            },
            {
                "id": "4",
                "name": "4",
                "creationTimestamp": "4",
            },
            {
                "id": "1",
                "name": "1",
                "creationTimestamp": "1",
            },
            {
                "id": "3",
                "name": "3",
                "creationTimestamp": "3",
            },
        ],
    )
    @mock.patch(MPATH + "GCE._get_name_filter", return_value="name-filter")
    @mock.patch(MPATH + "GCE._get_project", return_value="project-name")
    def test_daily_image_returns_latest_from_query(  # noqa: D102
        self,
        m_get_project,
        m_get_name_filter,
        m_query_image_list,
    ):
        gce = FakeGCE(tag="tag")
        image = gce.daily_image(
            "jammy", arch="x86_64", image_type=ImageType.GENERIC
        )
        assert m_get_project.call_args_list == [
            mock.call(image_type=ImageType.GENERIC)
        ]
        assert m_get_name_filter.call_args_list == [
            mock.call(release="jammy", image_type=ImageType.GENERIC)
        ]
        assert m_query_image_list.call_args_list == [
            mock.call("jammy", "project-name", "name-filter", "x86_64")
        ]
        assert image == "projects/project-name/global/images/4"
