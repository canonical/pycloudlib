"""Tests related to pycloudlib.instance module."""
from unittest import mock

import pytest

from pycloudlib.instance import BaseInstance
from pycloudlib.kvm.instance import KVMInstance
from pycloudlib.lxd.instance import LXDInstance
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


class TestExecute:
    """Tests covering pycloudlib.instance.Instance.execute.

    TODO: There are elements of `execute` which could be refactored onto the
          relevant subclasses.  Some of these tests should move along with that
          refactor.
    """

    @pytest.mark.parametrize("instance_cls", (LXDInstance, KVMInstance))
    def test_all_rcs_acceptable(self, instance_cls):
        """Test that we invoke util.subp with rcs=None.

        rcs=None means that we will get a Result object back for all return
        codes, rather than an exception for non-zero return codes.
        """
        instance = instance_cls(None)
        with mock.patch("pycloudlib.instance.subp") as m_subp:
            instance.execute("some_command")
        assert 1 == m_subp.call_count
        _args, kwargs = m_subp.call_args
        assert kwargs.get("rcs", mock.sentinel.not_none) is None


class TestWait:
    """Tests covering pycloudlib.instance.Instance.wait."""

    def test_wait(self, concrete_instance_cls):
        """Test that wait calls the two methods it should."""
        instance = concrete_instance_cls(key_pair=None)
        with mock.patch.multiple(
            instance,
            _wait_for_instance_start=mock.DEFAULT,
            _wait_for_cloudinit=mock.DEFAULT,
        ) as mocks:
            instance.wait()

        assert 1 == mocks["_wait_for_instance_start"].call_count
        assert 1 == mocks["_wait_for_cloudinit"].call_count


class TestWaitForSystem:
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

        assert 2 == m_execute.call_count
        assert (
            mock.call("cloud-init status --help")
            == m_execute.call_args_list[0]
        )
        assert (
            mock.call(
                ["cloud-init", "status", "--wait", "--long"],
                description="waiting for start",
            )
            == m_execute.call_args_list[1]
        )

    def test_without_wait_available(self, concrete_instance_cls):
        """Test the happy path for instances without `status --wait`."""

        def side_effect(cmd, *_args, **_kwargs):
            stdout = ""
            if "--help" in cmd:
                stdout = "help content without wait"
            return Result(stdout=stdout, stderr="", return_code=0)

        instance = concrete_instance_cls(key_pair=None)
        with mock.patch.object(instance, "execute") as m_execute:
            m_execute.side_effect = side_effect
            instance._wait_for_cloudinit()

        assert 2 == m_execute.call_count
        assert (
            mock.call("cloud-init status --help")
            == m_execute.call_args_list[0]
        )
        # There's no point checksum testing the full shellscript: test enough
        # to be sure we've got the right thing.
        first_arg = m_execute.call_args_list[1][0][0]
        assert "runlevel" in first_arg
        assert "result.json" in first_arg

    @pytest.mark.parametrize("has_wait", [True, False])
    def test_failure_path(self, has_wait, concrete_instance_cls):
        """Test failure for both has_wait and !has_wait cases."""

        def side_effect(cmd, *_args, **_kwargs):
            stdout = ""
            if "--help" in cmd:
                # The --help call should be successful, and contain the
                # appropriate output to select --wait or not
                if has_wait:
                    stdout = "help content containing --wait"
                return Result(stdout=stdout, stderr="", return_code=0)
            # Any other call should fail
            return Result(stdout="fail_out", stderr="fail_err", return_code=1)

        instance = concrete_instance_cls(key_pair=None)
        with mock.patch.object(instance, "execute") as m_execute:
            m_execute.side_effect = side_effect
            with pytest.raises(OSError) as excinfo:
                instance._wait_for_cloudinit()

        assert "out: fail_out error: fail_err" in str(excinfo.value)
