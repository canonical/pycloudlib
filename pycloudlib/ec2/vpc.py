# This file is part of pycloudlib. See LICENSE file for license information.
"""Used to define custom Virtual Private Clouds (VPC)."""

import ipaddress
import logging

from botocore.exceptions import ClientError

from pycloudlib.ec2.util import _tag_resource
from pycloudlib.errors import CloudError

logger = logging.getLogger(__name__)


class VPC:
    """Virtual Private Cloud class proxy for AWS VPC resource."""

    def __init__(self, vpc):
        """Create a VPC proxy instance for an AWS VPC resource.

        Args:
            vpc_id: Optional ID of existing VPC object to return
        """
        self.vpc = vpc

    @classmethod
    def create(cls, resource, name, ipv4_cidr="192.168.1.0/20"):
        """Create a pycloudlib.ec2.VPC proxy for an AWS VPC resource.

        Args:
            resource: EC2 resource client
            name: String for the name or tag of the VPC
            ipv4_cidr: String of the CIDR for IPV4 subnet to associate with the
                VPC.

        Returns:
            pycloudlib.ec2.VPC instance

        """
        logger.debug("Creating VPC named (%s)", name)
        vpc = cls._create_vpc(
            resource=resource, name=name, ipv4_cidr=ipv4_cidr
        )
        vpc.wait_until_available()
        vpc.reload()
        gateway = cls._create_internet_gateway(resource, vpc)
        subnet = cls._create_subnet(vpc, ipv4_cidr)
        route_table = cls._create_routing_table(vpc, gateway.id, subnet.id)
        sec_group = cls._create_security_group(vpc, name)
        for aws_resource in (vpc, gateway, subnet, route_table, sec_group):
            _tag_resource(aws_resource, name)
        logger.debug("Created VPC (%s) named (%s)", vpc.id, name)
        return cls(vpc)

    @classmethod
    def from_existing(cls, resource, vpc_id):
        """Wrap an existing boto3 EC2 VPC resource given the vpc_id.

        Args:
            resource: EC2 resource client
            vpc_id: String for an existing VPC id.

        Returns:
            pycloudlib.ec2.VPC instance

        """
        logger.debug("Reusing existing VPC (%s)", vpc_id)
        vpc = resource.Vpc(vpc_id)
        return cls(vpc)

    @property
    def id(self):
        """ID of the VPC."""
        return self.vpc.id

    @property
    def name(self):
        """Name of the VPC from tags."""
        for tag in self.vpc.tags:
            if tag["Key"] == "Name":
                return tag["Value"]
        return "NO-TAG-NAME-PRESENT"

    @classmethod
    def _create_internet_gateway(cls, resource, vpc):
        """Create Internet Gateway and assign to VPC.

        Returns:
            Internet gateway object

        """
        logger.debug("creating internet gateway for vpc %s", vpc.id)
        internet_gateway = resource.create_internet_gateway()
        internet_gateway.attach_to_vpc(VpcId=vpc.id)

        return internet_gateway

    @classmethod
    def _create_routing_table(cls, vpc, gateway_id, subnet_id):
        """Update default routing table with internet gateway and subnet.

        This sets up internet access between the VPC via the internet gateway
        by configuring routing tables for IPv4 and IPv6.
        """
        logger.debug("creating routing table")
        route_table = vpc.create_route_table()
        route_table.create_route(
            DestinationCidrBlock="0.0.0.0/0", GatewayId=gateway_id
        )
        route_table.create_route(
            DestinationIpv6CidrBlock="::/0", GatewayId=gateway_id
        )
        route_table.associate_with_subnet(SubnetId=subnet_id)
        return route_table

    @classmethod
    def _create_security_group(cls, vpc, name):
        """Enable ingress to default VPC security group.

        Returns:
            Security group object

        """
        logger.debug("creating security group")
        security_group = vpc.create_security_group(
            GroupName=name, Description="pycloudlib created security group"
        )
        security_group.authorize_ingress(
            IpProtocol="-1", FromPort=-1, ToPort=-1, CidrIp="0.0.0.0/0"
        )

        return security_group

    @classmethod
    def _create_subnet(cls, vpc, ipv4_cidr):
        """Generate IPv4 and IPv6 subnets for use in an AWS VPC resource.

        Args:
            vpc: AWS VPC resource to which the created subnet is associated.
            ipv4_cidr: CIDR for IPV4 network

        Returns:
            Create subnet object

        """
        ipv6_cidr = vpc.ipv6_cidr_block_association_set[0]["Ipv6CidrBlock"]
        kwargs = {"CidrBlock": ipv4_cidr}
        try:
            ipaddress.IPv6Network(ipv6_cidr)
            kwargs["Ipv6CidrBlock"] = ipv6_cidr[:-2] + "64"
        except ValueError as e:
            logger.warning(
                "Skipping IPv6 association on vpc."
                " Could not understand Ipv6CidrBlock: [%s]: %s",
                ipv6_cidr,
                str(e),
            )
        logger.debug("creating subnets with following ranges:")
        for key, value in kwargs.items():
            logger.debug("%s: %s", key, value)
        subnet = vpc.create_subnet(**kwargs)

        # enable public IP on instance launch
        modify_subnet = subnet.meta.client.modify_subnet_attribute
        modify_subnet(SubnetId=subnet.id, MapPublicIpOnLaunch={"Value": True})

        return subnet

    @classmethod
    def _create_vpc(cls, resource, name, ipv4_cidr):
        """Set up AWS EC2 VPC or return existing VPC.

        Args:
            resource: boto 3 resource client
            name: the name/tag of the VPC to create
            ipv4_cidr: CIDR for IPV4 network

        Returns:
            VPC resource created from AWS cli

        """
        logger.debug(
            "creating new vpc named %s with subnet %s", name, ipv4_cidr
        )
        try:
            vpc = resource.create_vpc(
                CidrBlock=ipv4_cidr, AmazonProvidedIpv6CidrBlock=True
            )
        except ClientError as error:
            raise CloudError(error) from error

        vpc.wait_until_available()

        return vpc

    def delete(self):
        """Terminate all associated instances and delete an entire VPC."""
        for instance in self.vpc.instances.all():
            logger.debug("waiting for instance %s termination", instance.id)
            instance.terminate()
            instance.wait_until_terminated()

        for security_group in self.vpc.security_groups.all():
            logger.debug("deleting security group %s", security_group.id)
            security_group.delete()

        for subnet in self.vpc.subnets.all():
            logger.debug("deleting subnet %s", subnet.id)
            subnet.delete()

        for route_table in self.vpc.route_tables.all():
            logger.debug("deleting routing table %s", route_table.id)
            route_table.delete()

        for gateway in self.vpc.internet_gateways.all():
            logger.debug("deleting internet gateway %s", gateway.id)
            gateway.detach_from_vpc(VpcId=self.vpc.id)
            gateway.delete()

        if self.vpc:
            logger.debug("deleting vpc %s", self.vpc.id)
            self.vpc.delete()
