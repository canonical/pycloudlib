# This file is part of pycloudlib. See LICENSE file for license information.
# pylint: disable=C0302
"""Azure Cloud type."""
import base64
import contextlib
import logging
from typing import Dict, List, Optional

from azure.core.exceptions import ResourceNotFoundError
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.network import NetworkManagementClient
from azure.mgmt.resource import ResourceManagementClient

from pycloudlib.azure import security_types, util
from pycloudlib.azure.instance import AzureInstance
from pycloudlib.cloud import BaseCloud, ImageType
from pycloudlib.config import ConfigFile
from pycloudlib.errors import (
    InstanceNotFoundError,
    NetworkNotFoundError,
    PycloudlibError,
    PycloudlibTimeoutError,
)
from pycloudlib.util import get_timestamped_tag, update_nested

UBUNTU_DAILY_IMAGES = {
    "xenial": "Canonical:UbuntuServer:16.04-DAILY-LTS:latest",
    "bionic": "Canonical:UbuntuServer:18.04-DAILY-LTS:latest",
    "focal": "Canonical:0001-com-ubuntu-server-focal-daily:20_04-daily-lts:latest",  # noqa: E501
    "impish": "Canonical:0001-com-ubuntu-server-impish-daily:21_10-daily:latest",  # noqa: E501
    "jammy": "Canonical:0001-com-ubuntu-server-jammy-daily:22_04-daily-lts:latest",  # noqa: E501
    "kinetic": "Canonical:0001-com-ubuntu-server-kinetic-daily:22_10-daily:latest",  # noqa: E501
    "lunar": "Canonical:0001-com-ubuntu-server-lunar-daily:23_04-daily:latest",
    "mantic": "Canonical:0001-com-ubuntu-server-mantic-daily:23_10-daily:latest",  # noqa: E501
}

UBUNTU_DAILY_PRO_IMAGES = {
    "xenial": "Canonical:0001-com-ubuntu-pro-xenial:pro-16_04-lts:latest",
    "bionic": "Canonical:0001-com-ubuntu-pro-bionic:pro-18_04-lts:latest",
    "focal": "Canonical:0001-com-ubuntu-pro-focal:pro-20_04-lts:latest",
    "jammy": "Canonical:0001-com-ubuntu-pro-jammy:pro-22_04-lts:latest",
}

UBUNTU_DAILY_PRO_FIPS_IMAGES = {
    "xenial": "Canonical:0001-com-ubuntu-pro-xenial-fips:pro-fips-16_04-private:latest",  # noqa: E501
    "bionic": "Canonical:0001-com-ubuntu-pro-bionic-fips:pro-fips-18_04:latest",  # noqa: E501
    "focal": "Canonical:0001-com-ubuntu-pro-focal-fips:pro-fips-20_04:latest",
}

UBUNTU_RELEASE_IMAGES = {
    "xenial": "Canonical:UbuntuServer:16.04-LTS:latest",
    "bionic": "Canonical:UbuntuServer:18.04-LTS:latest",
    "focal": "Canonical:0001-com-ubuntu-server-focal:20_04-lts-gen2:latest",
    "impish": "Canonical:0001-com-ubuntu-server-impish:21_10-gen2:latest",
    "jammy": "Canonical:0001-com-ubuntu-server-jammy:22_04-lts-gen2:latest",
}

UBUNTU_CVM_IMAGES = {
    "focal": "Canonical:0001-com-ubuntu-confidential-vm-focal:20_04-lts-cvm:latest",  # noqa: E501
    "jammy": "Canonical:0001-com-ubuntu-confidential-vm-jammy:22_04-lts-cvm:latest",  # noqa: E501
}

logging.getLogger("azure.core.pipeline.policies.http_logging_policy").setLevel(
    logging.WARNING
)


class Azure(BaseCloud):
    """Azure Cloud Class."""

    _type = "azure"

    def __init__(
        self,
        tag: str,
        timestamp_suffix: bool = True,
        config_file: Optional[ConfigFile] = None,
        *,
        client_id: Optional[str] = None,
        client_secret: Optional[str] = None,
        subscription_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
        region: Optional[str] = None,
        username: Optional[str] = None,
    ):
        """Initialize the connection to Azure.

        Azure will try to read user credentials form the /home/$USER/.azure
        folder. However, we can overwrite those credentials with the provided
        id parameters.

        Args:
            tag: string used to name and tag resources with
            timestamp_suffix: bool set True to append a timestamp suffix to the
                tag
            config_file: path to pycloudlib configuration file
            client_id: user's client id
            client_secret: user's client secret access key
            subscription_id: user's subscription id key
            tenant_id: user's tenant id key
            region: The region where the instance will be created
        """
        super().__init__(
            tag,
            timestamp_suffix,
            config_file,
            required_values=[
                client_id,
                client_secret,
                subscription_id,
                tenant_id,
            ],
        )

        self.created_resource_groups: List = []

        self._log.debug("logging into Azure")
        self.location = region or self.config.get("region") or "centralus"
        self.username = username or "ubuntu"

        self.registered_instances: Dict[str, AzureInstance] = {}
        self.registered_images: Dict[str, dict] = {}

        config_dict = {}

        client_id = client_id or self.config.get("client_id")
        if client_id:
            config_dict["clientId"] = client_id

        client_secret = client_secret or self.config.get("client_secret")
        if client_secret:
            config_dict["clientSecret"] = client_secret

        subscription_id = subscription_id or self.config.get("subscription_id")
        if subscription_id:
            config_dict["subscriptionId"] = subscription_id

        tenant_id = tenant_id or self.config.get("tenant_id")
        if tenant_id:
            config_dict["tenantId"] = tenant_id

        self.resource_client = util.get_client(
            ResourceManagementClient, config_dict
        )

        self.network_client = util.get_client(
            NetworkManagementClient, config_dict
        )

        self.compute_client = util.get_client(
            ComputeManagementClient, config_dict
        )

        self.resource_group = self._create_resource_group()
        self.base_tag = tag

    def image_serial(self, image_id):
        """Find the image serial of the latest daily image for a particular release.

        Args:
            image_id: string, Ubuntu image id

        Returns:
            string, serial of latest image

        """
        raise NotImplementedError

    def _create_network_security_group(self, inbound_ports):
        """Create a network security group.

        This method creates a network security groups that allows the user
        to ssh into the machine and execute commands.

        Args:
            inbound_ports: List of strings, optional inbound ports
                           to enable in the instance.

        Returns:
            The network security object created by Azure

        """
        if not inbound_ports:
            inbound_ports = []

        # We need to guarantee that the 22 port is enabled
        # here, otherwise we will not be able to ssh into it
        if "22" not in inbound_ports:
            inbound_ports = ["22"] + inbound_ports

        security_group_name = "{}-sgn".format(self.tag)
        nsg_group = self.network_client.network_security_groups

        self._log.debug("Creating Azure network security group")

        security_rules = []

        # The lower the number, the higher is the priority of the rule.
        # We are assuming here that the SSH rule will be the first item
        # in the list
        priority = 300
        for port in inbound_ports:
            security_rules.append(
                {
                    "name": "port-{}".format(port),
                    "priority": priority,
                    "protocol": "TCP",
                    "access": "Allow",
                    "direction": "Inbound",
                    "sourceAddressPrefix": "*",
                    "sourcePortRange": "*",
                    "destinationAddressPrefix": "*",
                    "destinationPortRange": port,
                }
            )
            priority += 10

        nsg_poller = nsg_group.begin_create_or_update(
            resource_group_name=self.resource_group.name,
            network_security_group_name=security_group_name,
            parameters={
                "location": self.location,
                "security_rules": security_rules,
            },
        )

        return nsg_poller.result()

    def _create_resource_group(self):
        """Create a resource group.

        This method creates an Azure resource group. Every other component that
        we create will be contained into this resource group. This means that
        if we delete this resource group, we delete all resources associated
        with it.

        Returns:
            The resource group created by Azure

        """
        resource_name = "{}-rg".format(self.tag)
        self._log.debug("Creating Azure resource group")

        with contextlib.suppress(ResourceNotFoundError):
            return self.resource_client.resource_groups.get(resource_name)

        resource_group = self.resource_client.resource_groups.create_or_update(
            resource_name,
            {"location": self.location, "tags": {"name": self.tag}},
        )
        self.created_resource_groups.append(resource_group)
        return resource_group

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

        self._log.debug("Creating Azure virtual network")
        network_poller = (
            self.network_client.virtual_networks.begin_create_or_update(
                self.resource_group.name,
                virtual_network_name,
                {
                    "location": self.location,
                    "address_space": {"address_prefixes": address_prefixes},
                    "tags": {"name": self.tag},
                },
            )
        )

        return network_poller.result()

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

        self._log.debug("Creating Azure subnet")
        subnet_poller = self.network_client.subnets.begin_create_or_update(
            self.resource_group.name,
            vnet_name,
            subnet_name,
            {"address_prefix": address_prefix, "tags": {"name": self.tag}},
        )

        return subnet_poller.result()

    def _create_ip_address(self):
        """Create an ip address.

        This method creates an Azure ip address to be used when
        provisioning a network interface

        Returns:
            The ip address created by Azure

        """
        ip_name = "{}-ip".format(self.tag)

        self._log.debug("Creating Azure ip address")
        ip_poller = (
            self.network_client.public_ip_addresses.begin_create_or_update(
                self.resource_group.name,
                ip_name,
                {
                    "location": self.location,
                    "sku": {"name": "Standard"},
                    "public_ip_allocation_method": "Static",
                    "rpublic_ip_address_version": "IPV4",
                    "tags": {"name": self.tag},
                },
            )
        )

        return ip_poller.result()

    def _create_network_interface_client(
        self, ip_address_id, subnet_id, nsg_id, nic_params=None
    ):
        """Create a network interface client.

        This method creates an Azure network interface to be used when
        provisioning a virtual machine

        Args:
            ip_address_id: string, The ip address id
            subnet_id: string, the subnet id
            nsg_id: string, the network security group id
            nic_params: dict, configuration overrides

        Returns:
            The ip address created by Azure

        """
        nic_name = "{}-nic".format(self.tag)
        ip_config_name = "{}-ip-config".format(self.tag)

        nic_config = {
            "location": self.location,
            "ip_configurations": [
                {
                    "name": ip_config_name,
                    "subnet": {"id": subnet_id},
                    "public_ip_address": {"id": ip_address_id},
                }
            ],
            "network_security_group": {"id": nsg_id},
            "tags": {"name": self.tag},
        }

        if nic_params:
            update_nested(nic_config, nic_params)

        self._log.debug("Creating Azure network interface")
        nic_poller = (
            self.network_client.network_interfaces.begin_create_or_update(
                self.resource_group.name, nic_name, nic_config
            )
        )

        return nic_poller.result()

    def _create_vm_parameters(
        self, name, image_id, instance_type, nic_id, user_data
    ):
        """Create the virtual machine parameters to be used for provision.

        Composes the dict that will be used to provision an Azure virtual
        machine. We check if the user has passed user_data and the type of
        image_id we are receiving, which can be snapshots ids or not.

        Args:
            name: string, The name of the virtual machine.
            image_id: string, The identifier of an image.
            instance_type: string, Type of instance to create.
            nic_id: string, The network interface id.
            user_data: string, The user data to be passed to the
                       virtual machine.

        Returns:
            A dict containing the parameters to provision a virtual machine.

        """
        vm_parameters = {
            "location": self.location,
            "hardware_profile": {"vm_size": instance_type},
            "storage_profile": {"image_reference": {}},
            "os_profile": {
                "computer_name": name,
                "admin_username": self.username,
                "linux_configuration": {
                    "ssh": {
                        "public_keys": [
                            {
                                "path": "/home/{}/.ssh/authorized_keys".format(
                                    self.username
                                ),
                                "key_data": self.key_pair.public_key_content,
                            }
                        ]
                    },
                    "disable_password_authentication": True,
                },
            },
            "network_profile": {
                "network_interfaces": [
                    {
                        "id": nic_id,
                    }
                ]
            },
            "tags": {"name": self.tag},
        }

        if user_data:
            # We need to encode the user_data into base64 before sending
            # it to the virtual machine.
            vm_parameters["os_profile"]["custom_data"] = base64.b64encode(
                user_data.encode()
            ).decode()

        vm_parameters["storage_profile"][
            "image_reference"
        ] = util.get_image_reference_params(image_id)

        # We can have pro images from two different sources; marketplaces
        # and snapshots. A snapshot image does not have the necessary metadata
        # encoded in the image_id to create the 'plan' dict. In this case,
        # we get the necessary info from the registered_images dict
        # where we store the required metadata about any snapshot created by
        # pycloudlib.
        registered_image = self.registered_images.get(image_id)
        if util.is_pro_image(image_id, registered_image):
            vm_parameters["plan"] = util.get_plan_params(
                image_id, registered_image
            )

        return vm_parameters

    def _create_virtual_machine(
        self, image_id, instance_type, nic_id, user_data, name, vm_params=None
    ):
        """Create a virtual machine.

        This method provisions an Azure virtual machine for the image_id
        provided by the user.

        Args:
            image_id: string, The image to be used when provisiong
                      a virtual machine.
            instance_type: string, Type of instance to create
            nic_id: string, The network interface to used for this
                    virtual machine.
            user_data: string, user data used by cloud-init when
                       booting the virtual machine.
            name: string, optional name to provide when creating the vm.
            vm_params: dict containing values as vm_params to send to
                    virtual_machines.begin_create_or_update.

        Returns:
            The virtual machine created by Azure

        """
        if not name:
            name = "{}-vm".format(self.tag)
        params = self._create_vm_parameters(
            name, image_id, instance_type, nic_id, user_data
        )
        if vm_params:
            update_nested(params, vm_params)
        self._log.debug("Creating Azure virtual machine: %s", name)
        vm_poller = (
            self.compute_client.virtual_machines.begin_create_or_update(
                self.resource_group.name,
                name,
                params,
            )
        )

        return vm_poller.result()

    def delete_image(self, image_id, **kwargs):
        """Delete an image from Azure.

        Args:
            image_id: string, The id of the image to be deleted
        """
        image_name = util.get_resource_name_from_id(image_id)
        if not image_name:
            return
        resource_group_name = util.get_resource_group_name_from_id(image_id)

        delete_poller = self.compute_client.images.begin_delete(
            resource_group_name=resource_group_name, image_name=image_name
        )

        delete_poller.wait()

        if delete_poller.status() == "Succeeded":
            if image_id in self.registered_images:
                del self.registered_images[image_id]
                self._log.debug("Image %s was deleted", image_id)
        else:
            self._log.debug(
                "Error deleting %s. Status: %d",
                image_id,
                delete_poller.status(),
            )

    def _get_image(self, release, image_map):
        image_id = image_map.get(release)
        if image_id is None:
            msg = "No Ubuntu image found for {}. Expected one of: {}"
            raise ValueError(msg.format(release, " ".join(image_map.keys())))

        return image_id

    def released_image(self, release):
        """Get the released image.

        Args:
            release: string, Ubuntu release to look for
        Returns:
            string, id of latest image

        """
        self._log.debug("finding release Ubuntu image for %s", release)
        return self._get_image(release, UBUNTU_RELEASE_IMAGES)

    def confidential_vm_image(self, release):
        """Get the confidential computing vm image.

        Args:
            release: string, Ubuntu release to look for
        Returns:
            string, id of latest image

        """
        self._log.debug("finding confidential vm Ubuntu image for %s", release)
        return self._get_image(release, UBUNTU_CVM_IMAGES)

    def _get_images_dict(self, image_type: ImageType):
        if image_type == ImageType.GENERIC:
            return UBUNTU_DAILY_IMAGES

        if image_type == ImageType.PRO:
            return UBUNTU_DAILY_PRO_IMAGES

        if image_type == ImageType.PRO_FIPS:
            return UBUNTU_DAILY_PRO_FIPS_IMAGES

        raise ValueError("Invalid image_type")

    def daily_image(
        self,
        release: str,
        *,
        image_type: ImageType = ImageType.GENERIC,
        **kwargs,
    ):
        """Find the image info for the latest daily image for a given release.

        Args:
            release: string, Ubuntu release to look for.

        Returns:
            A string representing an Ubuntu image

        """
        self._log.debug("finding daily Ubuntu image for %s", release)
        return self._get_image(release, self._get_images_dict(image_type))

    def _check_for_network_interfaces(self):
        """
        Check for existing networking interfaces in instance resource group.

        Check if we already have a network interface that is not attached to
        any virtual machines in the instance resource group. If we have one
        of those reoources, we just return it.

        Returns:
            An Azure network interface resource

        """
        all_nics = self.network_client.network_interfaces.list(
            resource_group_name=self.resource_group.name
        )

        for nic in all_nics:
            if nic.virtual_machine is None:
                return nic

        return None

    def launch(
        self,
        image_id,
        instance_type="Standard_DS1_v2",
        user_data=None,
        name=None,
        inbound_ports=None,
        username: Optional[str] = None,
        security_type=security_types.AzureSecurityType.STANDARD,
        **kwargs,
    ):
        """Launch virtual machine on Azure.

        Args:
            image_id: string, Ubuntu image to use
            user_data: string, user-data to pass to virtual machine
            name: string, optional name to give the vm when launching.
                  Default results in a name of <tag>-vm
            inbound_ports: List of strings, optional inbound ports
                           to enable in the instance.
            security_type: AzureSecurityType, security on vm image.
                           Defaults to STANDARD
            username: username to use when connecting via SSH
            kwargs:
                - vm_params: dict to override configuration for
                virtual_machines.begin_create_or_update
                - nic_params: dict to override configuration for
                network_client.network_interfaces.begin_create_or_update
                - security_type_params: dict to configure security_types

        Returns:
            Azure Instance object
        Raises: ValueError on invalid image_id
        """
        # pylint: disable-msg=too-many-locals
        if not image_id:
            raise ValueError(
                f"{self._type} launch requires image_id param."
                f" Found: {image_id}"
            )
        self._log.debug("Launching Azure virtual machine: %s", image_id)

        # For every new launch, we need to update the tag, since
        # we are using it as a base for the name of all the
        # resources we are creating.
        self.tag = get_timestamped_tag(self.base_tag)

        if self.resource_group is None:
            self.resource_group = self._create_resource_group()

        # We will not reuse existing network interfaces if we need to customize
        # it to enable more ports. The rationale for is that we want to reuse
        # those resources only if they are generic enough
        nic = None
        if not inbound_ports:
            # Check if we already have an existing network interface that is
            # not attached to a virtual machine. If we have, we will just
            # use it
            nic = self._check_for_network_interfaces()

        if nic is None:
            self._log.debug(
                "Could not find a network interface. Creating one now"
            )
            virtual_network = self._create_virtual_network()
            self._log.debug(
                "Created virtual network with name: %s", virtual_network.name
            )

            subnet = self._create_subnet(vnet_name=virtual_network.name)
            self._log.debug("Created subnet with name: %s", subnet.name)

            ip_address = self._create_ip_address()
            ip_address_str = ip_address.ip_address
            self._log.debug(
                "Created ip address with name: %s", ip_address.name
            )

            network_security_group = self._create_network_security_group(
                inbound_ports=inbound_ports
            )
            self._log.debug(
                "Created network security group with name: %s",
                network_security_group.name,
            )

            nic = self._create_network_interface_client(
                ip_address_id=ip_address.id,
                subnet_id=subnet.id,
                nsg_id=network_security_group.id,
                nic_params=kwargs.get("nic_params", None),
            )

            self._log.debug(
                "Created network interface with name: %s", nic.name
            )
        else:
            ip_address_str = self._retrieve_ip_from_network_interface(nic=nic)
            self._log.debug(
                "Found network interface: %s. Reusing it", nic.name
            )

        vm_params = kwargs.get("vm_params", {})
        os_disk_encryption = kwargs.get("security_type_params", {}).get(
            "os_disk_encryption", None
        )
        security_types.configure_security_types_vm_params(
            security_type, vm_params, os_disk_encryption
        )

        vm = self._create_virtual_machine(
            image_id=image_id,
            instance_type=instance_type,
            nic_id=nic.id,
            user_data=user_data,
            name=name,
            vm_params=vm_params,
        )

        instance_info = {
            "vm": vm,
            "ip_address": ip_address_str,
            "rg_name": self.resource_group.name,
        }

        instance = AzureInstance(
            key_pair=self.key_pair,
            client=self.compute_client,
            instance=instance_info,
            username=username,
        )

        self.created_instances.append(instance)

        self.registered_instances[vm.name] = instance
        return instance

    def _create_ssh_resource(self, key_name):
        """Create a ssh resource.

        This method creates an Azure ssh resource to be associated
        with a resource group.

        Args:
            key_name: string, The name of the ssh resource.

        """
        self.compute_client.ssh_public_keys.create(
            self.resource_group.name,
            key_name,
            parameters={"location": self.location, "tags": {"name": self.tag}},
        )

    def create_key_pair(self, key_name):
        """Create a pair of ssh keys.

        This method creates an a pair of ssh keys in
        the class resource group.

        Args:
            key_name: string, The name of the ssh resource.

        """
        self._create_ssh_resource(key_name)

        ssh_call = self.compute_client.ssh_public_keys.generate_key_pair(
            resource_group_name=self.resource_group.name,
            ssh_public_key_name=key_name,
        )

        # Azure's SDK returns multi-line DOS format for pubkeys.
        # OpenSSH doesn't like this format and ignores it resulting in
        # Unauthorized key errors. Issue: #88
        return ssh_call.public_key.replace("\r\n", ""), ssh_call.private_key

    def list_keys(self):
        """List all ssh keys in the class resource group."""
        ssh_public_keys = self.compute_client.ssh_public_keys

        return [
            ssh.name
            for ssh in ssh_public_keys.list_by_resource_group(
                self.resource_group.name
            )
        ]

    def delete_key(self, key_name):
        """Delete a ssh key from the class resource group.

        Args:
            key_name: string, The name of the ssh resource.

        """
        ssh_public_keys = self.compute_client.ssh_public_keys
        ssh_public_keys.delete(
            resource_group_name=self.resource_group.name,
            ssh_public_key_name=key_name,
        )

    def use_key(self, public_key_path, private_key_path=None, name=None):
        """Use an existing already uploaded key.

        Args:
            public_key_path: path to the public key to upload
            private_key_path: path to the private key to upload
            name: name to reference key by

        """
        if not name:
            name = self.tag
        super().use_key(public_key_path, private_key_path, name)

    def _get_instances(self):
        """Return an iterable of Azure instances related to a subscription id.

        Returns:
            An list of azure virtual machine associated with the subscription
            id

        """
        return self.compute_client.virtual_machines.list_all()

    def _retrieve_ip_from_network_interface(self, nic):
        """Retrieve the ip address associated with a network interface.

        Args:
            nic: An Azure network interface resource

        Return:
            A string representing the network interface ip address

        """
        ip_address_id = nic.ip_configurations[0].public_ip_address.id
        all_ips = self.network_client.public_ip_addresses.list_all()

        for ip_address in all_ips:
            if ip_address.id == ip_address_id:
                return ip_address.ip_address

        raise PycloudlibError(
            f"""
            Error locationg the ip address: {ip_address_id}.
            This ip address was not found in this subscription.
            """
        )

    def _retrive_instance_ip(self, instance):
        """Retrieve public ip address of instance.

        Args:
            instance: An Azure Virtual Machine object

        Returns:
            A string represeting the instance ip_address

        """
        # Right now, we are only supporting getting the ip address for
        # virtual machines with only one network profile attached to it
        nic_id = instance.network_profile.network_interfaces[0].id
        all_nics = self.network_client.network_interfaces.list_all()

        instance_nic = None
        for nic in all_nics:
            if nic.id == nic_id:
                instance_nic = nic

        if instance_nic is None:
            raise NetworkNotFoundError(resource_id=nic_id)

        return self._retrieve_ip_from_network_interface(nic=instance_nic)

    def get_instance(
        self,
        instance_id,
        search_all=False,
        *,
        username: Optional[str] = None,
        **kwargs,
    ):
        """Get an instance by id.

        Args:
            instance_id: string, The instance name to search by
            search_all: boolean, Flag that indicates that if we should search
                for the instance in the entire reach of the
                subsctription id. If false, we will search only
                in the resource group created by this instance.
            username: username to use when connecting via SSH
            **kwargs: dictionary of other arguments to be used by this
                method. Currently unused but provided for base
                class compatibility.

        Returns:
            An instance object to use to manipulate the instance further.

        """
        if search_all:
            all_instances = self._get_instances()

            for instance in all_instances:
                if instance.name == instance_id:
                    ip_address = self._retrive_instance_ip(instance)
                    resource_group_name = util.get_resource_group_name_from_id(
                        instance.id
                    )

                    instance_info = {
                        "vm": instance,
                        "ip_address": ip_address,
                        "rg_name": resource_group_name,
                    }
                    azure_instance = AzureInstance(
                        key_pair=self.key_pair,
                        client=self.compute_client,
                        instance=instance_info,
                        username=username,
                    )

                    self.registered_instances[instance.name] = azure_instance
                    return azure_instance

            raise InstanceNotFoundError(instance_id)

        if instance_id in self.registered_instances:
            instance = self.registered_instances[instance_id]

            if instance.status == "deleted":
                raise PycloudlibError(
                    f"The image {instance_id} was already deleted"
                )

            return instance

        raise InstanceNotFoundError(resource_id=instance_id)

    def snapshot(
        self, instance, clean=True, delete_provisioned_user=True, **kwargs
    ):
        """Snapshot an instance and generate an image from it.

        Args:
            instance: Instance to snapshot
            clean: Run instance clean method before taking snapshot
            delete_provisioned_user: Deletes the last provisioned user
            kwargs: Other named arguments specific to this implementation

        Returns:
            An image id string

        """
        if clean:
            instance.clean()
        user = "+user" if delete_provisioned_user else ""
        instance.execute("sudo waagent -deprovision{} -force".format(user))
        instance.shutdown(wait=True)
        instance.generalize()

        self._log.debug("creating custom image from instance %s", instance.id)

        image_poller = self.compute_client.images.begin_create_or_update(
            resource_group_name=self.resource_group.name,
            image_name="%s-%s" % (self.tag, "image"),
            parameters={
                "location": self.location,
                "source_virtual_machine": {"id": instance.id},
                "tags": {"name": self.tag, "src-image-id": instance.image_id},
            },
        )

        image = image_poller.result()

        image_id = image.id
        image_name = image.name

        self.created_images.append(image_id)

        self.registered_images[image_id] = {
            "name": image_name,
            "sku": instance.sku,
            "offer": instance.offer,
        }

        return image_id

    def delete_resource_group(self, resource_group_name: Optional[str] = None):
        """Delete a resource group.

        If no resource group is provided, delete self.resource_group
        """
        if resource_group_name is None and self.resource_group:
            resource_group_name = self.resource_group.name
            self.resource_group = None
        if resource_group_name:
            with contextlib.suppress(ResourceNotFoundError):
                poller = self.resource_client.resource_groups.begin_delete(
                    resource_group_name=resource_group_name
                )
                poller.wait(timeout=300)
                if not poller.done():
                    raise PycloudlibTimeoutError(
                        "Resource not deleted after 300 seconds"
                    )

    # pylint: disable=broad-except
    def clean(self) -> List[Exception]:
        """Cleanup ALL artifacts associated with this Cloud instance.

        This includes all instances, snapshots, resources, etc.
        To ensure cleanup isn't interrupted, any exceptions raised during
        cleanup operations will be collected and returned.
        """
        exceptions = super().clean()
        for resource_group in self.created_resource_groups:
            try:
                self.delete_resource_group(resource_group.name)
            except Exception as e:
                exceptions.append(e)
        return exceptions
