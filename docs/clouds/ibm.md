# IBM

The following page documents the IBM VPC cloud integration in pycloudlib.

## Credentials

To operate on IBM VPC an IBM Cloud API key is required. This should be set in pycloudlib.toml
or passed to pycloudlib.IBM at initialization time.

## SSH Keys

IBM VPC requires an SSH key to be uploaded before using it. See the SSH Key page for more details.

## Image Lookup

Note: IBM does not contain daily Ubuntu images.

To find latest released image ID for a release of Ubuntu:

```python
ibm.released_image('xenial')
'r010-7334d328-7a1f-47d4-8dda-013e857a1f2b'
```

The return image ID can then be used for launching instances.

## Instances

Launching an instance requires at a minimum an image ID. Optionally, a user can specify an instance type or a Virtual Private Cloud (VPC):

```python
inst_0 = ibm.launch('r010-7334d328-7a1f-47d4-8dda-013e857a1f2b')
inst_1 = ibm.launch('r010-7334d328-7a1f-47d4-8dda-013e857a1f2b', instance_type='bx2-metal-96x384', user_data=data)
vpc = ibm.get_or_create_vpc('custom_vpc')
inst_2 = ibm.launch('r010-7334d328-7a1f-47d4-8dda-013e857a1f2b', vpc=vpc)
```

If no VPC is specified the region's default VPC, including security group is used. See the Virtual Private Cloud (VPC) section below for more details on creating a custom VPC.

If further customization of an instance is required, a user can pass additional arguments to the launch command and have them passed on.

```python
inst = ibm.launch(
    'r010-7334d328-7a1f-47d4-8dda-013e857a1f2b',
    **kwargs,
)
```

By default, the launch method will wait for cloud-init to finish initializing before completing. When launching multiple instances a user may not wish to wait for each instance to come up by passing the `wait=False` option.

```python
instances = []
for inst in range(num_instances):
    instances.append(ibm.launch('r010-7334d328-7a1f-47d4-8dda-013e857a1f2b', wait=False))

for instance in instances:
    instance.wait()
```

Similarly, when deleting an instance, the default action will wait for the instance to complete termination. Otherwise, the `wait=False` option can be used to start the termination of a number of instances:

```python
inst.delete()

for instance in instances:
    instance.delete(wait=False)

for instance in instances:
    instance.wait_for_delete()
```

An existing instance can get used by providing an instance-id.

```python
instance = ibm.get_instance('i-025795d8e55b055da')
```

## Snapshots

A snapshot of an instance is used to generate a new backing Custom Image. The generated image can in turn get used to launch new instances. This allows for customization of an image and then re-use of that image.

```python
inst = ibm.launch('r010-7334d328-7a1f-47d4-8dda-013e857a1f2b')
inst.update()
inst.execute('touch /etc/foobar')
snapshot = ibm.snapshot(instance.id)
inst_prime = ibm.launch(snapshot)
```

The snapshot function returns a string of the created Custom Image ID.

To delete the image when the snapshot is no longer required:

```python
ibm.image_delete(snapshot)
```

## Unique Operations

The following are unique operations to the IBM cloud.

### Virtual Private Clouds

If a custom VPC is required for any reason, then one can be created
and then later used during instance creation.

```python
vpc = ibm.get_or_create_vpc(name)
ibm.launch('r010-7334d328-7a1f-47d4-8dda-013e857a1f2b', vpc=vpc)
```

If the VPC is destroyed, all instances and subnets will be deleted as well.

```python
vpc.delete()
```
