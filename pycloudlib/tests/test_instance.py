"""Tests related to pycloudlib.instance module."""
from contextlib import suppress as noop
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

    @pytest.mark.parametrize(
        "instance_cls,cloud_name",
        (
            (LXDInstance, "lxd"),
            (KVMInstance, "kvm"),
        ),
    )
    def test_all_rcs_acceptable(self, instance_cls, cloud_name):
        """Test that we invoke util.subp with rcs=None.

        rcs=None means that we will get a Result object back for all return
        codes, rather than an exception for non-zero return codes.
        """
        instance = instance_cls(None)
        with mock.patch(
            "pycloudlib.{}.instance.subp".format(cloud_name)
        ) as m_subp:
            instance.execute("some_command")
        assert 1 == m_subp.call_count
        _args, kwargs = m_subp.call_args
        assert kwargs.get("rcs", mock.sentinel.not_none) is None


class TestWait:
    """Tests covering pycloudlib.instance.Instance.wait."""

    @pytest.mark.parametrize("raise_on_cloudinit_failure", [True, False, None])
    def test_wait(self, raise_on_cloudinit_failure, concrete_instance_cls):
        """Test wait calls the two methods it should with correct passthrough.

        (`None` is used to test the default.)
        """
        instance = concrete_instance_cls(key_pair=None)
        with mock.patch.multiple(
            instance,
            _wait_for_instance_start=mock.DEFAULT,
            _wait_for_cloudinit=mock.DEFAULT,
        ) as mocks:
            if raise_on_cloudinit_failure is not None:
                instance.wait(
                    raise_on_cloudinit_failure=raise_on_cloudinit_failure
                )
            else:
                instance.wait()

        assert 1 == mocks["_wait_for_instance_start"].call_count
        assert 1 == mocks["_wait_for_cloudinit"].call_count
        kwargs = mocks["_wait_for_cloudinit"].call_args[1]
        if raise_on_cloudinit_failure is None:
            # We expect True by default
            raise_on_cloudinit_failure = True
        assert kwargs["raise_on_failure"] == raise_on_cloudinit_failure


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
            instance._wait_for_cloudinit(raise_on_failure=True)

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
            return_code = 0
            if "--help" in cmd:
                # `cloud-init status --help` on trusty returns non-zero
                return_code = 2
                stdout = "help content without wait"
            return Result(stdout=stdout, stderr="", return_code=return_code)

        instance = concrete_instance_cls(key_pair=None)
        with mock.patch.object(instance, "execute") as m_execute:
            m_execute.side_effect = side_effect
            instance._wait_for_cloudinit(raise_on_failure=True)

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

    @pytest.mark.parametrize(
        "raise_on_failure,expectation",
        [(True, pytest.raises(OSError)), (False, noop())],
    )
    @pytest.mark.parametrize("has_wait", [True, False])
    def test_failure_path(
        self,
        has_wait,
        raise_on_failure,
        expectation,
        concrete_instance_cls,
    ):
        """Test failure for both has_wait and !has_wait cases."""

        def side_effect(cmd, *_args, **_kwargs):
            stdout = ""
            if "--help" in cmd:
                # The --help call should contain the appropriate output to
                # select --wait or not, and is unsuccessful if it doesn't (to
                # mirror trusty's behaviour)
                return_code = 2
                if has_wait:
                    return_code = 0
                    stdout = "help content containing --wait"
                return Result(
                    stdout=stdout, stderr="", return_code=return_code
                )
            # Any other call should fail
            return Result(stdout="fail_out", stderr="fail_err", return_code=1)

        instance = concrete_instance_cls(key_pair=None)
        with mock.patch.object(instance, "execute") as m_execute:
            m_execute.side_effect = side_effect
            with expectation as excinfo:
                instance._wait_for_cloudinit(raise_on_failure=raise_on_failure)

        if raise_on_failure:
            assert "out: fail_out error: fail_err" in str(excinfo.value)
