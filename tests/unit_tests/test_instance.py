"""Tests related to pycloudlib.instance module."""

from itertools import repeat

import pytest
from paramiko import SSHException

from pycloudlib.errors import PycloudlibTimeoutError
from pycloudlib.instance import BaseInstance
from pycloudlib.result import Result

# Disable this pylint check as fixture usage incorrectly triggers it:
# pylint: disable=redefined-outer-name


@pytest.fixture
def concrete_instance_cls(mocker):
    """Return a BaseInstance subclass which can be instantiated.

    Source: https://stackoverflow.com/a/28738073
    """
    mocker.patch.object(BaseInstance, "__abstractmethods__", set())
    return BaseInstance


class TestWait:
    """Tests covering pycloudlib.instance.Instance.wait."""

    def test_wait(self, concrete_instance_cls, mocker):
        """Test wait calls the two methods it should with correct passthrough.

        (`None` is used to test the default.)
        """
        instance = concrete_instance_cls(key_pair=None)
        mocks = mocker.patch.multiple(
            instance,
            _wait_for_instance_start=mocker.DEFAULT,
            _wait_for_execute=mocker.DEFAULT,
            _wait_for_cloudinit=mocker.DEFAULT,
        )
        instance.wait()

        assert 1 == mocks["_wait_for_instance_start"].call_count
        assert 1 == mocks["_wait_for_execute"].call_count
        assert 1 == mocks["_wait_for_cloudinit"].call_count

    @pytest.mark.parametrize(
        "execute_effect",
        [
            pytest.param(lambda *args, **kwargs: Result("", "", 1), id="nonzero"),
            pytest.param(SSHException, id="exception"),
        ],
    )
    def test_wait_execute_failure(
        self,
        execute_effect,
        concrete_instance_cls,
        mocker,
    ):
        """Test wait calls when execute command fails."""
        mocker.patch("logging.Logger.debug")
        mocker.patch("logging.Logger.info")
        m_time = mocker.patch("pycloudlib.instance.time.time")
        m_sleep = mocker.patch("pycloudlib.instance.time.sleep")
        m_execute = mocker.patch.object(BaseInstance, "execute")

        instance = concrete_instance_cls(key_pair=None)
        m_time.side_effect = [1, 1, 2, 10 * 60 + 1]
        m_execute.side_effect = execute_effect
        expected_msg = "Instance can't be reached after 10 minutes. Failed to obtain new boot id"
        expected_call_args = [mocker.call("cat /proc/sys/kernel/random/boot_id", no_log=True)] * 2

        with pytest.raises(PycloudlibTimeoutError) as excinfo:
            instance.wait()

        assert expected_msg == str(excinfo.value)
        assert m_sleep.call_count == 2
        assert expected_call_args == m_execute.call_args_list


class TestRestart:
    """Test base restart behavior."""

    @pytest.fixture(autouse=True)
    def setup_mocks(self, mocker):
        """Mock things we don't want as test parameters."""
        mocker.patch("pycloudlib.instance.BaseInstance._sync_filesystem")
        self.m_wait_for_restart = mocker.patch("pycloudlib.instance.BaseInstance.wait_for_restart")
        self.m_wait = mocker.patch("pycloudlib.instance.BaseInstance.wait")
        self.m_boot_id = mocker.patch("pycloudlib.instance.BaseInstance.get_boot_id")
        self.m_do_restart = mocker.patch("pycloudlib.instance.BaseInstance._do_restart")

    def test_no_wait(
        self,
        concrete_instance_cls,
    ):
        """Test wait=False."""
        instance = concrete_instance_cls(key_pair=None)
        instance.restart(wait=False)
        assert self.m_do_restart.call_count == 1
        assert self.m_boot_id.call_count == 0
        assert self.m_wait_for_restart.call_count == 0
        assert self.m_wait.call_count == 0

    def test_instance_not_reachable(
        self,
        concrete_instance_cls,
    ):
        """Test when instance is not reachable."""
        instance = concrete_instance_cls(key_pair=None)
        self.m_boot_id.side_effect = SSHException
        instance.restart(wait=True)
        assert self.m_do_restart.call_count == 1
        assert self.m_wait_for_restart.call_count == 0
        assert self.m_wait.call_count == 1

    def test_instance_reachable(
        self,
        concrete_instance_cls,
    ):
        """Test when instance is reachable."""
        instance = concrete_instance_cls(key_pair=None)
        self.m_boot_id.side_effect = Result("11111111-1111-1111-1111-111111111111", "", 0)
        instance.restart(wait=True)
        assert self.m_do_restart.call_count == 1
        assert self.m_wait_for_restart.call_count == 1
        assert self.m_wait.call_count == 0


class TestWaitForRestart:
    """Tests covering pycloudlib.instance.Instance.wait_for_restart."""

    def test_wait_for_restart(
        self, concrete_instance_cls, mocker
    ):
        """Test wait calls _wait_for_execute and waits till differing."""
        mocker.patch("pycloudlib.instance.time.time", return_value=1)
        mocker.patch("pycloudlib.instance.time.sleep")
        mocker.patch.object(BaseInstance, "_wait_for_cloudinit")
        m_execute = mocker.patch.object(
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

        instance = concrete_instance_cls(key_pair=None)
        instance.wait_for_restart(old_boot_id="11111111-1111-1111-1111-111111111111")
        assert m_execute.call_count == 5

    @pytest.mark.parametrize(
        "execute_side_effect",
        [
            SSHException,
            repeat(Result("11111111-1111-1111-1111-111111111111", "", 0)),
        ],
    )
    def test_boot_id_failure(
        self,
        execute_side_effect,
        concrete_instance_cls,
        mocker,
    ):
        """Test wait calls when execute command fails."""
        mocker.patch("logging.Logger.debug")
        mocker.patch("logging.Logger.info")
        m_time = mocker.patch("pycloudlib.instance.time.time")
        m_sleep = mocker.patch("pycloudlib.instance.time.sleep")
        m_execute = mocker.patch.object(BaseInstance, "execute")

        m_execute.side_effect = execute_side_effect
        instance = concrete_instance_cls(key_pair=None)
        m_time.side_effect = [1, 1, 2, 10 * 60 + 1]
        expected_msg = "Instance can't be reached after 10 minutes. Failed to obtain new boot id"
        expected_call_args = [mocker.call("cat /proc/sys/kernel/random/boot_id", no_log=True)] * 2

        with pytest.raises(PycloudlibTimeoutError) as excinfo:
            instance.wait_for_restart(old_boot_id="11111111-1111-1111-1111-111111111111")

        assert expected_msg == str(excinfo.value)
        assert m_sleep.call_count == 2
        assert expected_call_args == m_execute.call_args_list


# Disable this one because we're intentionally testing a protected member
# pylint: disable=protected-access
class TestWaitForCloudinit:
    """Tests covering pycloudlib.instance.Instance._wait_for_cloudinit."""

    def test_with_wait_available(self, concrete_instance_cls, mocker):
        """Test the happy path for instances with `status --wait`."""
        instance = concrete_instance_cls(key_pair=None)
        m_execute = mocker.patch.object(instance, "execute")
        instance._wait_for_cloudinit()

        assert (
            mocker.call(
                ["cloud-init", "status", "--wait", "--long"],
                description="waiting for start",
            )
            == m_execute.call_args
        )

    def test_wait_on_target_not_active(self, concrete_instance_cls, mocker):
        """Test that we wait for cloud-init is-active before calling status."""
        mocker.patch("time.sleep")
        instance = concrete_instance_cls(key_pair=None)
        m_execute = mocker.patch.object(
            instance,
            "execute",
            side_effect=[Result("", "", 0)] + [Result("", "", 1)] * 500,
        )

        instance._wait_for_cloudinit()
        expected = [
            mocker.call("command -v systemctl"),
            *(
                [
                    mocker.call(
                        ["systemctl", "is-active", "cloud-init.target"],
                        no_log=True,
                    )
                ]
                * 300
            ),
            mocker.call(
                ["cloud-init", "status", "--wait", "--long"],
                description="waiting for start",
            ),
        ]
        assert expected == m_execute.call_args_list


class TestClean:
    """Tests covering pycloudlib.instance.BaseInstance.clean."""

    def test_clean_with_c_all_support(self, concrete_instance_cls, mocker):
        """Test clean method when cloud-init supports -c all option."""
        instance = concrete_instance_cls(key_pair=None)
        m_execute = mocker.patch.object(
            instance,
            "execute",
            side_effect=[
                Result("", "", 0),  # cloud-init clean --logs --machine-id -c all
                Result("", "", 0),  # rm -rf /var/log/syslog
            ],
        )
        instance.clean()

        expected_calls = [
            mocker.call("sudo cloud-init clean --logs --machine-id -c all"),
            mocker.call("sudo rm -rf /var/log/syslog"),
        ]
        assert expected_calls == m_execute.call_args_list

    def test_clean_without_arg_support(self, concrete_instance_cls, mocker):
        """Test clean method when cloud-init doesn't support -c all option."""
        instance = concrete_instance_cls(key_pair=None)
        m_execute = mocker.patch.object(
            instance,
            "execute",
            side_effect=[
                Result(
                    "",
                    "cloud-init clean: error: unrecognized arguments: -c all",
                    2,
                ),  # First attempt fails
                Result("", "", 0),  # Fallback without -c all
                Result("", "", 0),  # rm -rf /var/log/syslog
            ],
        )
        instance.clean()

        expected_calls = [
            mocker.call("sudo cloud-init clean --logs --machine-id -c all"),
            mocker.call("sudo cloud-init clean --logs"),
            mocker.call("sudo rm -rf /var/log/syslog"),
        ]
        assert expected_calls == m_execute.call_args_list

    def test_clean_unexpected_error(self, concrete_instance_cls, mocker):
        """Test clean method does not fallback on unexpected error."""
        instance = concrete_instance_cls(key_pair=None)
        m_execute = mocker.patch.object(
            instance,
            "execute",
            side_effect=[
                Result(
                    "",
                    "cloud-init clean: error: permission denied",
                    1,
                ),  # Different error
                Result("", "", 0),  # rm -rf /var/log/syslog
            ],
        )
        instance.clean()

        expected_calls = [
            mocker.call("sudo cloud-init clean --logs --machine-id -c all"),
            mocker.call("sudo rm -rf /var/log/syslog"),
        ]
        assert expected_calls == m_execute.call_args_list
