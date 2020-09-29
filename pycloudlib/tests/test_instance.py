"""Tests related to pycloudlib.instance module."""
from unittest import mock

import pytest

from pycloudlib.lxd.instance import LXDInstance
from pycloudlib.kvm.instance import KVMInstance


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
