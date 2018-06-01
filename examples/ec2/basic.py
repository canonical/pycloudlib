#!/usr/bin/python3
# This file is part of pycloudlib. See LICENSE file for license information.
"""Basic example of lifecycle with an EC2 instance."""

import pycloudlib


def ec2_basic():
    """Launch an EC2 instance.

    First, setup the EC2 API and connect to the region. Credentials and
    region are determined by default by the AWS API libraries by
    looking at ~/.aws/credentials and ~/.aws/config.

    Next, to launch an instance run create. Here additional arguments
    can be passed in to further customize the instance. The wait
    argument is used to wait for the instance to complete cloud-init.

    Interactions with the instances include running a commands as well
    as pushing and pulling files.

    Finally, delete the instance.
    """
    ec2 = pycloudlib.EC2()

    instance = ec2.launch('abcd1234')
    instance.execute('ip a')
    instance.delete()


if __name__ == '__main__':
    ec2_basic()
