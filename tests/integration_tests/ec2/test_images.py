"""EC2 integration tests testing image related functionality."""

import logging

import pytest

from pycloudlib.cloud import ImageType
from pycloudlib.ec2.cloud import EC2

logger = logging.getLogger(__name__)


@pytest.fixture
def ec2_cloud():
    """
    Fixture to create an EC2 instance for testing.

    Yields:
        EC2: An instance of the EC2 cloud class.
    """
    with EC2(tag="integration-test-images") as ec2:
        yield ec2


def test_finding_all_image_types_focal(ec2_cloud: EC2):
    """
    Tests that all image types are available for the focal suite and that they are all unique.

    As per issue #481, focal has both `fips` and `fips-updates` image types and previous to
    introducing the `PRO_FIPS_UPDATES` image type, the `PRO_FIPS` image type could return a
    `PRO_FIPS_UPDATES` image if it was newer. This test asserts that PR #483 prevents this from
    happening.

    Test assertions:
    - All image types are available for the focal suite (exception is raised if not).
    - No daily images returned per image type are the same (same image ID).
    """
    suite = "focal"
    images: dict[ImageType, str] = {}
    # iterate through all ImageType enum values
    for image_type in ImageType:
        images[image_type] = ec2_cloud.daily_image(release=suite, image_type=image_type)
        logger.info(
            "Found %s image for %s: %s",
            image_type,
            suite,
            images[image_type],
        )

    # make sure that none of the images are the same
    assert len(set(images.values())) == len(images), f"Not all images are unique: {images}"
