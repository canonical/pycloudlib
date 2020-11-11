"""Tests related to pycloudlib.lxd.instance module."""
from unittest import mock
import pytest

from pycloudlib.instance import BaseInstance
from pycloudlib.lxd.instance import LXDInstance


class TestWaitForCloudinit:
    """Tests covering pycloudlib.lxd.instance._wait_for_cloudinit method."""

    @mock.patch("pycloudlib.lxd.instance.time.sleep")
    @mock.patch.object(BaseInstance, "_wait_for_cloudinit")
    @mock.patch.object(LXDInstance, "is_vm", new_callable=mock.PropertyMock)
    def test_wait_for_vm_with_raise_parameter(
        self, m_is_vm, m_wait_for_cloudinit, m_sleep
    ):  # pylint: disable=W0212
        """Test covering _wait_for_cloudinit on LXD vms."""
        m_is_vm.return_value = True
        instance = LXDInstance(name=None)

        m_wait_for_cloudinit.side_effect = [
            OSError("Failed to connect to lxd-agent"),
            OSError("Failed to connect to lxd-agent"),
            OSError(
                "cloud-init failed to start: out: ................... error"),
            OSError("cloud-init error")
        ]

        with pytest.raises(OSError) as excinfo:
            instance._wait_for_cloudinit(raise_on_failure=True)

        assert m_wait_for_cloudinit.call_args_list == [
            mock.call(raise_on_failure=True),
            mock.call(raise_on_failure=True),
            mock.call(raise_on_failure=True),
            mock.call(raise_on_failure=True)
        ]
        assert m_wait_for_cloudinit.call_count == 4
        assert m_sleep.call_count == 3
        assert "cloud-init error" == str(excinfo.value)
