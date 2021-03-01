"""Openstack instance tests."""
from unittest import mock

from pycloudlib.openstack.instance import OpenstackInstance

SERVER_ADDRESSES = {
    'no_floating': [
        {
            'OS-EXT-IPS-MAC:mac_addr': '11:11:11:11:11:11',
            'addr': '10.0.0.1',
            'OS-EXT-IPS:type': 'fixed',
            'version': 4
        },
    ],
    'includes_floating': [
        {
            'OS-EXT-IPS-MAC:mac_addr': '22:22:22:22:22:22',
            'addr': '10.0.0.2',
            'OS-EXT-IPS:type': 'fixed',
            'version': 4
        },
        {
            'OS-EXT-IPS-MAC:mac_addr': '33:33:33:33:33:33',
            'addr': '10.0.0.3',
            'OS-EXT-IPS:type': 'floating',
            'version': 4
        }
    ]
}

# While the actual results from openstack will have a lot more values
# in the dict, 'floating_ip_address' is all we care about
NETWORK_IPS = [
    {'floating_ip_address': '10.0.0.4', 'unrelated': 'field'},
    {'floating_ip_address': '10.0.0.3', 'dont': 'care'},
]


@mock.patch(
    'pycloudlib.openstack.instance.OpenstackInstance.'
    '_create_and_attach_floating_id'
)
class TestAttachFloatingIp:
    """Ensure we create/use floating IPs accordingly."""

    def test_existing_floating_ip(self, m_create):
        """Test that if a server has an existing floating IP, we use it."""
        m_connection = mock.Mock()
        m_server = m_connection.compute.get_server.return_value
        m_server.addresses = SERVER_ADDRESSES
        m_connection.network.ips.return_value = NETWORK_IPS

        instance = OpenstackInstance(None, None, connection=m_connection)
        assert '10.0.0.3' == instance.floating_ip['floating_ip_address']
        assert 0 == m_create.call_count

    def test_no_matching_floating_ip(self, m_create):
        """Test that if a server doesn't have a floating IP, we create it."""
        m_connection = mock.Mock()
        m_server = m_connection.compute.get_server.return_value = mock.Mock()
        m_server.addresses = SERVER_ADDRESSES
        m_connection.network.ips.return_value = []

        instance = OpenstackInstance(None, None, connection=m_connection)
        assert instance.floating_ip is m_create.return_value
        assert 1 == m_create.call_count
