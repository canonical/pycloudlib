#!/usr/bin/python3
# This file is part of pycloudlib. See LICENSE file for license information.
"""Multi-Instance launch and delete with EC2."""

import pycloudlib


def ec2_multi_instance(num_instances):
    """Launch and delete multiple EC2 instances.

    This demonstrates the fastest way to create multiple instances.
    In these cases, the wait argument is set to False to allow for
    launching instances as quickly as possible and then run commands
    once cloud-init is complete and immediately delete the instance.
    The last step is to verify that the instance is in fact deleted.

    @param num_instances: number of instances to create
    """
    ec2 = pycloudlib.EC2()

    instances = []
    for instance in num_instances:
        instance.append(
            ec2.launch('abcd1234', wait=False)
        )

    for instance in instances:
        instance.wait()
        instance.run('date')
        instance.terminate(wait=False)

    for instance in instances:
        instance.wait_for_terminate()


if __name__ == '__main__':
    ec2_multi_instance(2)
