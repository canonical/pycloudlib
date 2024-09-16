"""Tests related to pycloudlib.gce.cloud module."""

import mock
import pytest

from pycloudlib.cloud import ImageType
from pycloudlib.gce.cloud import GCE
from pycloudlib.result import Result

from google.cloud import compute_v1
from google.cloud.compute_v1.services.images.pagers import ListPager

# mock module path
MPATH = "pycloudlib.gce.cloud."


class FakeGCECredentials:
    """Fake GCE Service credentials object."""

    def __init__(self, service_account_email: str = None):
        self.service_account_email = service_account_email


@pytest.fixture()
def common_mocks(tmpdir):
    """Mock all known side-effects of GCE.__init__"""
    cfg_file = tmpdir.join("pyproject.toml")
    cfg_file.write("[gce]\n")
    with mock.patch(
        MPATH + "subp", return_value=Result("my-project", "", 0)
    ), mock.patch(
        MPATH + "compute_v1.ImagesClient",
        return_value="fake_images_client",
    ), mock.patch(
        MPATH + "get_credentials",
        return_value=FakeGCECredentials("service-acct@mail.com"),
    ), mock.patch.dict("os.environ", values={}):
        yield


@pytest.fixture()
def gce(request, common_mocks, tmpdir):
    """Mock subp calls to avoid __init__ side-effect w/ gcloud call"""
    toml_cfg = request.param.pop("toml", "[gce]\n")
    cfg_file = tmpdir.join("pyproject.toml")
    cfg_file.write(toml_cfg)
    kwargs = {
        "tag": "pycl-tag",
        "config_file": cfg_file.strpath,
    }
    kwargs.update(request.param.pop("kwargs", {}))
    yield GCE(**kwargs)


# pylint: disable=protected-access,missing-function-docstring
class TestGCE:
    """General GCE testing."""

    @pytest.mark.parametrize(
        "toml_content,expected",
        (
            (
                "[gce]\nservice_account_email = 'toml@mail.com'\n",
                "toml@mail.com",
            ),
            ("[gce]\n", "service-acct@mail.com"),
        ),
    )
    def test_init_config_parsing_service_account_email(
        self, toml_content, expected, common_mocks, tmpdir
    ):
        """
        service_account_email comes from pycloudlib.toml fallback config_file.
        """
        cfg_file = tmpdir.join("pyproject.toml")
        cfg_file.write(toml_content)
        gce = GCE(tag="pycl-tag", config_file=cfg_file.strpath)
        assert expected == gce.service_account_email

    @pytest.mark.parametrize(
        "environ,cred_path,project",
        [
            ({}, "", "my-project"),
            (
                {"GOOGLE_APPLICATION_CREDENTIALS": "other-file"},
                "other-file",
                "my-project",
            ),
            ({"GOOGLE_CLOUD_PROJECT": "env-project"}, "", "env-project"),
        ],
    )
    def test_init_config_parsing_from_environment(
        self, environ, cred_path, project, common_mocks, tmpdir
    ):
        with mock.patch.dict("os.environ", values=environ):
            gce = GCE(
                tag="pycl-tag",
                config_file=tmpdir.join("pyproject.toml").strpath,
            )
        assert cred_path == gce.credentials_path
        assert project == gce.project

    @pytest.mark.parametrize("gce", [{}], indirect=True)
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
                [Exception()],
                [],
                [],
                id="xenial_no_arm64_support_zero_sdk_list_calls",
            ),
            pytest.param(
                "xenial",
                "x86_64",
                [
                    ListPager(
                        method=mock.MagicMock(),
                        request=compute_v1.ListImagesRequest(
                            project="project-name",
                            filter="name=name-filter",
                            max_results=500,
                            page_token="",
                        ),
                        response=compute_v1.ImageList(
                            items=[
                                compute_v1.Image(name="image1"),
                                compute_v1.Image(name="image2"),
                                compute_v1.Image(name="image3"),
                            ]
                        ),
                    ),
                    Exception(),
                ],
                [
                    mock.call(
                        compute_v1.ListImagesRequest(
                            project="project-name",
                            filter="name=name-filter",
                            max_results=500,
                            page_token="",
                        )
                    )
                ],
                [
                    compute_v1.Image(name="image1"),
                    compute_v1.Image(name="image2"),
                    compute_v1.Image(name="image3"),
                ],
                id="xenial_x86_64_suppport_one_sdk_list_call_empty_pagetoken",
            ),
            pytest.param(
                "kinetic",
                "arm64",
                [
                    ListPager(
                        method=mock.MagicMock(),
                        request=compute_v1.ListImagesRequest(
                            project="project-name",
                            filter="(name=name-filter) AND (architecture=ARM64)",
                            max_results=500,
                            page_token="",
                        ),
                        response=compute_v1.ImageList(
                            items=[
                                compute_v1.Image(name="image1"),
                                compute_v1.Image(name="image2"),
                                compute_v1.Image(name="image3"),
                            ],
                            next_page_token="something",
                        ),
                    ),
                    ListPager(
                        method=mock.MagicMock(),
                        request=compute_v1.ListImagesRequest(
                            project="project-name",
                            filter="(name=name-filter) AND (architecture=ARM64)",
                            max_results=500,
                            page_token="something",
                        ),
                        response=compute_v1.ImageList(
                            items=[
                                compute_v1.Image(name="image4"),
                                compute_v1.Image(name="image5"),
                                compute_v1.Image(name="image6"),
                            ]
                        ),
                    ),
                    Exception(),
                ],
                [
                    mock.call(
                        compute_v1.ListImagesRequest(
                            project="project-name",
                            filter="(name=name-filter) AND (architecture=ARM64)",
                            max_results=500,
                            page_token="",
                        )
                    ),
                    mock.call(
                        compute_v1.ListImagesRequest(
                            project="project-name",
                            filter="(name=name-filter) AND (architecture=ARM64)",
                            max_results=500,
                            page_token="something",
                        )
                    ),
                ],
                [
                    compute_v1.Image(name="image1"),
                    compute_v1.Image(name="image2"),
                    compute_v1.Image(name="image3"),
                    compute_v1.Image(name="image4"),
                    compute_v1.Image(name="image5"),
                    compute_v1.Image(name="image6"),
                ],
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
        gce,
    ):
        with mock.patch.object(gce, "_images_client") as m_images:
            m_images.list.side_effect = api_side_effects

            qil = gce._query_image_list(
                release, "project-name", "name-filter", arch
            )
            assert expected_image_list == qil
            assert m_images.list.call_args_list == expected_filter_calls

    @pytest.mark.parametrize("gce", [{}], indirect=True)
    @mock.patch(
        MPATH + "GCE._query_image_list",
        return_value=ListPager(
            method=mock.MagicMock(),
            request=compute_v1.ListImagesRequest(
                project="project-name",
                filter="name=name-filter",
                max_results=500,
                page_token="",
            ),
            response=compute_v1.ImageList(
                items=[
                    compute_v1.Image(id="2", name="2", creation_timestamp="2"),
                    compute_v1.Image(id="4", name="4", creation_timestamp="4"),
                    compute_v1.Image(id="1", name="1", creation_timestamp="1"),
                    compute_v1.Image(id="3", name="3", creation_timestamp="3"),
                ]
            ),
        ),
    )
    @mock.patch(MPATH + "GCE._get_name_filter", return_value="name-filter")
    @mock.patch(MPATH + "GCE._get_project", return_value="project-name")
    def test_daily_image_returns_latest_from_query(  # noqa: D102
        self,
        m_get_project,
        m_get_name_filter,
        m_query_image_list,
        gce,
    ):
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

    @pytest.mark.parametrize("gce", [{}], indirect=True)
    @pytest.mark.parametrize(
        ["release", "image_type", "expected_name_filter"],
        [
            pytest.param(
                "jammy",
                ImageType.GENERIC,
                "daily-ubuntu-2204-jammy-*",
            ),
            pytest.param(
                "noble",
                ImageType.MINIMAL,
                "daily-ubuntu-minimal-2404-noble-*",
            ),
            pytest.param(
                "focal",
                ImageType.PRO,
                "ubuntu-pro-2004-focal-*",
            ),
            pytest.param(
                "focal",
                ImageType.PRO_FIPS,
                "ubuntu-pro-fips-2004-focal-*",
            ),
        ],
    )
    def test_get_name_filter(
        self, release, image_type, expected_name_filter, gce
    ):
        assert (
            gce._get_name_filter(release, image_type) == expected_name_filter
        )
