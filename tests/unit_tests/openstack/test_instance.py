"""Openstack instance tests."""

import pytest

from unittest import mock

from pycloudlib.openstack.instance import OpenstackInstance

SERVER_ADDRESSES = {
    "no_floating": [
        {
            "OS-EXT-IPS-MAC:mac_addr": "11:11:11:11:11:11",
            "addr": "10.0.0.1",
            "OS-EXT-IPS:type": "fixed",
            "version": 4,
        },
    ],
    "includes_floating": [
        {
            "OS-EXT-IPS-MAC:mac_addr": "22:22:22:22:22:22",
            "addr": "10.0.0.2",
            "OS-EXT-IPS:type": "fixed",
            "version": 4,
        },
        {
            "OS-EXT-IPS-MAC:mac_addr": "33:33:33:33:33:33",
            "addr": "10.0.0.3",
            "OS-EXT-IPS:type": "floating",
            "version": 4,
        },
    ],
}

# While the actual results from openstack will have a lot more values
# in the dict, 'floating_ip_address' is all we care about
NETWORK_IPS = [
    {"floating_ip_address": "10.0.0.4", "unrelated": "field"},
    {"floating_ip_address": "10.0.0.3", "dont": "care"},
]


class TestAttachFloatingIp:
    """Ensure we create/use floating IPs accordingly."""

    @pytest.fixture(autouse=True)
    def setup_connection(self):
        self.conn = mock.Mock()
        m_server = self.conn.compute.get_server.return_value
        m_server.addresses = SERVER_ADDRESSES
        m_create_floating_ip = self.conn.create_floating_ip.return_value
        m_create_floating_ip.floating_ip_address = "10.42.42.42"
        self.conn.network.ports.return_value = [
            mock.Mock(id="port1"), mock.Mock(id="port2")
        ]

    def test_existing_floating_ip(self):
        """Test that if a server has an existing floating IP, we use it."""
        self.conn.network.ips.return_value = NETWORK_IPS

        instance = OpenstackInstance(
            key_pair=None,
            instance_id=None,
            network_id=None,
            connection=self.conn,
        )
        assert "10.0.0.3" == instance.floating_ip["floating_ip_address"]
        assert 0 == self.conn.create_floating_ip.call_count

    def test_no_matching_floating_ip(self):
        """Test that if a server doesn't have a floating IP, we create it."""
        self.conn.network.ips.return_value = []

        instance = OpenstackInstance(
            key_pair=None,
            instance_id=None,
            network_id=None,
            connection=self.conn,
        )
        assert instance.floating_ip is self.conn.create_floating_ip.return_value
        assert 1 == self.conn.create_floating_ip.call_count
        self.conn.network.update_ip.assert_called_once_with(
            self.conn.create_floating_ip.return_value, port_id='port1'
        )
