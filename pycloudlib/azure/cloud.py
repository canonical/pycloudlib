# This file is part of pycloudlib. See LICENSE file for license information.
"""Azure Cloud type."""
import base64

from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.compute import ComputeManagementClient
from azure.common.client_factory import (get_client_from_cli_profile,
                                         get_client_from_json_dict)
from knack.util import CLIError

from pycloudlib.cloud import BaseCloud
from pycloudlib.azure.instance import AzureInstance
from pycloudlib.key import KeyPair


class Azure(BaseCloud):
    """Azure Cloud Class."""

    _type = 'azure'

    UBUNTU_RELEASE = {
        "trusty": "Canonical:UbuntuServer:14.04.0-LTS",
        "xenial": "Canonical:UbuntuServer:16.04-DAILY-LTS",
        "bionic": "Canonical:UbuntuServer:18.04-DAILY-LTS",
        "focal": "Canonical:0001-com-ubuntu-server-focal-daily:20_04-daily-lts"
    }

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
        self.username = "ubuntu"

        self.registered_vms = {}
        self.registered_images = {}

        config_dict = {}

        if client_id:
            config_dict["client_id"] = client_id

        if client_secret_id:
            config_dict["client_secret"] = client_secret_id

        if subscription_id:
            config_dict["subscription_id"] = subscription_id

        if tenant_id:
            config_dict["tenant_id"] = tenant_id

        self.resource_client = self.get_client(
            ResourceManagementClient, config_dict
        )

        self.network_client = self.get_client(
            NetworkManagementClient, config_dict
        )

        self.compute_client = self.get_client(
            ComputeManagementClient, config_dict
        )

        self.resource_group = self._create_resource_group()
        self.ssh_resource = None
        self.base_tag = tag

    def get_client(self, resource, config_dict):
        """Get azure client based on the give resource.

        This method will first verify if we can get the client
        by using the information provided on the login account
        of the user machine. If the user is not logged into Azure,
        we will try to get the client from the ids given by the
        user to this class.

        Args:
            resource: Azure Resource, An Azure resource that we want to get
                      a client for.
            config_dict: dict, Id parameters passed by the user to this class.

        Returns:
            The client for the resource passed as parameter.

        """
        try:
            client = get_client_from_cli_profile(resource)
        except CLIError:
            client = None

        if client is None:
            parameters = {
                "subscriptionId": config_dict.get("subscription_id"),
                "tenantId": config_dict.get("tenant_id"),
                "clientId": config_dict.get("client_id"),
                "clientSecret": config_dict.get("client_secret"),
                "activeDirectoryEndpointUrl":
                    "https://login.microsoftonline.com",
                "resourceManagerEndpointUrl": "https://management.azure.com/",
                "activeDirectoryGraphResourceId":
                    "https://graph.windows.net/",
                "sqlManagementEndpointUrl":
                    "https://management.core.windows.net:8443/",
                "galleryEndpointUrl": "https://gallery.azure.com/",
                "managementEndpointUrl":
                    "https://management.core.windows.net/"
            }

            client = get_client_from_json_dict(
                resource,
                parameters
            )

        return client

    def _create_network_security_group(self):
        """Create a network security group.

        This method creates a network security groups that allows the user
        to ssh into the machine and execute commands.

        Returns:
            The network security object created by Azure

        """
        security_group_name = "{}-sgn".format(self.tag)
        nsg_group = self.network_client.network_security_groups

        self._log.debug('Creating Azure network security group')
        nsg_call = nsg_group.create_or_update(
            resource_group_name=self.resource_group.name,
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

    def _create_resource_group(self):
        """Create a resource group.

        This method creates an Azure resource group. Every other componet that
        we create will be contained into this resource group. This means that
        if we delete this resource group, we delete all resources associated
        with it.

        Returns:
            The resource group created by Azure

        """
        resource_name = "{}-rg".format(self.tag)
        self._log.debug('Creating Azure resource group')

        return self.resource_client.resource_groups.create_or_update(
            resource_name,
            {
                "location": self.location
            }
        )

    def _create_virtual_network(self, address_prefixes=None):
        """Create a virtual network.

        This method creates an Azure virtual network to be used
        when provisioning a subnet.

        Args:
            address_prefixes:  list of strings, A list of address prefixes
                               to be used in this virtual network.
        Returns:
            The virtual network created by Azure

        """
        if address_prefixes is None:
            address_prefixes = ["10.0.0.0/16"]

        virtual_network_name = "{}-vnet".format(self.tag)

        self._log.debug('Creating Azure virtual network')
        network_call = self.network_client.virtual_networks.create_or_update(
            self.resource_group.name,
            virtual_network_name,
            {
                "location": self.location,
                "address_space": {
                    "address_prefixes": address_prefixes
                }
            }
        )

        return network_call.result()

    def _create_subnet(self, vnet_name, address_prefix="10.0.0.0/24"):
        """Create a subnet.

        This method creates an Azure subnet to be used when
        provisioning a network interface.

        Args:
            address_prefix: string, An address prefix to be used for
                            this subnet.

        Returns:
            The subnet created by Azure

        """
        subnet_name = "{}-subnet".format(self.tag)

        self._log.debug('Creating Azure subnet')
        subnet_call = self.network_client.subnets.create_or_update(
            self.resource_group.name,
            vnet_name,
            subnet_name,
            {"address_prefix": address_prefix}
        )

        return subnet_call.result()

    def _create_ip_address(self):
        """Create an ip address.

        This method creates an Azure ip address to be used when
        provisioning a network interface

        Returns:
            The ip address created by Azure

        """
        ip_name = "{}-ip".format(self.tag)

        self._log.debug('Creating Azure ip address')
        ip_call = self.network_client.public_ip_addresses.create_or_update(
            self.resource_group.name,
            ip_name,
            {
                "location": self.location,
                "sku": {"name": "Standard"},
                "public_ip_allocation_method": "Static",
                "rpublic_ip_address_version": "IPV4"
            }
        )

        return ip_call.result()

    def _create_network_interface_client(self, ip_address_id, subnet_id,
                                         nsg_id):
        """Create a network interface client.

        This method creates an Azure network interface to be used when
        provisioning a virtual machine

        Args:
            ip_address_id: string, The ip address id
            subnet_id: string, the subnet id
            nsg_id: string, the network security group id

        Returns:
            The ip address created by Azure

        """
        nic_name = "{}-nic".format(self.tag)
        ip_config_name = "{}-ip-config".format(self.tag)

        self._log.debug('Creating Azure network interface')
        nic_call = self.network_client.network_interfaces.create_or_update(
            self.resource_group.name,
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

    def _get_offer_from_image_id(self, image_id):
        """Extract offer from an image_id string.

        The image_id is expected to be a string in the following
        format: Canonical:UbuntuServer:19.10-DAILY. The offer is
        the first name after the first ':' symbol.

        Args:
            image_id: string, The image id

        Returns
            A string representing the image offer

        """
        return image_id.split(":")[1]

    def _get_sku_from_image_id(self, image_id):
        """Extract sku from an image_id string.

        The image_id is expected to be a string in the following
        format: Canonical:UbuntuServer:19.10-DAILY. The sku is
        the name after the second ':' symbol.

        Args:
            image_id: string, The image id

        Returns
            A string representing the image offer

        """
        return image_id.split(":")[-1]

    def _create_vm_parameters(self, vm_name, image_id, nic_id, user_data):
        """Create the virtual machine parameters to be used for provision.

        Composes the dict that will be used to provision an Azure virtual
        machine. We check if the user has passed user_data and the type of
        image_id we are receiving, which can be snapshots ids or not.

        Args:
            vm_name: string, The name of the virtual machine.
            image_id: string, The identifier of an image.
            nic_id: string, The network interface id.
            user_data: string, The user data to be passed to the
                       virtual machine.

        Returns:
            A dict containing the parameters to provision a virtual machine.

        """
        vm_parameters = {
            "location": self.location,
            "hardware_profile": {
                "vm_size": "Standard_DS1_v2"
            },
            "storage_profile": {
                "image_reference": {}
            },
            "os_profile": {
                "computer_name": vm_name,
                "admin_username": self.username,
                "linux_configuration": {
                    "ssh": {
                        "public_keys": [
                            {
                                "path": "/home/{}/.ssh/authorized_keys".format(
                                    self.username),
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
            """
            We need to encode the user_data into base64 before sending
            it to the virtual machine."""
            vm_parameters["os_profile"]["custom_data"] = base64.b64encode(
                user_data.encode()).decode()

        """
        We have two types of images, base images that are found on
        Azure marketplace and custom images based on other virtual
        machines. For marketplace images, we have an expected
        format: Canonical:UbuntuServer:19.10-DAILY. Here we have
        the published, offer and sku information. However, the
        snapshot images are just an id, similar to any other
        resource id that we find in Azure. Because of that
        difference, we need to treat those image types
        differently.
        """
        if image_id.startswith('Canonical'):
            vm_parameters["storage_profile"]["image_reference"] = {
                "publisher": 'Canonical',
                "offer": self._get_offer_from_image_id(image_id),
                "sku": self._get_sku_from_image_id(image_id),
                "version": "latest"
            }
        else:
            vm_parameters["storage_profile"]["image_reference"] = {
                "id": image_id
            }

        return vm_parameters

    def _create_virtual_machine(self, image_id, nic_id, user_data):
        """Create a virtual machine.

        This method provisions an Azure virtual machine for the image_id
        provided by the user.

        Args:
            image_id: string, The image to be used when provisiong
                      a virtual machine.
            nic_id: string, The network interface to used for this
                            virtual machine.
            user_data: string, user data used by cloud-init when
                       booting the virtual machine.
        Returns:
            The virtual machine created by Azure

        """
        vm_name = "{}-vm".format(self.tag)

        self._log.debug('Creating Azure virtual machine')
        vm_call = self.compute_client.virtual_machines.create_or_update(
            self.resource_group.name,
            vm_name,
            self._create_vm_parameters(vm_name, image_id, nic_id, user_data)
        )

        return vm_call.result()

    def delete_image(self, image_id):
        """Delete an image from Azure.

        Args:
            image_id: string, The id of the image to be deleted
        """
        self._log.debug(
            'Deleting Azure image: {}'.format(image_id))
        vm_name = self.registered_images.get(image_id, {}).get("name")

        delete_vm_resp = self.compute_client.images.delete(
            resource_group_name=self.resource_group.name,
            image_name=vm_name
        )

        response_code = delete_vm_resp._response.status_code
        if response_code == 200 or response_code == 202:
            self._log.debug('Image {} was deleted'.format(image_id))
            del self.registered_images[image_id]
        else:
            self._log.debug('Error deleting {}. Request returned {}'.format(
                image_id, response_code))

    def daily_image(self, release):
        """Find the iamge info for the latest daily image for a given release.

        Args:
            release: string, Ubuntu release to look for.

        Returns:
            A string representing an Ubuntu image

        """
        self._log.debug('finding daily Ubuntu image for %s', release)
        release = self.UBUNTU_RELEASE.get(release)

        if release is None:
            raise Exception(
                "No release image found for {}".format(self.release))

        return release

    def launch(self, image_id, user_data=None, **kwargs):
        """Launch virtual machine on Azure.

        Args:
            image_id: string, Ubuntu image to use
            user_data: string, user-data to pass to virtual machine
            kwargs: other named arguments to add to instance JSON

        Returns:
            Azure Instance object

        """
        self._log.debug(
            'Launching Azure virtual machine: {}'.format(image_id))

        self.tag = self.set_tag(self.base_tag)

        virtual_network = self._create_virtual_network()

        subnet = self._create_subnet(vnet_name=virtual_network.name)

        ip_address = self._create_ip_address()

        network_security_group = self._create_network_security_group()

        nic = self._create_network_interface_client(
            ip_address_id=ip_address.id,
            subnet_id=subnet.id,
            nsg_id=network_security_group.id
        )

        vm = self._create_virtual_machine(
            image_id=image_id,
            nic_id=nic.id,
            user_data=user_data
        )

        self.registered_vms[vm.name] = {
            "vm": vm,
            "ip_address": ip_address.ip_address,
            "rg_name": self.resource_group.name
        }

        return AzureInstance(
            client=self.compute_client,
            key_pair=self.key_pair,
            instance=self.registered_vms[vm.name]
        )

    def _create_ssh_resource(self, key_name):
        """Create a ssh resource.

        This method creates an Azure ssh resource to be associated
        with a resource group.

        Args:
            key_name: string, The name of the ssh resource.

        """
        ssh_resource = self.compute_client.ssh_public_keys.create(
            self.resource_group.name,
            key_name,
            parameters={
                "location": self.location
            }
        )
        self.ssh_resource = ssh_resource

    def create_key_pair(self, key_name):
        """Create a pair of ssh keys.

        This method creates an a pair of ssh keys in
        the class resource group.

        Args:
            key_name: string, The name of the ssh resource.

        """
        if self.ssh_resource is None:
            self._create_ssh_resource(key_name)

        ssh_call = self.compute_client.ssh_public_keys.generate_key_pair(
            resource_group_name=self.resource_group.name,
            ssh_public_key_name=self.ssh_resource.name)

        return ssh_call.public_key, ssh_call.private_key

    def list_keys(self):
        """List all ssh keys in the class resource group."""
        ssh_public_keys = self.compute_client.ssh_public_keys

        return [
            ssh.name
            for ssh in ssh_public_keys.list_by_resource_group(
                self.resource_group.name)
        ]

    def delete_key(self, key_name):
        """Delete a ssh key from the class resource group.

        Args:
            key_name: string, The name of the ssh resource.

        """
        ssh_public_keys = self.compute_client.ssh_public_keys
        ssh_public_keys.delete(
            resource_group_name=self.resource_group.name,
            ssh_public_key_name=self.ssh_resource.name
        )

        self.ssh_resource = None

    def use_key(self, public_key_path, private_key_path=None, name=None):
        """Use an existing already uploaded key.

        Args:
            public_key_path: path to the public key to upload
            private_key_path: path to the private key to upload
            name: name to reference key by

        """
        if not name:
            name = self.tag

        self._log.debug('using SSH key %s', name)
        self.key_pair = KeyPair(public_key_path, private_key_path, name)

    def get_instance(self, instance_id):
        """Get an instance by id.

        Args:
            instance_id: the instance name to search by

        Returns:
            An instance object to use to manipulate the instance further.

        """
        if instance_id in self.vm_info:
            return AzureInstance(
                client=self.compute_client,
                key_pair=self.key_pair,
                instance=self.vm_info[instance_id],
            )
        else:
            raise Exception(
                "Could not find {}".format(instance_id)
            )

    def snapshot(self, instance):
        """Snapshot an instance and generate an image from it.

        Args:
            instance: Instance to snapshot
            clean: run instance clean method before taking snapshot

        Returns:
            An image id string

        """
        instance.execute("sudo waagent -deprovision+user -force")
        instance.shutdown(wait=True)
        instance.generalize()

        self._log.debug(
            'creating custom image from instance %s', instance.id
        )

        response = self.compute_client.images.create_or_update(
            resource_group_name=self.resource_group.name,
            image_name='%s-%s' % (self.tag, "image"),
            parameters={
                "location": self.location,
                "source_virtual_machine": {
                    "id": instance.id
                }
            }
        )

        image = response.result()

        image_id = image.id
        image_name = image.name

        self.registered_images[image_id] = {
            "id": image_id,
            "name": image_name
        }

        return image_id
