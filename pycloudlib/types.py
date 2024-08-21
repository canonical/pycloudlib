"""Contains all helper classes and enums used in the library to aid in standardization."""

import dataclasses
import enum


@enum.unique
class ImageType(enum.Enum):
    """Allowed image types when launching cloud images."""

    GENERIC = "generic"
    MINIMAL = "minimal"
    PRO = "Pro"
    PRO_FIPS = "Pro FIPS"


@dataclasses.dataclass
class ImageInfo:
    """Dataclass that represents an image on any given cloud."""

    image_id: str
    image_name: str

    def __str__(self):
        """Return a human readable string representation of the image."""
        return f"{self.image_name} [id: {self.image_id}]"

    def __repr__(self):
        """Return a string representation of the image."""
        return f"ImageInfo(id={self.image_id}, name={self.image_name})"

    def __eq__(self, other):
        """
        Check if two ImageInfo objects represent the same image.

        Only the id is used for comparison since this should be the unique identifier for an image.
        """
        if not isinstance(other, ImageInfo):
            return False
        return self.image_id == other.image_id

    def __dict__(self):
        """Return a dictionary representation of the image."""
        return {"image_id": self.image_id, "image_name": self.image_name}
