"""GCE integration tests testing image related functionality."""

import logging

import pytest

from pycloudlib.cloud import ImageType
from pycloudlib.errors import ImageNotFoundError
from pycloudlib.gce.cloud import GCE

logger = logging.getLogger(__name__)


@pytest.fixture
def gce_cloud():
    """
    Fixture to create a GCE instance for testing.

    Yields:
        GCE: An instance of the GCE cloud class.
    """
    with GCE(tag="integration-test-images") as gce:
        yield gce

@pytest.mark.parametrize(
    "release, unavailable_image_types",
    (
        pytest.param(
            "focal",
            [ImageType.PRO_FIPS_UPDATES],
            id="focal",
        ),
        pytest.param(
            "jammy",
            [ImageType.PRO_FIPS],
            id="jammy",
        ),
    ),
)
def test_finding_all_image_types_focal(
    gce_cloud: GCE,
    release: str,
    unavailable_image_types: list[ImageType],
):
    """
    Tests that all image types are available for the focal suite and that they are all unique.

    Test assertions:
    - Certain image types are unavailable for the given release (exception is raised if not).
    - No daily images returned per image type are the same (same image ID).
    """
    images: dict[ImageType, str] = {}
    # iterate through all ImageType enum values
    for image_type in ImageType:
        if image_type in unavailable_image_types:
            with pytest.raises(ImageNotFoundError) as exc_info:
                gce_cloud.daily_image(release=release, image_type=image_type)
            logger.info(
                "Confirmed that %s image for %s is unavailable.",
                image_type,
                release,
            )
        else:
            images[image_type] = gce_cloud.daily_image(release=release, image_type=image_type)
            logger.info(
                "Found %s image for %s: %s",
                image_type,
                release,
                images[image_type],
            )

    # make sure that none of the images are the same
    assert len(set(images.values())) == len(images), f"Not all images are unique: {images}"
