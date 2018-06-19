#!/usr/bin/env python3
# This file is part of pycloudlib. See LICENSE file for license information.
"""Basic examples of various lifecycle with a LXD instance."""

import logging

import pycloudlib

RELEASE = 'bionic'


def snapshot_instance():
    """Demonstrate snapshot functionality.

    This shows the lifecycle of booting an instance and cleaning it
    before creating a snapshot.

    Next, both create the snapshot and immediately restore the original
    instance to the snapshot level.

    Finally, launch another instance from the snapshot of the instance.

    """
    lxd = pycloudlib.LXD()
    inst = lxd.launch('pycloudlib-snapshot-base', RELEASE)
    inst.clean()
    inst.stop()

    snapshot_name = 'snapshot'
    inst.snapshot(snapshot_name)
    inst.restore(snapshot_name)

    child_name = 'pycloudlib-snapshot-child'
    child = lxd.clone('%s/%s' % (inst.name, snapshot_name), child_name)
    child.start()

    lxd.delete_instance(child_name)
    inst.delete_snapshot(snapshot_name)
    inst.delete(wait=False)


def modify_instance():
    """Demonstrate how to modify and interact with an instance.

    The inits an instance and before starting it, edits the the
    container configuration.

    Once started the instance demonstrates some interactions with the
    instance.
    """
    lxd = pycloudlib.LXD()

    inst = lxd.init('pycloudlib-modify-inst', RELEASE)
    inst.edit('limits.memory', '3GB')
    inst.start()

    inst.execute('uptime > /tmp/uptime')
    inst.pull_file('/tmp/uptime', '/tmp/pulled_file')
    inst.push_file('/tmp/pulled_file', '/tmp/uptime_2')
    inst.execute('cat /tmp/uptime_2')

    inst.delete(wait=False)


def launch_multiple():
    """Launch multiple instances.

    How to quickly launch multiple instances with LXD. This prevents
    waiting for the instance to start each time. Note that the
    wait_for_delete method is not used, as LXD does not do any waiting.
    """
    lxd = pycloudlib.LXD()

    instances = []
    for num in range(3):
        inst = lxd.launch('pycloudlib-%s' % num, RELEASE, wait=False)
        instances.append(inst)

    for instance in instances:
        instance.wait()

    for instance in instances:
        instance.delete()


def launch_options():
    """Demonstrate various launching scenarios.

    First up is launching with a different profile, in this case with
    two profiles.

    Next, is launching an ephemeral instance with a different image
    remote server.

    Then, an instance with custom network, storage, and type settings.
    This is an example of booting an instance without cloud-init so
    wait is set to False.

    Finally, an instance with custom configurations options.
    """
    lxd = pycloudlib.LXD()

    lxd.launch(
        'pycloudlib-kvm', RELEASE, profile_list=['default', 'kvm']
    )
    lxd.delete_instance('pycloudlib-kvm')

    lxd.launch(
        'pycloudlib-ephemeral', RELEASE, image_remote='ubuntu', ephemeral=True
    )
    lxd.delete_instance('pycloudlib-ephemeral')

    lxd.launch(
        'pycloudlib-custom-hw', 'ubuntu/xenial', image_remote='images',
        network='lxdbr0', storage='default', inst_type='t2.micro', wait=False
    )
    lxd.delete_instance('pycloudlib-custom-hw')

    lxd.launch(
        'pycloudlib-privileged', RELEASE,
        config_dict={
            'security.nesting': 'true',
            'security.privileged': 'true'
        }
    )
    lxd.delete_instance('pycloudlib-privileged')


def basic_lifecycle():
    """Demonstrate basic set of lifecycle operations with LXD."""
    lxd = pycloudlib.LXD()
    name = 'pycloudlib-daily'
    inst = lxd.launch(name, RELEASE)
    inst.console_log()

    inst.execute('uptime')
    inst.stop()
    inst.start()
    inst.restart()

    inst = lxd.get_instance(name)
    inst.delete()


def demo():
    """Show examples of using the LXD library."""
    basic_lifecycle()
    launch_options()
    launch_multiple()
    modify_instance()
    snapshot_instance()


if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    demo()
