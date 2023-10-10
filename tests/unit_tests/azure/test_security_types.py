"""Tests related to pycloudlib.azure.security_types module."""
from copy import deepcopy

import pytest

from pycloudlib.azure.security_types import (
    AzureCVMOSDiskEncryption as DiskEncryption,
)
from pycloudlib.azure.security_types import (
    AzureSecurityType,
    configure_security_types_vm_params,
)


class TestSecurityType:
    """Tests covering Azure Security Types."""

    @pytest.mark.parametrize(
        "vm_params", ({}, {"key1": "val1", "key2": "val2"})
    )
    def test_trusted_launch_security_type(self, vm_params):
        """Test Standard type does not change vm_params."""
        orig_vm_params = deepcopy(vm_params)
        configure_security_types_vm_params(
            AzureSecurityType.STANDARD, vm_params
        )
        assert vm_params == orig_vm_params

    @pytest.mark.parametrize(
        "vm_params",
        (
            {},
            {
                "security_profile": {
                    "security_type": "Dummy",
                    "random_key": "random_value",
                }
            },
        ),
    )
    def test_trusted_security_type(self, vm_params):
        """Test trusted launch type changes vm_params."""
        orig_vm_params = deepcopy(vm_params)
        configure_security_types_vm_params(
            AzureSecurityType.TRUSTED_LAUNCH, vm_params
        )
        assert (
            vm_params["security_profile"]["security_type"]
            == AzureSecurityType.TRUSTED_LAUNCH.value
        )
        assert vm_params.get("security_profile", {}).get(
            "random_key", {}
        ) == orig_vm_params.get("security_profile", {}).get("random_key", {})

    @pytest.mark.parametrize(
        "vm_params,sec_type_params,disk_enc",
        (
            (
                {},
                {},
                DiskEncryption.DISK_WITH_VM_GUEST_STATE,
            ),
            (
                {},
                {"os_disk_encryption": DiskEncryption.VM_GUEST_STATE_ONLY},
                DiskEncryption.VM_GUEST_STATE_ONLY,
            ),
            (
                {"security_profile": {"security_type": "Dummy"}},
                {},
                DiskEncryption.DISK_WITH_VM_GUEST_STATE,
            ),
            (
                {
                    "security_profile": {"security_type": "Dummy"},
                    "random_key": "random_value",
                },
                {"os_disk_encryption": DiskEncryption.VM_GUEST_STATE_ONLY},
                DiskEncryption.VM_GUEST_STATE_ONLY,
            ),
        ),
    )
    def test_confidential_vm_security_type(
        self, vm_params, sec_type_params, disk_enc
    ):
        """Test confidential_vm type changes vm_params."""
        orig_vm_params = deepcopy(vm_params)
        configure_security_types_vm_params(
            AzureSecurityType.CONFIDENTIAL_VM,
            vm_params,
            sec_type_params.get("os_disk_encryption", None),
        )
        assert (
            vm_params["security_profile"]["security_type"]
            == AzureSecurityType.CONFIDENTIAL_VM.value
        )
        assert vm_params.get("random_key", {}) == orig_vm_params.get(
            "random_key", {}
        )
        assert (
            vm_params["storage_profile"]["os_disk"]["managed_disk"][
                "security_profile"
            ]["security_encryption_type"]
            == disk_enc.value
        )
