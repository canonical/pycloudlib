"""A run through of base API operations on all supported clouds."""

import os
from contextlib import suppress

import pycloudlib
from pycloudlib.cloud import BaseCloud


cloud_config = """#cloud-config
runcmd:
  - echo 'hello' > /home/ubuntu/example.txt
"""


def exercise_api(client: BaseCloud):
    """Run through supported functions in the base API."""
    try:
        image_id = client.released_image('focal')
    except NotImplementedError:
        image_id = client.daily_image('focal')
    print('focal image id: {}'.format(image_id))
    print('launching instance...')
    instance = client.launch(
        image_id=image_id,
        user_data=cloud_config
    )

    print('instance name: {}'.format(instance.name))
    with suppress(NotImplementedError):
        print('instance ip: {}'.format(instance.ip))

    print('starting instance...')
    instance.start()
    print('waiting for cloud-init...')
    instance.execute('cloud-init status --wait --long')
    with suppress(NotImplementedError):
        instance.console_log()
    example_output = instance.execute('cat /home/ubuntu/example.txt').stdout
    assert example_output == 'hello', example_output

    print('restarting instance...')
    instance.execute('sync')  # Prevent's some wtfs :)
    instance.restart()
    example_output = instance.execute('cat /home/ubuntu/example.txt').stdout
    assert example_output == 'hello', example_output

    print('shutting down instance...')
    instance.shutdown()
    print('starting instance...')
    instance.start()
    example_output = instance.execute('cat /home/ubuntu/example.txt').stdout
    assert example_output == 'hello', example_output
    snapshot_id = None
    with suppress(NotImplementedError):
        print('snapshotting instance...')
        snapshot_id = client.snapshot(instance)
        print('snapshot image id: {}'.format(snapshot_id))
    if snapshot_id:
        assert snapshot_id != image_id
        instance_from_snapshot = client.launch(image_id=snapshot_id)
        instance_from_snapshot.start()
        instance_from_snapshot.execute('cloud-init status --wait --long')
        print('deleting instance created from snapshot')
        instance_from_snapshot.delete()
        print('deleting snapshot...')
        client.delete_image(snapshot_id)

    print('deleting instance...')
    instance.delete()


clouds = {
    pycloudlib.Azure: {},
    pycloudlib.EC2: {},
    pycloudlib.GCE: {
        'project': os.environ.get('PROJECT'),
        'region': 'us-central1',
        'zone': 'a',
    },
    pycloudlib.OCI: {
        'compartment_id': os.environ.get('COMPARTMENT_ID')
    },
    pycloudlib.Openstack: {
        'network': os.environ.get('OPENSTACK_NETWORK'),
    },
    pycloudlib.LXD: {},
}

if __name__ == '__main__':
    for cloud, cloud_kwargs in clouds.items():
        print('Using cloud: {}'.format(cloud.__name__))
        client_api = cloud(tag='base-api-test', **cloud_kwargs)
        exercise_api(client_api)
        print()
