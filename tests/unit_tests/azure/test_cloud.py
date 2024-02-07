"""Tests related to pycloudlib.azure.cloud module."""
import datetime
from io import StringIO

import mock
import pytest
from azure.core.exceptions import ResourceNotFoundError

from pycloudlib.azure.cloud import Azure
from pycloudlib.azure.util import AzureCreateParams, AzureParams

CONFIG = """\
[azure]

"""

resource_client_mock = mock.MagicMock()
resource_group_mock = mock.MagicMock()
resource_mock = mock.MagicMock()

network_client_mock = mock.MagicMock()
network_group_mock = mock.MagicMock()
compute_client_mock = mock.MagicMock()


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

        cloud = Azure(
            tag="tag",
            timestamp_suffix=False,
            config_file=StringIO(CONFIG),
            region="location",
        )
        cloud._create_network_security_group(inbound_ports=inbound_ports)

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


@mock.patch(
    "pycloudlib.azure.util.get_client",
    side_effect=[
        resource_client_mock,
        network_client_mock,
        compute_client_mock,
    ],
)
class TestNonComputeParamsOverrides:
    def test_rg_params_override(self, _m_get_client):
        type(resource_mock).name = mock.PropertyMock(
            return_value="resource_group"
        )
        type(resource_client_mock).resource_groups = mock.PropertyMock(
            return_value=resource_group_mock
        )
        resource_group_mock.create_or_update.return_value = resource_mock
        resource_group_mock.get.side_effect = ResourceNotFoundError()

        new_params = {"location": "new_location", "tags": {"name": "new-tag"}}
        new_rg = AzureParams("default-pyc-rg", new_params)
        cloud = Azure(
            tag="pyc-test",
            timestamp_suffix=False,
            resource_group_params=new_rg,
            config_file=StringIO(CONFIG),
        )
        cloud._create_resource_group()
        assert resource_group_mock.create_or_update.call_count == 2
        expected_calls = [
            mock.call(new_rg.name, new_rg.parameters),
            mock.call(
                cloud.tag + "-rg",
                {
                    "location": cloud.location,
                    "tags": {"name": cloud.tag},
                },
            ),
        ]
        assert (
            expected_calls
            == resource_group_mock.create_or_update.call_args_list
        )

    @pytest.mark.parametrize(
        "nsg_obj",
        (
            None,
            AzureCreateParams(
                "nsg001", "new-nsg-rg", {"location": "new-nsg-location"}
            ),
        ),
    )
    def test_nsg_params_override(self, _m_get_client, nsg_obj):
        type(network_client_mock).network_security_groups = mock.PropertyMock(
            return_value=network_group_mock
        )
        type(resource_mock).name = mock.PropertyMock(return_value="default-rg")
        type(resource_client_mock).resource_groups = mock.PropertyMock(
            return_value=resource_group_mock
        )
        resource_group_mock.create_or_update.return_value = resource_mock
        resource_group_mock.get.side_effect = ResourceNotFoundError()
        cloud = Azure(
            tag="pyc-test",
            timestamp_suffix=False,
            config_file=StringIO(CONFIG),
        )
        cloud._create_network_security_group(None, nsg_obj)
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
        expected_calls = []
        parameters = {
            "location": cloud.location,
            "security_rules": expected_security_rules,
        }
        if not nsg_obj:
            expected_calls = [
                mock.call(
                    resource_group_name="default-rg",
                    network_security_group_name="pyc-test-sgn",
                    parameters=parameters,
                ),
            ]
        else:
            parameters["location"] = "new-nsg-location"
            expected_calls = [
                mock.call(
                    resource_group_name=nsg_obj.resource_group_name,
                    network_security_group_name=nsg_obj.name,
                    parameters=parameters,
                ),
            ]

        assert (
            expected_calls
            == network_group_mock.begin_create_or_update.call_args_list
        )

        network_group_mock.begin_create_or_update.reset_mock()

    @pytest.mark.parametrize(
        "vnet_obj",
        (
            None,
            AzureCreateParams(
                "vnet001",
                "new-vnet-rg",
                {"address_space": {"address_prefixes": ["addr_prefix"]}},
            ),
        ),
    )
    def test_vnet_params_override(self, _m_get_client, vnet_obj):
        virtual_networks = mock.MagicMock()
        type(network_client_mock).virtual_networks = mock.PropertyMock(
            return_value=virtual_networks
        )
        type(resource_mock).name = mock.PropertyMock(return_value="default-rg")
        type(resource_client_mock).resource_groups = mock.PropertyMock(
            return_value=resource_group_mock
        )
        resource_group_mock.create_or_update.return_value = resource_mock
        resource_group_mock.get.side_effect = ResourceNotFoundError()
        cloud = Azure(
            tag="pyc-test",
            timestamp_suffix=False,
            config_file=StringIO(CONFIG),
        )
        cloud._create_virtual_network(None, vnet_obj)

        expected_calls = []

        parameters = {
            "location": cloud.location,
            "address_space": {"address_prefixes": ["10.0.0.0/16"]},
            "tags": {"name": cloud.tag},
        }

        if not vnet_obj:
            expected_calls = [
                mock.call("default-rg", "pyc-test-vnet", parameters)
            ]
        else:
            expected_calls = [
                mock.call(
                    vnet_obj.resource_group_name, vnet_obj.name, parameters
                )
            ]
            parameters["address_space"]["address_prefixes"] = ["addr_prefix"]
            pass
        assert (
            expected_calls
            == virtual_networks.begin_create_or_update.call_args_list
        )

    @pytest.mark.parametrize(
        "subnet_obj",
        (
            None,
            AzureCreateParams(
                "subnet001", "new-subnet-rg", {"address_prefix": "addr_prfx"}
            ),
        ),
    )
    def test_subnet_params_override(self, _m_get_client, subnet_obj):
        subnets = mock.MagicMock()
        type(network_client_mock).subnets = mock.PropertyMock(
            return_value=subnets
        )
        type(resource_mock).name = mock.PropertyMock(
            return_value="default-subnet-rg"
        )
        type(resource_client_mock).resource_groups = mock.PropertyMock(
            return_value=resource_group_mock
        )
        resource_group_mock.create_or_update.return_value = resource_mock
        resource_group_mock.get.side_effect = ResourceNotFoundError()
        cloud = Azure(
            tag="pyc-test",
            timestamp_suffix=False,
            config_file=StringIO(CONFIG),
        )
        cloud._create_subnet("vnet001", subnet_obj)

        expected_calls = []

        parameters = {
            "address_prefix": "10.0.0.0/24",
            "tags": {"name": cloud.tag},
        }

        if not subnet_obj:
            expected_calls = [
                mock.call(
                    "default-subnet-rg",
                    "vnet001",
                    cloud.tag + "-subnet",
                    parameters,
                )
            ]
        else:
            parameters["address_prefix"] = "addr_prfx"
            expected_calls = [
                mock.call(
                    subnet_obj.resource_group_name,
                    "vnet001",
                    subnet_obj.name,
                    parameters,
                )
            ]
        assert expected_calls == subnets.begin_create_or_update.call_args_list

    @pytest.mark.parametrize(
        "ip_obj",
        (
            None,
            AzureCreateParams(
                "ip001", "new-ip-rg", {"sku": {"name": "Basic"}}
            ),
        ),
    )
    @mock.patch("datetime.datetime", wraps=datetime.datetime)
    def test_ip_params_override(self, dt, _m_get_client, ip_obj):
        test_dt = datetime.datetime(2024, 2, 1, 16, 58, 45, 948199)
        dt.now.return_value = test_dt
        us = test_dt.strftime("%f")
        public_ip_addresses = mock.MagicMock()
        type(network_client_mock).public_ip_addresses = mock.PropertyMock(
            return_value=public_ip_addresses
        )
        type(resource_mock).name = mock.PropertyMock(
            return_value="default-ip-rg"
        )
        type(resource_client_mock).resource_groups = mock.PropertyMock(
            return_value=resource_group_mock
        )
        resource_group_mock.create_or_update.return_value = resource_mock
        resource_group_mock.get.side_effect = ResourceNotFoundError()
        cloud = Azure(
            tag="pyc-test",
            timestamp_suffix=False,
            config_file=StringIO(CONFIG),
        )
        cloud._create_ip_address(ip_obj)

        expected_calls = []

        parameters = {
            "location": cloud.location,
            "sku": {"name": "Standard"},
            "public_ip_allocation_method": "Static",
            "rpublic_ip_address_version": "IPV4",
            "tags": {"name": cloud.tag},
        }

        if not ip_obj:
            expected_calls = [
                mock.call(
                    "default-ip-rg",
                    "{}-{}-ip".format(cloud.tag, us),
                    parameters,
                )
            ]
        else:
            parameters["sku"]["name"] = "Basic"
            expected_calls = [
                mock.call(
                    ip_obj.resource_group_name,
                    ip_obj.name,
                    parameters,
                )
            ]
        assert (
            expected_calls
            == public_ip_addresses.begin_create_or_update.call_args_list
        )

    @pytest.mark.parametrize(
        "nic_obj",
        (
            None,
            AzureCreateParams(
                "nic001", "new-nic-rg", {"location": "new-nic-location"}
            ),
        ),
    )
    @mock.patch("datetime.datetime", wraps=datetime.datetime)
    def test_nic_params_override(self, dt, _m_get_client, nic_obj):
        test_dt = datetime.datetime(2024, 2, 1, 16, 58, 45, 948199)
        dt.now.return_value = test_dt
        us = test_dt.strftime("%f")
        network_interfaces = mock.MagicMock()
        type(network_client_mock).network_interfaces = mock.PropertyMock(
            return_value=network_interfaces
        )
        type(resource_mock).name = mock.PropertyMock(
            return_value="default-nic-rg"
        )
        type(resource_client_mock).resource_groups = mock.PropertyMock(
            return_value=resource_group_mock
        )
        resource_group_mock.create_or_update.return_value = resource_mock
        resource_group_mock.get.side_effect = ResourceNotFoundError()
        cloud = Azure(
            tag="pyc-test",
            timestamp_suffix=False,
            config_file=StringIO(CONFIG),
        )
        cloud._create_network_interface_client(
            "ip_id", "subnet_id", "nsg_id", nic_obj
        )

        expected_calls = []

        parameters = {
            "location": cloud.location,
            "ip_configurations": [
                {
                    "name": "{}-{}-ip-config".format(cloud.tag, us),
                    "subnet": {"id": "subnet_id"},
                    "public_ip_address": {"id": "ip_id"},
                }
            ],
            "network_security_group": {"id": "nsg_id"},
            "tags": {"name": cloud.tag},
        }
        if not nic_obj:
            expected_calls = [
                mock.call(
                    "default-nic-rg", "{}-nic".format(cloud.tag), parameters
                )
            ]
        else:
            parameters["location"] = "new-nic-location"
            parameters["ip_configurations"] = [
                {
                    "name": "{}-{}-ip-config".format(nic_obj.name, us),
                    "subnet": {"id": "subnet_id"},
                    "public_ip_address": {"id": "ip_id"},
                }
            ]
            expected_calls = [
                mock.call(
                    nic_obj.resource_group_name, nic_obj.name, parameters
                )
            ]
        assert (
            expected_calls
            == network_interfaces.begin_create_or_update.call_args_list
        )
