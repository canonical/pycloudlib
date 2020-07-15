# This file is part of pycloudlib. See LICENSE file for license information.
"""Used to define custom Virtual Private Clouds (VPC)."""

import logging

from botocore.exceptions import ClientError

from pycloudlib.ec2.util import _tag_resource


class VPC:
    """Virtual Private Cloud Class."""

    def __init__(self, resource, name, ipv4_cidr='192.168.1.0/20',
                 vpc_id=None):
        """Define and setup a VPC.

        Args:
            resource: EC2 resource object
            name: name of VPC
            ipv4_cidr: CIDR for IPV4 network
            vpc_id: Optional ID of existing VPC object to return
        """
        self._log = logging.getLogger(__name__)

        self.name = name
        if vpc_id is not None:
            self._log.debug(
                'Reusing existing VPC (%s) named %s.', vpc_id, name
            )
            self.vpc = resource.Vpc(vpc_id)
        else:
            self._resource = resource
            self.vpc = self._create_vpc(ipv4_cidr)
            gateway = self._create_internet_gateway()
            subnet = self._create_subnet(ipv4_cidr)
            self._create_routing_table(gateway.id, subnet.id)

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

    def _create_routing_table(self, gateway_id, subnet_id):
        """Update default routing table with internet gateway and subnet.

        This sets up internet access between the VPC via the internet gateway
        by configuring routing tables for IPv4 and IPv6.
        """
        self._log.debug('creating routing table')
        route_table = self.vpc.create_route_table()
        route_table.create_route(
            DestinationCidrBlock='0.0.0.0/0',
            GatewayId=gateway_id
        )
        route_table.create_route(
            DestinationIpv6CidrBlock='::/0',
            GatewayId=gateway_id
        )
        route_table.associate_with_subnet(SubnetId=subnet_id)

        _tag_resource(route_table, self.name)

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

    def _create_subnet(self, ipv4_cidr):
        """Generate IPv4 and IPv6 subnets for use.

        Args:
            ipv4_cidr: CIDR for IPV4 network

        Returns:
            Create subnet object

        """
        ipv6_cidr = self.vpc.ipv6_cidr_block_association_set[0][
            'Ipv6CidrBlock'][:-2] + '64'

        self._log.debug('creating subnets with following ranges:')
        self._log.debug('ipv4: %s', ipv4_cidr)
        self._log.debug('ipv6: %s', ipv6_cidr)
        subnet = self.vpc.create_subnet(
            CidrBlock=ipv4_cidr, Ipv6CidrBlock=ipv6_cidr
        )

        # enable public IP on instance launch
        modify_subnet = subnet.meta.client.modify_subnet_attribute
        modify_subnet(
            SubnetId=subnet.id, MapPublicIpOnLaunch={'Value': True}
        )

        _tag_resource(subnet, self.name)

        return subnet

    def _create_vpc(self, ipv4_cidr):
        """Set up AWS EC2 VPC or return existing VPC.

        Args:
            ipv4_cidr: CIDR for IPV4 network

        Returns:
            Create VPC object

        """
        self._log.debug('creating new vpc named %s', self.name)
        try:
            vpc = self._resource.create_vpc(
                CidrBlock=ipv4_cidr,
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

        for security_group in self.vpc.security_groups.all():
            self._log.debug(
                'deleting security group %s', security_group.id
            )
            security_group.delete()

        for subnet in self.vpc.subnets.all():
            self._log.debug('deleting subnet %s', subnet.id)
            subnet.delete()

        for route_table in self.vpc.route_tables.all():
            self._log.debug('deleting routing table %s', route_table.id)
            route_table.delete()

        for gateway in self.vpc.internet_gateways.all():
            self._log.debug(
                'deleting internet gateway %s', gateway.id
            )
            gateway.detach_from_vpc(VpcId=self.vpc.id)
            gateway.delete()

        if self.vpc:
            self._log.debug('deleting vpc %s', self.vpc.id)
            self.vpc.delete()
