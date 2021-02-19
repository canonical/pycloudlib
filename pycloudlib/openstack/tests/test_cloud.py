"""Openstack cloud tests."""
from unittest import mock

import pytest
from openstack.connection import Connection

from pycloudlib.openstack.cloud import Openstack


@mock.patch('pycloudlib.key.KeyPair.public_key_content',
            new_callable=mock.PropertyMock,
            return_value='pretend public key')
@mock.patch('openstack.connect', return_value=mock.Mock(spec=Connection))
class TestOpenstackKeypair:
    """Tests covering _get_openstack_keypair."""

    def test_keypair_doesnt_exist(self, m_openstack, _m_public_key_content):
        """Test no pre-existing openstack keypair."""
        m_openstack.return_value.get_keypair.return_value = None
        cloud = Openstack(tag='test', network=None)
        cloud._get_openstack_keypair()
        assert 1 == cloud.conn.create_keypair.call_count

    def test_keypairs_match(self, m_openstack, m_public_key_content):
        """Test pre-existing openstack keypair has same name and content."""
        openstack_keypair_mock = mock.Mock()
        openstack_keypair_mock.public_key = m_public_key_content()
        m_openstack.return_value.get_keypair.return_value = \
            openstack_keypair_mock
        cloud = Openstack(tag='test', network=None)
        assert openstack_keypair_mock == cloud._get_openstack_keypair()

    def test_keypairs_dont_match(self, m_openstack, m_public_key_content):
        """Test pre-existing openstack keypair has different content."""
        openstack_keypair_mock = mock.Mock()
        openstack_keypair_mock.public_key = m_public_key_content()
        m_openstack.return_value.get_keypair.return_value = 'something else'
        cloud = Openstack(tag='test', network=None)
        with pytest.raises(Exception):
            cloud._get_openstack_keypair()
