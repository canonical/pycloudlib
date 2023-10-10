"""Tests related to pycloudlib.azure.cloud module."""
from io import StringIO

import mock
import pytest

from pycloudlib.azure.cloud import Azure

CONFIG = """\
[azure]

"""


# Disable this one because we're intentionally testing a protected member
# pylint: disable=protected-access
class TestCreateNetworkInterfaceClient:
    """Tests covering _create_network_interface_client method."""

    @pytest.mark.parametrize(
        "inbound_ports",
        (
            ["3128", "8080"],
            None,
        ),
    )
    @mock.patch("pycloudlib.azure.util.get_client")
    def test_create_network_interface_with_inbound_ports(
        self, m_get_client, inbound_ports
    ):
        """Test method handling of inbound_ports."""
        resource_client_mock = mock.MagicMock()
        resource_group_mock = mock.MagicMock()
        resource_mock = mock.MagicMock()

        network_client_mock = mock.MagicMock()
        network_group_mock = mock.MagicMock()
        compute_client_mock = mock.MagicMock()
        m_get_client.side_effect = [
            resource_client_mock,
            network_client_mock,
            compute_client_mock,
        ]

        type(resource_mock).name = mock.PropertyMock(
            return_value="resource_group"
        )
        type(resource_client_mock).resource_groups = mock.PropertyMock(
            return_value=resource_group_mock
        )
        resource_group_mock.create_or_update.return_value = resource_mock
        resource_group_mock.get.return_value = resource_mock
        type(network_client_mock).network_security_groups = mock.PropertyMock(
            return_value=network_group_mock
        )

        instance = Azure(
            tag="tag",
            timestamp_suffix=False,
            config_file=StringIO(CONFIG),
            region="location",
        )
        instance._create_network_security_group(inbound_ports=inbound_ports)

        expected_security_rules = [
            {
                "name": "port-22",
                "priority": 300,
                "protocol": "TCP",
                "access": "Allow",
                "direction": "Inbound",
                "sourceAddressPrefix": "*",
                "sourcePortRange": "*",
                "destinationAddressPrefix": "*",
                "destinationPortRange": "22",
            },
        ]

        if inbound_ports:
            expected_security_rules.extend(
                [
                    {
                        "name": "port-3128",
                        "priority": 310,
                        "protocol": "TCP",
                        "access": "Allow",
                        "direction": "Inbound",
                        "sourceAddressPrefix": "*",
                        "sourcePortRange": "*",
                        "destinationAddressPrefix": "*",
                        "destinationPortRange": "3128",
                    },
                    {
                        "name": "port-8080",
                        "priority": 320,
                        "protocol": "TCP",
                        "access": "Allow",
                        "direction": "Inbound",
                        "sourceAddressPrefix": "*",
                        "sourcePortRange": "*",
                        "destinationAddressPrefix": "*",
                        "destinationPortRange": "8080",
                    },
                ]
            )

        expected_calls = [
            mock.call(
                resource_group_name="resource_group",
                network_security_group_name="tag-sgn",
                parameters={
                    "location": "location",
                    "security_rules": expected_security_rules,
                },
            ),
        ]

        assert (
            expected_calls
            == network_group_mock.begin_create_or_update.call_args_list
        )
