# This file is part of pycloudlib. See LICENSE file for license information.
"""Azure Cloud type."""
import base64

from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.compute import ComputeManagementClient
from azure.common.client_factory import get_client_from_cli_profile

from pycloudlib.cloud import BaseCloud
from pycloudlib.azure.instance import AzureInstance


class Azure(BaseCloud):
    """Azure Cloud Class."""

    _type = 'azure'

    def __init__(self, tag, client_id=None, client_secret_id=None,
                 subscription_id=None, tenant_id=None):
        """Initialize the connection to Azure.

        Azure will try to read user credentials form the /home/$USER/.azure
        folder. However, we can overwrite those credentials with the provided
        id parameters.

        Args:
            tag: string used to name and tag resources with
            client_id: user's client id
            client_secret_id: user's client secret access key
            subscription_id: user's subscription id key
            tenant_id: user's tenant id key
        """
        super().__init__(tag)
        self._log.debug('logging into Azure')
        self.location = "centralus"
        config_dict = {}

        if client_id:
            config_dict["clientId"] = client_id

        if client_secret_id:
            config_dict["clientSecret"] = client_secret_id

        if subscription_id:
            config_dict["subscriptionId"] = subscription_id

        if tenant_id:
            config_dict["tenantId"] = tenant_id

        self.resource_client = get_client_from_cli_profile(
            ResourceManagementClient, **config_dict)

        self.network_client = get_client_from_cli_profile(
            NetworkManagementClient, **config_dict)

        self.compute_client = get_client_from_cli_profile(
            ComputeManagementClient, **config_dict)

        self.resource_group = None

    def create_network_security_group(self, resource_group_name):
        security_group_name = "{}-sgn".format(self.tag)
        nsg_group = self.network_client.network_security_groups

        self._log.debug('Creating Azure network security group')
        nsg_call = nsg_group.create_or_update(
            resource_group_name=resource_group_name,
            network_security_group_name=security_group_name,
            parameters={
                "location": self.location,
                "security_rules": [
                    {
                        "name": "SSH",
                        "properties": {
                            "priority": 300,
                            "protocol": "TCP",
                            "access": "Allow",
                            "direction": "Inbound",
                            "sourceAddressPrefix": "*",
                            "sourcePortRange": "*",
                            "destinationAddressPrefix": "*",
                            "destinationPortRange": "22"
                        }
                    }
                ]
            }
        )

        return nsg_call.result()

    def create_resource_group(self):
        resource_name = "{}-rg".format(self.tag)
        self._log.debug('Creating Azure resource group')

        return self.resource_client.resource_groups.create_or_update(
            resource_name,
            {
                "location": self.location
            }
        )

    def create_virtual_network(self, resource_group_name,
                               address_prefixes=None):
        if address_prefixes is None:
            address_prefixes = ["10.0.0.0/16"]

        virtual_network_name = "{}-vnet".format(self.tag)

        self._log.debug('Creating Azure virtual network')
        network_call = self.network_client.virtual_networks.create_or_update(
            resource_group_name,
            virtual_network_name,
            {
                "location": self.location,
                "address_space": {
                    "address_prefixes": address_prefixes
                }
            }
        )

        return network_call.result()

    def create_subnet(self, resource_group_name, vnet_name,
                      address_prefix="10.0.0.0/24"):
        subnet_name = "{}-subnet".format(self.tag)

        self._log.debug('Creating Azure subnet')
        subnet_call = self.network_client.subnets.create_or_update(
            resource_group_name,
            vnet_name,
            subnet_name,
            {"address_prefix": address_prefix}
        )

        return subnet_call.result()

    def create_ip_address(self, resource_group_name):
        ip_name = "{}-ip".format(self.tag)

        self._log.debug('Creating Azure ip address')
        ip_call = self.network_client.public_ip_addresses.create_or_update(
            resource_group_name,
            ip_name,
            {
                "location": self.location,
                "sku": {"name": "Standard"},
                "public_ip_allocation_method": "Static",
                "public_ip_address_version": "IPV4"
            }
        )

        return ip_call.result()

    def create_network_interface_client(self, resource_group_name,
                                        ip_address_id, subnet_id, nsg_id):
        nic_name = "{}-nic".format(self.tag)
        ip_config_name = "{}-ip-config".format(self.tag)

        self._log.debug('Creating Azure network interface')
        nic_call = self.network_client.network_interfaces.create_or_update(
            resource_group_name,
            nic_name,
            {
                "location": self.location,
                "ip_configurations": [
                    {
                        "name": ip_config_name,
                        "subnet": {
                            "id": subnet_id
                        },
                        "public_ip_address": {
                            "id": ip_address_id
                            }
                    }
                ],
                "network_security_group": {
                    "id": nsg_id
                }
            }
        )

        return nic_call.result()

    def create_vm_parameters(self, vm_name, nic_id, user_data):
        username = "ubuntu"

        vm_parameters = {
            "location": self.location,
            "storage_profile": {
                "image_reference": {
                    "publisher": 'Canonical',
                    "offer": "UbuntuServer",
                    "sku": "16.04.0-LTS",
                    "version": "latest"
                }
            },
            "hardware_profile": {
                "vm_size": "Standard_DS1_v2"
            },
            "os_profile": {
                "computer_name": vm_name,
                "admin_username": username,
                "linux_configuration": {
                    "ssh": {
                        "public_keys": [
                            {
                                "path": "/home/{}/.ssh/authorized_keys".format(
                                    username),
                                "key_data": self.key_pair.public_key_content
                            }
                        ]
                    },
                    "disable_password_authentication": True
                }
            },
            "network_profile": {
                "network_interfaces": [{
                    "id": nic_id,
                }]
            }
        }

        if user_data:
            vm_parameters["os_profile"]["custom_data"] = base64.b64encode(
                user_data.encode()).decode()

        return vm_parameters

    def create_virtual_machine(self, resource_group_name, nic_id, user_data):
        vm_name = "{}-vm".format(self.tag)

        self._log.debug('Creating Azure virtual machine')
        vm_call = self.compute_client.virtual_machines.create_or_update(
            resource_group_name,
            vm_name,
            self.create_vm_parameters(vm_name, nic_id, user_data)
        )

        return vm_call.result()

    def delete_image(self, image_id):
        self._log.debug(
            'Deleting Azure virtual machine: {}'.format(image_id))
        delete_vm_resp = self.compute_client.virtual_machines.delete(
            resource_group_name=self.resource_group.name,
            vm_name=image_id)

        response_code = delete_vm_resp._response.status_code
        if response_code == 200 or response_code == 202:
            self._log.debug('Image {} was deleted'.format(image_id))
        else:
            self._log.debug('Error deleting {}. Request returned {}'.format(
                image_id, response_code))

    def launch(self, image_id, instance_type=None, user_data=None,
               wait=True, **kwargs):
        self._log.debug(
            'Launching Azure virtual machine: {}'.format(image_id))
        if self.resource_group is None:
            self.resource_group = self.create_resource_group()

        virtual_network = self.create_virtual_network(
            resource_group_name=self.resource_group.name
        )

        subnet = self.create_subnet(
            resource_group_name=self.resource_group.name,
            vnet_name=virtual_network.name
        )

        ip_address = self.create_ip_address(
            resource_group_name=self.resource_group.name
        )

        network_security_group = self.create_network_security_group(
            resource_group_name=self.resource_group.name
        )

        nic = self.create_network_interface_client(
            resource_group_name=self.resource_group.name,
            ip_address_id=ip_address.id,
            subnet_id=subnet.id,
            nsg_id=network_security_group.id
        )

        vm = self.create_virtual_machine(
            resource_group_name=self.resource_group.name,
            nic_id=nic.id,
            user_data=user_data
        )

        return AzureInstance(
            key_pair=self.key_pair,
            instance=vm,
            ip_address=ip_address.ip_address
        )
