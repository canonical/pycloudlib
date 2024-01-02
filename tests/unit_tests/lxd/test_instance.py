"""Tests for pycloudlib.lxd.instance."""
import re
from copy import deepcopy
from json import dumps
from unittest import mock

import pytest

from pycloudlib.errors import PycloudlibTimeoutError
from pycloudlib.lxd.instance import LXDInstance, LXDVirtualMachineInstance
from pycloudlib.result import Result

LXD_QUERY = {
    "state": {
        "network": {
            "enp5s0": {
                "addresses": [
                    {
                        "address": "10.161.80.57",
                        "family": "inet",
                        "netmask": "24",
                        "scope": "global",
                    },
                    {
                        "address": "fd42:80e2:4695:1e96:216:3eff:fe06:e5f6",
                        "family": "inet6",
                        "netmask": "64",
                        "scope": "global",
                    },
                    {
                        "address": "fe80::216:3eff:fe06:e5f6",
                        "family": "inet6",
                        "netmask": "64",
                        "scope": "link",
                    },
                ],
                "counters": {
                    "bytes_received": 627023316,
                    "bytes_sent": 5159667,
                    "errors_received": 0,
                    "errors_sent": 0,
                    "packets_dropped_inbound": 0,
                    "packets_dropped_outbound": 0,
                    "packets_received": 344183,
                    "packets_sent": 71759,
                },
                "host_name": "tap55cb7af1",
                "hwaddr": "00:16:3e:06:e5:f6",
                "mtu": 1500,
                "state": "up",
                "type": "broadcast",
            },
            "lo": {
                "addresses": [
                    {
                        "address": "127.0.0.1",
                        "family": "inet",
                        "netmask": "8",
                        "scope": "local",
                    },
                    {
                        "address": "::1",
                        "family": "inet6",
                        "netmask": "128",
                        "scope": "local",
                    },
                ],
                "counters": {
                    "bytes_received": 67612,
                    "bytes_sent": 67612,
                    "errors_received": 0,
                    "errors_sent": 0,
                    "packets_dropped_inbound": 0,
                    "packets_dropped_outbound": 0,
                    "packets_received": 654,
                    "packets_sent": 654,
                },
                "host_name": "",
                "hwaddr": "",
                "mtu": 65536,
                "state": "up",
                "type": "loopback",
            },
            "veth1998ea41": {
                "addresses": [],
                "counters": {
                    "bytes_received": 100604,
                    "bytes_sent": 13587,
                    "errors_received": 0,
                    "errors_sent": 0,
                    "packets_dropped_inbound": 0,
                    "packets_dropped_outbound": 0,
                    "packets_received": 1210,
                    "packets_sent": 42,
                },
                "host_name": "",
                "hwaddr": "56:f1:b2:7f:8b:32",
                "mtu": 1500,
                "state": "up",
                "type": "broadcast",
            },
        },
        "pid": 182418,
        "processes": 46,
        "status": "Running",
        "status_code": 103,
    },
}

LXD_QUERY_BOND_BRIDGE = {
    "state": {
        "network": {
            "bond0": {
                "addresses": [],
                "counters": {
                    "bytes_received": 284039,
                    "bytes_sent": 32537,
                    "errors_received": 0,
                    "errors_sent": 0,
                    "packets_dropped_inbound": 0,
                    "packets_dropped_outbound": 0,
                    "packets_received": 419,
                    "packets_sent": 332,
                },
                "host_name": "tapd24998e9",
                "hwaddr": "02:00:00:56:ca:9f",
                "mtu": 1500,
                "state": "up",
                "type": "broadcast",
            },
            "enp5s0": {
                "addresses": [],
                "counters": {
                    "bytes_received": 284039,
                    "bytes_sent": 32537,
                    "errors_received": 0,
                    "errors_sent": 0,
                    "packets_dropped_inbound": 0,
                    "packets_dropped_outbound": 0,
                    "packets_received": 419,
                    "packets_sent": 332,
                },
                "host_name": "tapd24998e9",
                "hwaddr": "02:00:00:56:ca:9f",
                "mtu": 1500,
                "state": "up",
                "type": "broadcast",
            },
            "lo": {
                "addresses": [
                    {
                        "address": "127.0.0.1",
                        "family": "inet",
                        "netmask": "8",
                        "scope": "local",
                    },
                    {
                        "address": "::1",
                        "family": "inet6",
                        "netmask": "128",
                        "scope": "local",
                    },
                ],
                "counters": {
                    "bytes_received": 8280,
                    "bytes_sent": 8280,
                    "errors_received": 0,
                    "errors_sent": 0,
                    "packets_dropped_inbound": 0,
                    "packets_dropped_outbound": 0,
                    "packets_received": 104,
                    "packets_sent": 104,
                },
                "host_name": "",
                "hwaddr": "",
                "mtu": 65536,
                "state": "up",
                "type": "loopback",
            },
            "ovs-br": {
                "addresses": [
                    {
                        "address": "10.96.250.88",
                        "family": "inet",
                        "netmask": "24",
                        "scope": "global",
                    },
                    {
                        "address": "fd42:54d5:33be:7862:8da:baff:fe4e:dd4a",
                        "family": "inet6",
                        "netmask": "64",
                        "scope": "global",
                    },
                    {
                        "address": "fe80::ff:fe56:ca9f",
                        "family": "inet6",
                        "netmask": "64",
                        "scope": "link",
                    },
                ],
                "counters": {
                    "bytes_received": 279989,
                    "bytes_sent": 30289,
                    "errors_received": 0,
                    "errors_sent": 0,
                    "packets_dropped_inbound": 0,
                    "packets_dropped_outbound": 0,
                    "packets_received": 448,
                    "packets_sent": 304,
                },
                "host_name": "",
                "hwaddr": "0a:da:ba:4e:dd:4a",
                "mtu": 1500,
                "state": "up",
                "type": "broadcast",
            },
            "ovs-br.100": {
                "addresses": [
                    {
                        "address": "fe80::8da:baff:fe4e:dd4a",
                        "family": "inet6",
                        "netmask": "64",
                        "scope": "link",
                    }
                ],
                "counters": {
                    "bytes_received": 0,
                    "bytes_sent": 1076,
                    "errors_received": 0,
                    "errors_sent": 0,
                    "packets_dropped_inbound": 0,
                    "packets_dropped_outbound": 0,
                    "packets_received": 0,
                    "packets_sent": 14,
                },
                "host_name": "",
                "hwaddr": "0a:da:ba:4e:dd:4a",
                "mtu": 1500,
                "state": "up",
                "type": "broadcast",
            },
            "ovs-br.200": {
                "addresses": [
                    {
                        "address": "fe80::8da:baff:fe4e:dd4a",
                        "family": "inet6",
                        "netmask": "64",
                        "scope": "link",
                    }
                ],
                "counters": {
                    "bytes_received": 0,
                    "bytes_sent": 1146,
                    "errors_received": 0,
                    "errors_sent": 0,
                    "packets_dropped_inbound": 0,
                    "packets_dropped_outbound": 0,
                    "packets_received": 0,
                    "packets_sent": 15,
                },
                "host_name": "",
                "hwaddr": "0a:da:ba:4e:dd:4a",
                "mtu": 1500,
                "state": "up",
                "type": "broadcast",
            },
            "ovs-system": {
                "addresses": [],
                "counters": {
                    "bytes_received": 0,
                    "bytes_sent": 0,
                    "errors_received": 0,
                    "errors_sent": 0,
                    "packets_dropped_inbound": 0,
                    "packets_dropped_outbound": 0,
                    "packets_received": 0,
                    "packets_sent": 0,
                },
                "host_name": "",
                "hwaddr": "d6:45:c7:56:47:43",
                "mtu": 1500,
                "state": "down",
                "type": "broadcast",
            },
        }
    }
}

LXD_QUERY_IPV6_ONLY = {
    "state": {
        "network": {
            "bond0": {
                "addresses": [],
                "counters": {
                    "bytes_received": 2820,
                    "bytes_sent": 4698,
                    "errors_received": 0,
                    "errors_sent": 0,
                    "packets_dropped_inbound": 0,
                    "packets_dropped_outbound": 0,
                    "packets_received": 22,
                    "packets_sent": 52,
                },
                "host_name": "tap027f33c0",
                "hwaddr": "02:00:00:c6:51:4f",
                "mtu": 1500,
                "state": "up",
                "type": "broadcast",
            },
            "enp5s0": {
                "addresses": [],
                "counters": {
                    "bytes_received": 2820,
                    "bytes_sent": 4698,
                    "errors_received": 0,
                    "errors_sent": 0,
                    "packets_dropped_inbound": 0,
                    "packets_dropped_outbound": 0,
                    "packets_received": 22,
                    "packets_sent": 52,
                },
                "host_name": "tap027f33c0",
                "hwaddr": "02:00:00:c6:51:4f",
                "mtu": 1500,
                "state": "up",
                "type": "broadcast",
            },
            "lo": {
                "addresses": [
                    {
                        "address": "127.0.0.1",
                        "family": "inet",
                        "netmask": "8",
                        "scope": "local",
                    },
                    {
                        "address": "::1",
                        "family": "inet6",
                        "netmask": "128",
                        "scope": "local",
                    },
                ],
                "counters": {
                    "bytes_received": 7256,
                    "bytes_sent": 7256,
                    "errors_received": 0,
                    "errors_sent": 0,
                    "packets_dropped_inbound": 0,
                    "packets_dropped_outbound": 0,
                    "packets_received": 92,
                    "packets_sent": 92,
                },
                "host_name": "",
                "hwaddr": "",
                "mtu": 65536,
                "state": "up",
                "type": "loopback",
            },
            "ovs-br": {
                "addresses": [
                    {
                        "address": "fd42:5f0a:40d6:c5b9:609a:bbff:fe75:7c43",
                        "family": "inet6",
                        "netmask": "64",
                        "scope": "global",
                    },
                    {
                        "address": "fe80::ff:fec6:514f",
                        "family": "inet6",
                        "netmask": "64",
                        "scope": "link",
                    },
                ],
                "counters": {
                    "bytes_received": 3936,
                    "bytes_sent": 2968,
                    "errors_received": 0,
                    "errors_sent": 0,
                    "packets_dropped_inbound": 0,
                    "packets_dropped_outbound": 0,
                    "packets_received": 44,
                    "packets_sent": 31,
                },
                "host_name": "",
                "hwaddr": "62:9a:bb:75:7c:43",
                "mtu": 1500,
                "state": "up",
                "type": "broadcast",
            },
            "ovs-br.100": {
                "addresses": [
                    {
                        "address": "fe80::609a:bbff:fe75:7c43",
                        "family": "inet6",
                        "netmask": "64",
                        "scope": "link",
                    }
                ],
                "counters": {
                    "bytes_received": 0,
                    "bytes_sent": 866,
                    "errors_received": 0,
                    "errors_sent": 0,
                    "packets_dropped_inbound": 0,
                    "packets_dropped_outbound": 0,
                    "packets_received": 0,
                    "packets_sent": 11,
                },
                "host_name": "",
                "hwaddr": "62:9a:bb:75:7c:43",
                "mtu": 1500,
                "state": "up",
                "type": "broadcast",
            },
            "ovs-br.200": {
                "addresses": [
                    {
                        "address": "fe80::609a:bbff:fe75:7c43",
                        "family": "inet6",
                        "netmask": "64",
                        "scope": "link",
                    }
                ],
                "counters": {
                    "bytes_received": 0,
                    "bytes_sent": 866,
                    "errors_received": 0,
                    "errors_sent": 0,
                    "packets_dropped_inbound": 0,
                    "packets_dropped_outbound": 0,
                    "packets_received": 0,
                    "packets_sent": 11,
                },
                "host_name": "",
                "hwaddr": "62:9a:bb:75:7c:43",
                "mtu": 1500,
                "state": "up",
                "type": "broadcast",
            },
            "ovs-system": {
                "addresses": [],
                "counters": {
                    "bytes_received": 0,
                    "bytes_sent": 0,
                    "errors_received": 0,
                    "errors_sent": 0,
                    "packets_dropped_inbound": 0,
                    "packets_dropped_outbound": 0,
                    "packets_received": 0,
                    "packets_sent": 0,
                },
                "host_name": "",
                "hwaddr": "72:05:bf:60:22:ec",
                "mtu": 1500,
                "state": "down",
                "type": "broadcast",
            },
        }
    }
}

LXD_QUERY_IPV4_VS_IPV6 = {
    "state": {
        "network": {
            "bond0": {
                "addresses": [],
                "counters": {
                    "bytes_received": 2820,
                    "bytes_sent": 4698,
                    "errors_received": 0,
                    "errors_sent": 0,
                    "packets_dropped_inbound": 0,
                    "packets_dropped_outbound": 0,
                    "packets_received": 22,
                    "packets_sent": 52,
                },
                "host_name": "tap027f33c0",
                "hwaddr": "02:00:00:c6:51:4f",
                "mtu": 1500,
                "state": "up",
                "type": "broadcast",
            },
            "lo": {
                "addresses": [
                    {
                        "address": "127.0.0.1",
                        "family": "inet",
                        "netmask": "8",
                        "scope": "local",
                    },
                    {
                        "address": "::1",
                        "family": "inet6",
                        "netmask": "128",
                        "scope": "local",
                    },
                ],
                "counters": {
                    "bytes_received": 7256,
                    "bytes_sent": 7256,
                    "errors_received": 0,
                    "errors_sent": 0,
                    "packets_dropped_inbound": 0,
                    "packets_dropped_outbound": 0,
                    "packets_received": 92,
                    "packets_sent": 92,
                },
                "host_name": "",
                "hwaddr": "",
                "mtu": 65536,
                "state": "up",
                "type": "loopback",
            },
            "ovs-br": {
                "addresses": [
                    {
                        "address": "fd42:5f0a:40d6:c5b9:609a:bbff:fe75:7c43",
                        "family": "inet6",
                        "netmask": "64",
                        "scope": "global",
                    },
                    {
                        "address": "fe80::ff:fec6:514f",
                        "family": "inet6",
                        "netmask": "64",
                        "scope": "link",
                    },
                ],
                "counters": {
                    "bytes_received": 3936,
                    "bytes_sent": 2968,
                    "errors_received": 0,
                    "errors_sent": 0,
                    "packets_dropped_inbound": 0,
                    "packets_dropped_outbound": 0,
                    "packets_received": 44,
                    "packets_sent": 31,
                },
                "host_name": "",
                "hwaddr": "62:9a:bb:75:7c:43",
                "mtu": 1500,
                "state": "up",
                "type": "broadcast",
            },
            "enp5s0": {
                "addresses": [
                    {
                        "address": "172.16.254.1",
                        "family": "inet",
                        "netmask": "64",
                        "scope": "global",
                    },
                ],
                "counters": {
                    "bytes_received": 2820,
                    "bytes_sent": 4698,
                    "errors_received": 0,
                    "errors_sent": 0,
                    "packets_dropped_inbound": 0,
                    "packets_dropped_outbound": 0,
                    "packets_received": 22,
                    "packets_sent": 52,
                },
                "host_name": "tap027f33c0",
                "hwaddr": "02:00:00:c6:51:4f",
                "mtu": 1500,
                "state": "up",
                "type": "broadcast",
            },
            "ovs-br.100": {
                "addresses": [
                    {
                        "address": "fe80::609a:bbff:fe75:7c43",
                        "family": "inet6",
                        "netmask": "64",
                        "scope": "link",
                    }
                ],
                "counters": {
                    "bytes_received": 0,
                    "bytes_sent": 866,
                    "errors_received": 0,
                    "errors_sent": 0,
                    "packets_dropped_inbound": 0,
                    "packets_dropped_outbound": 0,
                    "packets_received": 0,
                    "packets_sent": 11,
                },
                "host_name": "",
                "hwaddr": "62:9a:bb:75:7c:43",
                "mtu": 1500,
                "state": "up",
                "type": "broadcast",
            },
            "ovs-br.200": {
                "addresses": [
                    {
                        "address": "fe80::609a:bbff:fe75:7c43",
                        "family": "inet6",
                        "netmask": "64",
                        "scope": "link",
                    }
                ],
                "counters": {
                    "bytes_received": 0,
                    "bytes_sent": 866,
                    "errors_received": 0,
                    "errors_sent": 0,
                    "packets_dropped_inbound": 0,
                    "packets_dropped_outbound": 0,
                    "packets_received": 0,
                    "packets_sent": 11,
                },
                "host_name": "",
                "hwaddr": "62:9a:bb:75:7c:43",
                "mtu": 1500,
                "state": "up",
                "type": "broadcast",
            },
            "ovs-system": {
                "addresses": [],
                "counters": {
                    "bytes_received": 0,
                    "bytes_sent": 0,
                    "errors_received": 0,
                    "errors_sent": 0,
                    "packets_dropped_inbound": 0,
                    "packets_dropped_outbound": 0,
                    "packets_received": 0,
                    "packets_sent": 0,
                },
                "host_name": "",
                "hwaddr": "72:05:bf:60:22:ec",
                "mtu": 1500,
                "state": "down",
                "type": "broadcast",
            },
        }
    }
}


class TestRestart:
    """Tests covering pycloudlib.lxd.instance.Instance.restart."""

    @pytest.mark.parametrize("force", (False, True))
    @mock.patch("pycloudlib.lxd.instance.subp")
    def test_restart_calls_lxc_cmd_with_force_param(self, m_subp, force):
        """Honor force param on restart."""
        instance = LXDInstance(name="my_vm")
        instance._do_restart(force=force)  # pylint: disable=protected-access
        if force:
            assert "--force" in m_subp.call_args[0][0]
        else:
            assert "--force" not in m_subp.call_args[0][0]

    @mock.patch("pycloudlib.lxd.instance.LXDInstance.shutdown")
    @mock.patch("pycloudlib.lxd.instance.subp")
    def test_restart_does_not_shutdown(self, _m_subp, m_shutdown):
        """Don't shutdown (stop) instance on restart."""
        instance = LXDInstance(name="my_vm")
        instance._do_restart()  # pylint: disable=protected-access
        assert not m_shutdown.called


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
    def test_exec_with_run_command_on_xenial_machine(self, m_subp, caplog):
        """Test exec does not work with xenial vm."""
        instance = LXDVirtualMachineInstance(
            None, execute_via_ssh=False, series="xenial"
        )

        instance._run_command(["test"], None)
        assert self._missing_agent_msg in caplog.text
        assert m_subp.call_count == 1

    @mock.patch("pycloudlib.lxd.instance.subp")
    def test_file_pull_with_agent_on_xenial_machine(self, m_subp, caplog):
        """Test file pull does not work with xenial vm."""
        instance = LXDVirtualMachineInstance(
            None, execute_via_ssh=False, series="xenial"
        )

        instance.pull_file("/some/file", "/some/local/file")
        assert self._missing_agent_msg in caplog.text
        assert m_subp.call_count == 1

    @mock.patch("pycloudlib.lxd.instance.subp")
    def test_file_push_with_agent_on_xenial_machine(self, m_subp, caplog):
        """Test file push does not work with xenial vm."""
        instance = LXDVirtualMachineInstance(
            None, execute_via_ssh=False, series="xenial"
        )

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
                ["unparseable"],
                "",
                0,
                150,
                PycloudlibTimeoutError(
                    "Unable to determine IP address after 150 retries."
                    " exit:0 stdout: unparseable stderr: "
                ),
            ),
            (  # retry on non-zero exit code
                [dumps(LXD_QUERY)],
                "",
                1,
                150,
                PycloudlibTimeoutError(
                    "Unable to determine IP address after 150 retries."
                    " exit:1 stdout:"
                ),
            ),
            (  # empty values will retry indefinitely
                [""],
                "",
                0,
                150,
                PycloudlibTimeoutError(
                    "Unable to determine IP address after 150 retries."
                    " exit:0 stdout:  stderr: "
                ),
            ),
            (  # only retry until success
                ["unparseable", dumps(LXD_QUERY)],
                "",
                0,
                1,
                "10.161.80.57",
            ),
            ([dumps(LXD_QUERY)], "", 0, 0, "10.161.80.57"),
        ),
    )
    @mock.patch("pycloudlib.lxd.instance.time.sleep")
    @mock.patch("pycloudlib.lxd.instance.subp")
    def test_ip_parses_ipv4_output_from_lxc(
        self, m_subp, m_sleep, stdouts, stderr, return_code, sleeps, expected
    ):
        """IPv4 output matches specific vm name from `lxc list`.

        Errors are retried and result in PycloudlibTimeoutError on failure.
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
            ["lxc", "query", "/1.0/instances/my_vm?recursion=1"]
        )
        if isinstance(expected, Exception):
            with pytest.raises(type(expected), match=re.escape(str(expected))):
                instance.ip  # pylint: disable=pointless-statement
            assert [lxc_mock] * sleeps == m_subp.call_args_list
        else:
            assert expected == instance.ip
            assert [lxc_mock] * (1 + sleeps) == m_subp.call_args_list
        assert sleeps == m_sleep.call_count

    def test_parse_ip(self):
        """Verify ipv4 parser."""
        assert "10.161.80.57" == LXDInstance(name="my_vm").parse_ip(LXD_QUERY)
        local = deepcopy(LXD_QUERY)
        local.get("state", {}).get("network", {}).pop("enp5s0")
        assert LXDInstance(name="my_vm").parse_ip(local) is None

    def test_parse_ip_bond_bridge(self):
        """Verify ipv4 parser with a cfg with bonds and bridging."""
        assert "10.96.250.88" == LXDInstance(name="my_vm").parse_ip(
            LXD_QUERY_BOND_BRIDGE
        )

    def test_parse_ip_ipv6_only(self):
        """Verify ip parser works with a cfg with a globlal ipv6 address."""
        assert "fd42:5f0a:40d6:c5b9:609a:bbff:fe75:7c43" == LXDInstance(
            name="my_vm"
        ).parse_ip(LXD_QUERY_IPV6_ONLY)

    def test_parse_ip_prefer_ipv4(self):
        """Verify ip parser prefers ipv4 addresses over ipv6 ones."""
        assert "172.16.254.1" == LXDInstance(name="my_vm").parse_ip(
            LXD_QUERY_IPV4_VS_IPV6
        )


class TestWaitForStop:
    """Tests covering pycloudlib.lxd.instance.Instance.wait_for_stop."""

    @pytest.mark.parametrize("is_ephemeral", ((True), (False)))
    def test_wait_for_stop_does_not_wait_for_ephemeral_instances(
        self, is_ephemeral
    ):
        """LXDInstance.wait_for_stop does not wait on ephemeral instances."""
        instance = LXDInstance(name="test")
        with mock.patch.object(instance, "wait_for_state") as wait_for_state:
            with mock.patch.object(type(instance), "ephemeral", is_ephemeral):
                instance.wait_for_stop()

        call_count = 0 if is_ephemeral else 1
        assert call_count == wait_for_state.call_count


class TestShutdown:
    """Tests covering pycloudlib.lxd.instance.Instance.shutdown."""

    @pytest.mark.parametrize(
        "wait,force,cmd",
        (
            (True, False, ["lxc", "stop", "test"]),
            (False, False, ["lxc", "stop", "test"]),
            (True, True, ["lxc", "stop", "test", "--force"]),
        ),
    )
    @mock.patch("pycloudlib.lxd.instance.subp")
    def test_shutdown_calls_wait_for_stopped_state_when_wait_true(
        self, m_subp, wait, force, cmd
    ):
        """LXDInstance.wait_for_stopped called when wait is True."""
        instance = LXDInstance(name="test")
        with mock.patch.object(instance, "wait_for_stop") as wait_for_stop:
            with mock.patch.object(type(instance), "state", "RUNNING"):
                instance.shutdown(wait=wait, force=force)

        assert [mock.call(cmd)] == m_subp.call_args_list
        call_count = 1 if wait else 0
        assert call_count == wait_for_stop.call_count


class TestDelete:
    """Tests covering pycloudlib.lxd.instance.Instance.delete."""

    @pytest.mark.parametrize("is_ephemeral", ((True), (False)))
    @mock.patch("pycloudlib.lxd.instance.LXDInstance.shutdown")
    @mock.patch("pycloudlib.lxd.instance.subp")
    def test_delete_on_ephemeral_instance_calls_shutdown(
        self, m_subp, m_shutdown, is_ephemeral
    ):
        """Check if ephemeral instance delete stops it instead of deleting it.

        Also verify is delete is actually called if instance is not ephemeral.
        """
        instance = LXDInstance(name="test")

        with mock.patch.object(type(instance), "ephemeral", is_ephemeral):
            instance.delete(wait=False)

        assert 0 == m_shutdown.call_count
        assert 1 == m_subp.call_count
        assert [
            mock.call(["lxc", "delete", "test", "--force"])
        ] == m_subp.call_args_list
