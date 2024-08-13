"""Tests related to pycloudlib.instance module."""

from itertools import repeat
from unittest import mock

import pytest
from paramiko import SSHException

from pycloudlib.errors import PycloudlibTimeoutError
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

    @pytest.mark.parametrize(
        "execute_effect",
        [
            pytest.param(
                lambda *args, **kwargs: Result("", "", 1), id="nonzero"
            ),
            pytest.param(SSHException, id="exception"),
        ],
    )
    @mock.patch.object(BaseInstance, "execute")
    @mock.patch("pycloudlib.instance.time.sleep")
    @mock.patch("pycloudlib.instance.time.time")
    @mock.patch("logging.Logger.debug")
    def test_wait_execute_failure(
        self,
        m_debug,
        m_time,
        m_sleep,
        m_execute,
        execute_effect,
        concrete_instance_cls,
    ):
        """Test wait calls when execute command fails."""
        instance = concrete_instance_cls(key_pair=None)
        m_time.side_effect = [1, 1, 2, 40 * 60, 40 * 60 + 1]
        m_execute.side_effect = execute_effect
        expected_msg = (
            "Instance can't be reached after 40 minutes. "
            "Failed to obtain new boot id"
        )
        expected_call_args = [
            mock.call("cat /proc/sys/kernel/random/boot_id", no_log=True)
        ] * 2

        with pytest.raises(PycloudlibTimeoutError) as excinfo:
            instance.wait()

        assert expected_msg == str(excinfo.value)
        assert m_sleep.call_count == 2
        assert expected_call_args == m_execute.call_args_list


@mock.patch("pycloudlib.instance.BaseInstance._do_restart")
@mock.patch("pycloudlib.instance.BaseInstance.get_boot_id")
@mock.patch("pycloudlib.instance.BaseInstance.wait")
@mock.patch("pycloudlib.instance.BaseInstance.wait_for_restart")
class TestRestart:
    """Test base restart behavior."""

    @pytest.fixture(autouse=True)
    def unchecked_mocks(self):
        """Mock things we don't want as test parameters."""
        with mock.patch("pycloudlib.instance.BaseInstance._sync_filesystem"):
            yield

    def test_no_wait(
        self,
        m_wait_for_restart,
        m_wait,
        m_boot_id,
        m_do_restart,
        concrete_instance_cls,
    ):
        """Test wait=False."""
        instance = concrete_instance_cls(key_pair=None)
        instance.restart(wait=False)
        assert m_do_restart.call_count == 1
        assert m_boot_id.call_count == 0
        assert m_wait_for_restart.call_count == 0
        assert m_wait.call_count == 0

    def test_instance_not_reachable(
        self,
        m_wait_for_restart,
        m_wait,
        m_boot_id,
        m_do_restart,
        concrete_instance_cls,
    ):
        """Test when instance is not reachable."""
        instance = concrete_instance_cls(key_pair=None)
        m_boot_id.side_effect = SSHException
        instance.restart(wait=True)
        assert m_do_restart.call_count == 1
        assert m_wait_for_restart.call_count == 0
        assert m_wait.call_count == 1

    def test_instance_reachable(
        self,
        m_wait_for_restart,
        m_wait,
        m_boot_id,
        m_do_restart,
        concrete_instance_cls,
    ):
        """Test when instance is reachable."""
        instance = concrete_instance_cls(key_pair=None)
        m_boot_id.side_effect = Result(
            "11111111-1111-1111-1111-111111111111", "", 0
        )
        instance.restart(wait=True)
        assert m_do_restart.call_count == 1
        assert m_wait_for_restart.call_count == 1
        assert m_wait.call_count == 0


class TestWaitForRestart:
    """Tests covering pycloudlib.instance.Instance.wait_for_restart."""

    @mock.patch.object(
        BaseInstance,
        "execute",
        side_effect=[
            Result("11111111-1111-1111-1111-111111111111", "", 0),
            Result("11111111-1111-1111-1111-111111111111", "", 0),
            Result("11111111-1111-1111-1111-111111111111", "", 0),
            Result("11111111-1111-1111-1111-111111111111", "", 0),
            Result("22222222-2222-2222-2222-222222222222", "", 0),
        ],
    )
    @mock.patch.object(BaseInstance, "_wait_for_cloudinit")
    @mock.patch("pycloudlib.instance.time.sleep")
    @mock.patch("pycloudlib.instance.time.time", return_value=1)
    def test_wait_for_restart(
        self, _m_time, _m_sleep, _m_wait_ci, m_execute, concrete_instance_cls
    ):
        """Test wait calls _wait_for_execute and waits till differing."""
        instance = concrete_instance_cls(key_pair=None)
        instance.wait_for_restart(
            old_boot_id="11111111-1111-1111-1111-111111111111"
        )
        assert m_execute.call_count == 5

    @pytest.mark.parametrize(
        "execute_side_effect",
        [
            SSHException,
            repeat(Result("11111111-1111-1111-1111-111111111111", "", 0)),
        ],
    )
    @mock.patch.object(BaseInstance, "execute")
    @mock.patch("pycloudlib.instance.time.sleep")
    @mock.patch("pycloudlib.instance.time.time")
    @mock.patch("logging.Logger.debug")
    def test_boot_id_failure(
        self,
        m_debug,
        m_time,
        m_sleep,
        m_execute,
        execute_side_effect,
        concrete_instance_cls,
    ):
        """Test wait calls when execute command fails."""
        m_execute.side_effect = execute_side_effect
        instance = concrete_instance_cls(key_pair=None)
        m_time.side_effect = [1, 1, 2, 40 * 60, 40 * 60 + 1]
        expected_msg = (
            "Instance can't be reached after 40 minutes. "
            "Failed to obtain new boot id"
        )
        expected_call_args = [
            mock.call("cat /proc/sys/kernel/random/boot_id", no_log=True)
        ] * 2

        with pytest.raises(PycloudlibTimeoutError) as excinfo:
            instance.wait_for_restart(
                old_boot_id="11111111-1111-1111-1111-111111111111"
            )

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
            mock.call("command -v systemctl"),
            *(
                [
                    mock.call(
                        ["systemctl", "is-active", "cloud-init.target"],
                        no_log=True,
                    )
                ]
                * 300
            ),
            mock.call(
                ["cloud-init", "status", "--wait", "--long"],
                description="waiting for start",
            ),
        ]
        assert expected == m_execute.call_args_list
