"""Tests related to pycloudlib.lxd.instance module."""
from unittest import mock

from pycloudlib.instance import BaseInstance
from pycloudlib.lxd.instance import LXDInstance


class TestWaitForCloudinit:
    """Tests covering pycloudlib.lxd.instance._wait_for_cloudinit method."""

    @mock.patch("pycloudlib.lxd.instance.time.sleep")
    @mock.patch.object(BaseInstance, "_wait_for_cloudinit")
    def test_wait_for_vm_with_raise_parameter(
        self, m_wait_for_cloudinit, m_sleep
    ):  # pylint: disable=W0212
        """Test covering _wait_for_cloudinit on LXD vms."""
        instance = LXDInstance(name=None, is_vm=True)

        m_wait_for_cloudinit.side_effect = [OSError(), OSError(), True]
        instance._wait_for_cloudinit(raise_on_failure=True)

        assert m_wait_for_cloudinit.call_args_list == [
            mock.call(raise_on_failure=True),
            mock.call(raise_on_failure=True),
            mock.call(raise_on_failure=True)
        ]
        assert m_sleep.call_count == 2
        assert m_wait_for_cloudinit.call_count == 3
