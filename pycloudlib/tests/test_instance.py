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
    def test_wait_execute_failure(
        self, m_sleep, m_execute, concrete_instance_cls
    ):
        """Test wait calls when execute command fails."""
        instance = concrete_instance_cls(key_pair=None)
        m_execute.return_value = Result(stdout="", stderr="", return_code=1)
        expected_msg = "{}\n{}".format(
            "Instance can't be reached", "Failed to execute whoami command"
        )
        expected_call_args = [mock.call("whoami")] * 101

        with pytest.raises(OSError) as excinfo:
            instance.wait()

        assert expected_msg == str(excinfo.value)
        assert expected_call_args == m_execute.call_args_list
        assert m_sleep.call_count == 100


class TestWaitForCloudinit:
    """Tests covering pycloudlib.instance.Instance._wait_for_cloudinit."""

    # Disable this one because we're intentionally testing a protected member
    # pylint: disable=protected-access

    def test_with_wait_available(self, concrete_instance_cls):
        """Test the happy path for instances with `status --wait`."""

        def side_effect(cmd, *_args, **_kwargs):
            stdout = ""
            if "--help" in cmd:
                stdout = "help content containing --wait"
            return Result(stdout=stdout, stderr="", return_code=0)

        instance = concrete_instance_cls(key_pair=None)
        with mock.patch.object(instance, "execute") as m_execute:
            m_execute.side_effect = side_effect
            instance._wait_for_cloudinit()

        assert 1 == m_execute.call_count
        assert (
            [
                mock.call(
                    ["cloud-init", "status", "--wait", "--long"],
                    description="waiting for start",
                )
            ]
            == m_execute.call_args_list
        )

    def test_failure_path(
        self,
        concrete_instance_cls,
    ):
        """Test failure for both has_wait and !has_wait cases."""

        def side_effect(cmd, *_args, **_kwargs):
            stdout = ""
            if "whoami" == cmd:
                # The whoami call should be successful and inform us
                # that the instance can be reached
                return Result(stdout=stdout, stderr="", return_code=0)

            # Any other call should fail
            return Result(stdout="fail_out", stderr="fail_err", return_code=1)

        instance = concrete_instance_cls(key_pair=None)
        with mock.patch.object(instance, "execute") as m_execute:
            m_execute.side_effect = side_effect
            instance._wait_for_cloudinit()
