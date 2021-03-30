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


class TestVirtualMachineXenialAgentOperations:  # pylint: disable=W0212
    """Tests covering pycloudlib.lxd.instance.LXDVirtualMachineInstance."""

    # Key information we want in the logs when using non-ssh Xenial instances.
    _missing_agent_msg = "missing lxd-agent"

    @mock.patch("pycloudlib.lxd.instance.subp")
    def test_exec_with_run_command_on_xenial_machine(
        self,
        m_subp,
        caplog
    ):
        """Test exec does not work with xenial vm."""
        instance = LXDVirtualMachineInstance(
            None, execute_via_ssh=False, series="xenial")

        instance._run_command(["test"], None)
        assert self._missing_agent_msg in caplog.text
        assert m_subp.call_count == 1

    @mock.patch("pycloudlib.lxd.instance.subp")
    def test_file_pull_with_agent_on_xenial_machine(
        self,
        m_subp,
        caplog
    ):
        """Test file pull does not work with xenial vm."""
        instance = LXDVirtualMachineInstance(
            None, execute_via_ssh=False, series="xenial")

        instance.pull_file("/some/file", "/some/local/file")
        assert self._missing_agent_msg in caplog.text
        assert m_subp.call_count == 1

    @mock.patch("pycloudlib.lxd.instance.subp")
    def test_file_push_with_agent_on_xenial_machine(
        self,
        m_subp,
        caplog
    ):
        """Test file push does not work with xenial vm."""
        instance = LXDVirtualMachineInstance(
            None, execute_via_ssh=False, series="xenial")

        instance.push_file("/some/file", "/some/local/file")
        assert self._missing_agent_msg in caplog.text
        assert m_subp.call_count == 1
