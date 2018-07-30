# This file is part of pycloudlib. See LICENSE file for license information.
"""Used to define custom Virtual Private Clouds (VPC)."""

import logging

from botocore.exceptions import ClientError

from pycloudlib.ec2.util import _tag_resource


class VPC:
    """Virtual Private Cloud Class."""

    def __init__(self, resource, name, ipv4_cidr='192.168.1.0/20'):
        """Define and setup a VPC.

        Args:
            resource: EC2 resource object
            name: name of VPC
            ipv4_cidr: CIDR for IPV4 network
        """
        self._log = logging.getLogger(__name__)
        self._resource = resource

        self.name = name
        self.ipv4_cidr = ipv4_cidr

        self.vpc = self._create_vpc()
        self.internet_gateway = self._create_internet_gateway()
        self.subnet = self._create_subnet()
        self.routing_table = self._create_routing_table()
        self.security_group = self._create_security_group()

    @property
    def id(self):
        """ID of the VPC."""
        return self.vpc.id

    def _create_internet_gateway(self):
        """Create Internet Gateway and assign to VPC.

        Returns:
            Internet gateway object

        """
        self._log.debug('creating internet gateway')
        internet_gateway = self._resource.create_internet_gateway()
        internet_gateway.attach_to_vpc(VpcId=self.vpc.id)

        _tag_resource(internet_gateway, self.name)

        return internet_gateway

    def _create_routing_table(self):
        """Update default routing table with internet gateway.

        This sets up internet access between the VPC via the internet gateway
        by configuring routing tables for IPv4 and IPv6.

        Returns:
            Routing table object

        """
        self._log.debug('creating routing table')
        route_table = self.vpc.create_route_table()
        route_table.create_route(
            DestinationCidrBlock='0.0.0.0/0',
            GatewayId=self.internet_gateway.id
        )
        route_table.create_route(
            DestinationIpv6CidrBlock='::/0',
            GatewayId=self.internet_gateway.id
        )
        route_table.associate_with_subnet(SubnetId=self.subnet.id)

        _tag_resource(route_table, self.name)

        return route_table

    def _create_security_group(self):
        """Enable ingress to default VPC security group.

        Returns:
            Security group object

        """
        self._log.debug('creating security group')
        security_group = self.vpc.create_security_group(
            GroupName=self.name,
            Description='pycloudlib created security group'
        )
        security_group.authorize_ingress(
            IpProtocol='-1', FromPort=-1, ToPort=-1, CidrIp='0.0.0.0/0'
        )

        _tag_resource(security_group, self.name)

        return security_group

    def _create_subnet(self):
        """Generate IPv4 and IPv6 subnets for use.

        Returns:
            Create subnet object

        """
        ipv6_cidr = self.vpc.ipv6_cidr_block_association_set[0][
            'Ipv6CidrBlock'][:-2] + '64'

        self._log.debug('creating subnets with following ranges:')
        self._log.debug('ipv4: %s', self.ipv4_cidr)
        self._log.debug('ipv6: %s', ipv6_cidr)
        subnet = self.vpc.create_subnet(
            CidrBlock=self.ipv4_cidr, Ipv6CidrBlock=ipv6_cidr
        )

        # enable public IP on instance launch
        modify_subnet = subnet.meta.client.modify_subnet_attribute
        modify_subnet(
            SubnetId=subnet.id, MapPublicIpOnLaunch={'Value': True}
        )

        _tag_resource(subnet, self.name)

        return subnet

    def _create_vpc(self):
        """Set up AWS EC2 VPC or return existing VPC.

        Returns:
            Create VPN object

        """
        self._log.debug('creating new vpc named %s', self.name)
        try:
            vpc = self._resource.create_vpc(
                CidrBlock=self.ipv4_cidr,
                AmazonProvidedIpv6CidrBlock=True
            )
        except ClientError as error:
            raise RuntimeError(error)

        vpc.wait_until_available()

        _tag_resource(vpc, self.name)

        return vpc

    def delete(self):
        """Terminate all instances and delete an entire VPC."""
        for instance in self.vpc.instances.all():
            self._log.debug('waiting for instance %s termination', instance.id)
            instance.terminate()
            instance.wait_until_terminated()

        if self.security_group:
            self._log.debug(
                'deleting security group %s', self.security_group.id
            )
            self.security_group.delete()

        if self.subnet:
            self._log.debug('deleting subnet %s', self.subnet.id)
            self.subnet.delete()

        if self.routing_table:
            self._log.debug('deleting routing table %s', self.routing_table.id)
            self.routing_table.delete()

        if self.internet_gateway:
            self._log.debug(
                'deleting internet gateway %s', self.internet_gateway.id
            )
            self.internet_gateway.detach_from_vpc(VpcId=self.vpc.id)
            self.internet_gateway.delete()

        if self.vpc:
            self._log.debug('deleting vpc %s', self.vpc.id)
            self.vpc.delete()
