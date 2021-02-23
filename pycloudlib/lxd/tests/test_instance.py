"""Tests for pycloudlib.lxd.instance."""
from unittest import mock

from pycloudlib.lxd.instance import LXDInstance, LXDVirtualMachineInstance


class TestExecute:
    """Tests covering pycloudlib.lxd.instance.Instance.execute."""

    def test_all_rcs_acceptable_when_using_exec(self):
        """Test that we invoke util.subp with rcs=None for exec calls.

        rcs=None means that we will get a Result object back for all return
        codes, rather than an exception for non-zero return codes.
        """
        instance = LXDInstance(None, execute_via_ssh=False)
        with mock.patch("pycloudlib.lxd.instance.subp") as m_subp:
            instance.execute("some_command")
        assert 1 == m_subp.call_count
        args, kwargs = m_subp.call_args
        assert "exec" in args[0]
        assert kwargs.get("rcs", mock.sentinel.not_none) is None


class TestVirtualMachineExecute:  # pylint: disable=W0212
    """Tests covering pycloudlib.lxd.instance.LXDVirtualMachineInstance."""

    @mock.patch("pycloudlib.lxd.instance.subp")
    def test_exec_with_run_command_on_xenial_machine(
        self,
        _m_subp,
        caplog
    ):
        """Test exec does not work with xenial vm."""
        instance = LXDVirtualMachineInstance(
            None, execute_via_ssh=False, series="xenial")

        instance._run_command(["test"], None)
        expected_msg = (
            "Many xenial images do not support executing commands"
            " via exec due to missing kernel support: you may see"
            " unavoidable failures.\nSee"
            " https://github.com/canonical/pycloudlib/issues/132 for"
            " details."
        )
        assert expected_msg in caplog.messages
        assert _m_subp.call_count == 1
