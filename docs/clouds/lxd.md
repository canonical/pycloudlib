# LXD

The following page documents the LXD cloud integration in pycloudlib.

## Launching Instances

Launching instances with LXD only requires an instance name and a release name by default.

```python
lxd.launch('my-instance', 'bionic')
```

Instances can be initialized or launched. The difference is initializing involves getting the required image and setting up the instance, but not starting it. The following is the same as the above command.

```python
inst = lxd.init('my-instance', 'bionic')
inst.start()
```

### Launch Options

Instances can take a large number of settings and options. Consult the API for a full list, however here are a few examples showing different image remotes, ephemeral instance creation, and custom settings.

```python
lxd.launch(
    'pycloudlib-ephemeral', 'bionic', image_remote='ubuntu', ephemeral=True
)

lxd.launch(
    'pycloudlib-custom-hw', 'ubuntu/xenial', image_remote='images',
    network='lxdbr0', storage='default', inst_type='t2.micro', wait=False
)
```

## Snapshots

Snapshots allow for saving and reverting to a particular point in time.

```python
instance.snapshot(snapshot_name)
instance.restore(snapshot_name)
```

Snapshots can at as a base for creating new instances at a pre-configured state. See the cloning section below.

## Cloning

Cloning instances allows for copying an existing instance or snapshot of an instance to a new container. This is useful when wanting to setup a instance with a particular state and then re-use that state over and over to avoid needing to repeat the steps to get to the initial state.

```python
lxd.launch_snapshot('instance', new_instance_name)
lxd.launch_snapshot('instance\snapshot', new_instance_name)
```

## Unique Operations

### Enable KVM

Enabling KVM to work properly inside a container requires passing the `/dev/kvm` device to the container. This can be done by creating a profile and then using that profile when launching instances.

```shell
lxc profile create kvm
```

Add the `/dev/kvm` device to the profile.

```yaml
devices:
  kvm:
    path: /dev/kvm
    type: unix-char
```

Then launch the instance using the default and the KVM profiles.

```python
lxd.launch(
    'pycloudlib-kvm', RELEASE, profile_list=['default', 'kvm']
)
```

### Nested instances

To enable nested instances of LXD containers requires making the container a privileged containers. This can be achieved by setting the appropriate configuration options.

```python
lxd.launch(
    'pycloudlib-privileged',
    'bionic,
    config_dict={
        'security.nesting': 'true',
        'security.privileged': 'true'
    }
)
```