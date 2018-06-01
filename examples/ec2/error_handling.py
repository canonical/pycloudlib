#!/usr/bin/python3
# This file is part of pycloudlib. See LICENSE file for license information.
"""Exception handling with with an EC2 instance."""

import pycloudlib


def ec2_error_handling():
    """Demonstrating the possible exceptions.

    During platform related actions a PlatformError may be thrown if
    any platform actions fail.

    During instance interactions the InTargetExecuteError may be thrown
    if any instance actions fail.
    """
    try:
        ec2 = pycloudlib.EC2()
        instance = ec2.launch(image_id='abcd1234', instance_type='i3.metal')
    except pycloudlib.PlatformError as error:
        print(error)

    try:
        instance.execute('ip a')
    except pycloudlib.InTargetExecuteError as error:
        print(error)

    instance.delete()


if __name__ == '__main__':
    ec2_error_handling()
