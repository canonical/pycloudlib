"""Tests for pycloudlib.lxd.instance."""
import re
from unittest import mock

import pytest

from pycloudlib.lxd.instance import LXDInstance, LXDVirtualMachineInstance
from pycloudlib.result import Result


class TestRestart:
    """Tests covering pycloudlib.lxd.instance.Instance.restart."""

    @pytest.mark.parametrize(
        "wait,force,cmd",
        (
            (True, True, ["lxc", "restart", "my_vm", "--force"]),
            (True, False, ["lxc", "restart", "my_vm"]),
            # When wait is false, call shutdown and start
            (False, False, []), (False, True, [])
        )
    )
    @mock.patch("pycloudlib.lxd.instance.LXDInstance.start")
    @mock.patch("pycloudlib.lxd.instance.LXDInstance.shutdown")
    @mock.patch("pycloudlib.lxd.instance.LXDInstance.wait")
    @mock.patch("pycloudlib.lxd.instance.subp")
    def test_restart_calls_lxc_cmd_with_force_param(
        self, m_subp, m_wait, m_shutdown, m_start, wait, force, cmd
    ):
        """When wait=True, honor force param on lxc restart cmdline.

        When wait is False will wait on shutdown and not wait on start.
        """
        instance = LXDInstance(name="my_vm")
        instance.restart(force=force, wait=wait)
        if wait:
            assert [mock.call(cmd)] == m_subp.call_args_list
            assert 0 == m_shutdown.call_count
            assert 0 == m_start.call_count
            assert 1 == m_wait.call_count
        else:
            assert 0 == m_subp.call_count
            assert [
                mock.call(wait=True, force=force)
            ] == m_shutdown.call_args_list
            assert [mock.call(wait=wait)] == m_start.call_args_list
            assert 0 == m_wait.call_count


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
        expected_msg = (
            "Many Xenial images do not support `lxc file push` due to missing"
            " lxd-agent: you may see unavoidable failures.\n"
            "See https://github.com/canonical/pycloudlib/issues/132 for"
            " details."
        )
        assert expected_msg in caplog.messages
        assert m_subp.call_count == 1


class TestIP:
    """Tests covering pycloudlib.lxd.instance.Instance.ip."""

    @pytest.mark.parametrize(
        "stdouts,stderr,return_code,sleeps,expected",
        (
             (
                  ["unparseable"], "", 0, 150,
                  TimeoutError(
                      "Unable to determine IP address after 150 retries."
                      " exit:0 stdout: unparseable stderr: "
                  )
             ),
             (    # retry on non-zero exit code
                  ["10.0.0.1 (eth0)"], "", 1, 150,
                  TimeoutError(
                      "Unable to determine IP address after 150 retries."
                      " exit:1 stdout: 10.0.0.1 (eth0) stderr: "
                  )
             ),
             (    # empty values will retry indefinitely
                  [""], "", 0, 150,
                  TimeoutError(
                      "Unable to determine IP address after 150 retries."
                      " exit:0 stdout:  stderr: "
                  )
             ),
             (    # only retry until success
                  ["unparseable", "10.69.10.5 (eth0)\n"], "", 0, 1,
                  "10.69.10.5"
             ),
             (
                   ["10.69.10.5 (eth0)\n"], "", 0, 0, "10.69.10.5"
             ),
        )
    )
    @mock.patch("pycloudlib.lxd.instance.time.sleep")
    @mock.patch("pycloudlib.lxd.instance.subp")
    def test_ip_parses_ipv4_output_from_lxc(
        self, m_subp, m_sleep, stdouts, stderr, return_code, sleeps, expected
    ):
        """IPv4 output matches specific vm name from `lxc list`.

        Errors are retried and result in TimeoutError on failure.
        """
        if len(stdouts) > 1:
            m_subp.side_effect = [
                Result(stdout=out, stderr=stderr, return_code=return_code)
                for out in stdouts
            ]
        else:
            m_subp.return_value = Result(
                stdout=stdouts[0], stderr=stderr, return_code=return_code
            )
        instance = LXDInstance(name="my_vm")
        lxc_mock = mock.call(
            ["lxc", "list", "^my_vm$", "-c4", "--format", "csv"]
        )
        if isinstance(expected, Exception):
            with pytest.raises(type(expected), match=re.escape(str(expected))):
                instance.ip  # pylint: disable=pointless-statement
            assert [lxc_mock] * sleeps == m_subp.call_args_list
        else:
            assert expected == instance.ip
            assert [lxc_mock] * (1 + sleeps) == m_subp.call_args_list
        assert sleeps == m_sleep.call_count
