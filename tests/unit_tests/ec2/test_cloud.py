"""Tests related to pycloudlib.gce.cloud module."""

import mock
import pytest

from pycloudlib.cloud import ImageType
from pycloudlib.ec2.cloud import EC2

# mock module path
MPATH = "pycloudlib.ec2.cloud."


class FakeEC2(EC2):
    """EC2 Class that doesn't load config or make requests during __init__."""

    # pylint: disable=super-init-not-called
    def __init__(self, *_, **__):
        """Fake __init__ that sets mocks for needed variables."""


# pylint: disable=protected-access,missing-function-docstring
class TestEC2:
    """General EC2 testing."""

    @pytest.mark.parametrize(
        ["release", "image_type", "daily", "expected_name_filter"],
        [
            # Test GENERIC with LTS release and daily = True
            pytest.param(
                "focal",
                ImageType.GENERIC,
                True,
                "ubuntu/images-testing/hvm-ssd/ubuntu-focal-daily-*-server-*",
                id="generic-lts-daily",
            ),
            # Test GENERIC with LTS release and daily = False
            pytest.param(
                "noble",
                ImageType.GENERIC,
                False,
                "ubuntu/images/hvm-ssd-gp3/ubuntu-noble-*-server-*",
                id="generic-lts-non-daily",
            ),
            # Test MINIMAL with LTS release and daily = True
            pytest.param(
                "jammy",
                ImageType.MINIMAL,
                True,
                "ubuntu-minimal/images-testing/hvm-ssd/ubuntu-jammy-daily-*-minimal-*",
                id="minimal-lts-daily",
            ),
            # Test MINIMAL with LTS release and daily = False
            pytest.param(
                "noble",
                ImageType.MINIMAL,
                False,
                "ubuntu-minimal/images/hvm-ssd-gp3/ubuntu-noble-*-minimal-*",
                id="minimal-lts-non-daily",
            ),
            # Test PRO with LTS release
            pytest.param(
                "jammy",
                ImageType.PRO,
                False,
                "ubuntu-pro-server/images/hvm-ssd/ubuntu-jammy-22.04-*",
                id="pro-lts",
            ),
            # Test PRO_FIPS with LTS release
            pytest.param(
                "noble",
                ImageType.PRO_FIPS,
                False,
                "ubuntu-pro-fips*/images/hvm-ssd-gp3/ubuntu-noble-24.04-*",
                id="pro-fips-lts",
            ),
            # Test GENERIC with non-LTS release and daily = False
            pytest.param(
                "oracular",
                ImageType.GENERIC,
                False,
                "ubuntu/images/hvm-ssd-gp3/ubuntu-oracular-*-server-*",
                id="generic-non-lts-non-daily",
            ),
            # Test MINIMAL with non-LTS release and daily = False
            pytest.param(
                "oracular",
                ImageType.MINIMAL,
                False,
                "ubuntu-minimal/images/hvm-ssd-gp3/ubuntu-oracular-*-minimal-*",
                id="minimal-non-lts-non-daily",
            ),
            # Test GENERIC with non-LTS release and daily = True
            pytest.param(
                "oracular",
                ImageType.GENERIC,
                True,
                "ubuntu/images-testing/hvm-ssd-gp3/ubuntu-oracular-daily-*-server-*",
                id="generic-non-lts-daily",
            ),
            # Test MINIMAL with non-LTS release and daily = True
            pytest.param(
                "oracular",
                ImageType.MINIMAL,
                True,
                "ubuntu-minimal/images-testing/hvm-ssd-gp3/ubuntu-oracular-daily-*-minimal-*",
                id="minimal-non-lts-daily",
            ),
        ],
    )
    def test_get_name_for_image_type(
        self,
        release: str,
        image_type: ImageType,
        daily: str,
        expected_name_filter: str,
    ):
        """
        Test the _get_name_for_image_type() method against various
        combinations of release, image_type, and daily
        """
        ec2 = FakeEC2()
        result = ec2._get_name_for_image_type(
            release=release, image_type=image_type, daily=daily
        )
        assert result == expected_name_filter

    def test_get_name_for_image_type_invalid_image_type(self):
        """
        Test the _get_name_for_image_type() method with an invalid ImageType
        """
        ec2 = FakeEC2()
        with pytest.raises(ValueError) as exc_info:
            ec2._get_name_for_image_type(
                release="focal", image_type=None, daily=True
            )
        assert "Invalid image_type" in str(exc_info.value)

    def test_get_owner_for_all_image_types(self):
        """
        Test the _get_project() method against all possible ImageType enum values
        """
        expected_project_per_image_type = {
            ImageType.GENERIC: "099720109477",
            ImageType.MINIMAL: "099720109477",
            ImageType.PRO: "099720109477",
            ImageType.PRO_FIPS: "aws-marketplace",
        }

        ec2 = FakeEC2()

        # for each value of ImageType, check if it is in the expected_project_per_image_type dict
        # if not, then the test will fail because a new ImageType was added
        for image_type in ImageType:
            assert image_type in expected_project_per_image_type
            assert (
                ec2._get_owner(image_type)
                == expected_project_per_image_type[image_type]
            )
