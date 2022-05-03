"""Tests related to pycloudlib.instance module."""
from unittest import mock

import pytest

from pycloudlib.instance import BaseInstance
from pycloudlib.result import Result

# Disable this pylint check as fixture usage incorrectly triggers it:
# pylint: disable=redefined-outer-name


@pytest.fixture
def concrete_instance_cls():
    """Return a BaseInstance subclass which can be instantiated.

    Source: https://stackoverflow.com/a/28738073
    """
    with mock.patch.object(BaseInstance, "__abstractmethods__", set()):
        yield BaseInstance


class TestWait:
    """Tests covering pycloudlib.instance.Instance.wait."""

    def test_wait(self, concrete_instance_cls):
        """Test wait calls the two methods it should with correct passthrough.

        (`None` is used to test the default.)
        """
        instance = concrete_instance_cls(key_pair=None)
        with mock.patch.multiple(
            instance,
            _wait_for_instance_start=mock.DEFAULT,
            _wait_for_execute=mock.DEFAULT,
            _wait_for_cloudinit=mock.DEFAULT,
        ) as mocks:
            instance.wait()

        assert 1 == mocks["_wait_for_instance_start"].call_count
        assert 1 == mocks["_wait_for_execute"].call_count
        assert 1 == mocks["_wait_for_cloudinit"].call_count

    @mock.patch.object(BaseInstance, "execute")
    @mock.patch("pycloudlib.instance.time.sleep")
    @mock.patch("pycloudlib.instance.time.time")
    def test_wait_execute_failure(
        self, m_time, m_sleep, m_execute, concrete_instance_cls
    ):
        """Test wait calls when execute command fails."""
        instance = concrete_instance_cls(key_pair=None)
        m_time.side_effect = [1, 2, 40 * 60, 40 * 60 + 1]
        m_execute.return_value = Result(stdout="", stderr="", return_code=1)
        expected_msg = "{}\n{}".format(
            "Instance can't be reached after 40 minutes. ",
            "Failed to execute whoami command",
        )
        expected_call_args = [mock.call("whoami")] * 2

        with pytest.raises(OSError) as excinfo:
            instance.wait()

        assert expected_msg == str(excinfo.value)
        assert m_sleep.call_count == 2
        assert expected_call_args == m_execute.call_args_list


# Disable this one because we're intentionally testing a protected member
# pylint: disable=protected-access
class TestWaitForCloudinit:
    """Tests covering pycloudlib.instance.Instance._wait_for_cloudinit."""

    def test_with_wait_available(self, concrete_instance_cls):
        """Test the happy path for instances with `status --wait`."""
        instance = concrete_instance_cls(key_pair=None)
        with mock.patch.object(instance, "execute") as m_execute:
            instance._wait_for_cloudinit()

        assert (
            mock.call(
                ["cloud-init", "status", "--wait", "--long"],
                description="waiting for start",
            )
            == m_execute.call_args
        )

    @mock.patch("time.sleep")
    def test_wait_on_target_not_active(self, _m_sleep, concrete_instance_cls):
        """Test that we wait for cloud-init is-active before calling status."""
        instance = concrete_instance_cls(key_pair=None)
        with mock.patch.object(
            instance,
            "execute",
            side_effect=[Result("", "", 0)] + [Result("", "", 1)] * 500,
        ) as m_execute:
            instance._wait_for_cloudinit()
        expected = [
            mock.call(["which", "systemctl"]),
            *(
                [mock.call(["systemctl", "is-active", "cloud-init.target"])]
                * 300
            ),
            mock.call(
                ["cloud-init", "status", "--wait", "--long"],
                description="waiting for start",
            ),
        ]
        assert expected == m_execute.call_args_list
