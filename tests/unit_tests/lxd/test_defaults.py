"""Tests related to pycloudlib.lxd.defaults module."""

import hashlib

import pytest

from pycloudlib.lxd.defaults import LXC_PROFILE_VERSION, base_vm_profiles


class TestLXDProfilesWereNotModified:
    """Test covering if profiles were not accidentally changed."""

    # This dict represents a mapping between the profile version and the
    # md5sum associated with it. Whenever we have a new profile release,
    # we must add a new entry to it with the new checksums, not overriding
    # the existing dict we have here. The rationale for that is to avoid
    # us forgetting to bump the profile version when modifying it.
    version_to_md5sum = {
        "v1": {
            "xenial": "350af6388522c8c28d8e00152fac98cc",
            "bionic": "b79ba7ea46882d35e6d10b08c7531f6f",
            "focal": "9ce4202e39d98c1499e3bce3c144e14f",
            "groovy": "05b1582d39237fb2d1b55c8782982bfd",
            "hirsute": "1f3851328bec6253f51b1f1dc9bcbf55",
        },
        "v2": {
            "xenial": "c4f83c97c2f39a39f1e997aa33e4bb66",
            "bionic": "0e35f88aa29c66374fbd9fe3b4a36257",
            "focal": "9ce4202e39d98c1499e3bce3c144e14f",
            "groovy": "05b1582d39237fb2d1b55c8782982bfd",
            "hirsute": "1f3851328bec6253f51b1f1dc9bcbf55",
            "impish": "c2a4e4d6a9c16f73f2f79fe34d3f638f",
        },
        "v3": {
            "xenial": "1f4d35dc74a550eb6458222a531a24c4",
            "bionic": "f0e13a4b8d11bc7b3d82c0f06ef72211",
            "default": "a740b8296455ba0b51ad093c77b0261b",
        },
    }

    @pytest.mark.parametrize("series", base_vm_profiles.keys())
    def test_profiles_md5sum_was_not_changed(self, series):
        """Test if the profiles md5sum still match.

        This test will ensure that the current profile version
        matches the md5sums we have stored for the profiles.
        """
        profiles_md5sum = self.version_to_md5sum[LXC_PROFILE_VERSION]

        current_profile_md5sum = hashlib.md5(
            base_vm_profiles[series].encode("utf-8")
        ).hexdigest()
        if series not in profiles_md5sum:
            pytest.fail(
                "Series {} md5sum not yet present: {}".format(
                    series, current_profile_md5sum
                )
            )
        profile_md5sum = profiles_md5sum[series]

        assert profile_md5sum == current_profile_md5sum
