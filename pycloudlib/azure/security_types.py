"""Azure Security Types Classes."""

from enum import Enum
from typing import Any, Dict, Optional

from pycloudlib import util


class AzureSecurityType(Enum):
    """Represents Azure security types."""

    STANDARD = "Standard"
    TRUSTED_LAUNCH = "TrustedLaunch"
    CONFIDENTIAL_VM = "ConfidentialVM"


class AzureCVMOSDiskEncryption(Enum):
    """Represents Azure OS disk encryption types."""

    VM_GUEST_STATE_ONLY = "VMGuestStateOnly"
    DISK_WITH_VM_GUEST_STATE = "DiskWithVMGuestState"


def configure_security_types_vm_params(
    security_type: AzureSecurityType,
    vm_params: Dict[str, Any],
    os_disk_enc: Optional[AzureCVMOSDiskEncryption] = None,
):
    """Configure vm params depending on the security_type provided.

    Args:
        security_type: AzureSecurityType, the Azure security type
        vm_params: dict, The parameters passed to Azure for the vm
        os_disk_encryption: AzureCVMOSDiskEncryption, the os disk
                            encryption used for the vm
    """
    if security_type == AzureSecurityType.STANDARD:
        return
    if security_type == AzureSecurityType.TRUSTED_LAUNCH:
        param_update = {
            "security_profile": {
                "security_type": "TrustedLaunch",
                "uefi_settings": {
                    "secure_boot_enabled": True,
                    "v_tpm_enabled": True,
                },
            }
        }
    elif security_type == AzureSecurityType.CONFIDENTIAL_VM:
        if not os_disk_enc:
            os_disk_enc = AzureCVMOSDiskEncryption.DISK_WITH_VM_GUEST_STATE
        param_update = {
            "security_profile": {
                "security_type": "ConfidentialVM",
                "uefi_settings": {
                    "secure_boot_enabled": True,
                    "v_tpm_enabled": True,
                },
            },
            "storage_profile": {
                "os_disk": {
                    "create_option": "FromImage",
                    "delete_option": "Delete",
                    "managed_disk": {
                        "security_profile": {
                            "security_encryption_type": os_disk_enc.value,
                        },
                    },
                }
            },
        }
    util.update_nested(vm_params, param_update)
