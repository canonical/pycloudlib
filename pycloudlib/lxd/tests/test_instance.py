"""Tests for pycloudlib.lxd.instance."""
from unittest import mock

from pycloudlib.lxd.instance import LXDInstance


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
