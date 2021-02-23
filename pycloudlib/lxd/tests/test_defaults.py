"""Tests related to pycloudlib.lxd.defaults module."""
import hashlib

from pycloudlib.lxd.defaults import base_vm_profiles, LXC_PROFILE_VERSION


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
        }
    }

    def test_profiles_md5sum_was_not_changed(self):
        """Test if the profiles md5sum still match.

        This test will ensure that the current profile version
        matches the md5sums we have stored for the profiles.
        """
        profiles_md5sum = self.version_to_md5sum[LXC_PROFILE_VERSION]

        for series, current_profile in base_vm_profiles.items():
            current_profile_md5sum = hashlib.md5(
                current_profile.encode('utf-8')
            ).hexdigest()
            profile_md5sum = profiles_md5sum[series]

            print(series)
            print(current_profile_md5sum)
            assert profile_md5sum == current_profile_md5sum
