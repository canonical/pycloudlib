# EC2

The following page documents the AWS EC2 cloud integration in pycloudlib.

## Credentials

To access EC2 requires users to have an access key id and secret access key. These should be set in pycloudlib.toml.

### AWS Dotfile (Deprecated)

The AWS CLI, Python library boto3, and other AWS tools maintain credentials and configuration settings in a local dotfile found under the aws dotfile directory (i.e. `/home/$USER/.aws/`). If these files exist they will be used to provide login and region information.

These configuration files are normally generated when running `aws configure`:

```shell
$ cat /home/$USER/.aws/credentials
[default]
aws_access_key_id = <KEY_VALUE>
aws_secret_access_key = <KEY_VALUE>
$ cat /home/$USER/.aws/config
[default]
output = json
region = us-west-2
```

### Passed Directly (Deprecated)

The credential and region information can also be provided directly when initializing the EC2 object:

```python
ec2 = pycloudlib.EC2(
    access_key_id='KEY_VALUE',
    secret_access_key='KEY_VALUE',
    region='us-west-2'
)
```

This way different credentials or regions can be used by different objects allowing for interactions with multiple regions at the same time.

## SSH Keys

EC2 requires an SSH key to be uploaded before using it. See the SSH Key page for more details.

## Image Lookup

To find latest daily AMI ID for a release of Ubuntu:

```python
ec2.daily_image('xenial')
'ami-537e9a30'
```

The return AMI ID can then be used for launching instances.

## Instances

Launching an instance requires at a minimum an AMI ID. Optionally, a user can specify an instance type or a Virtual Private Cloud (VPC):

```python
inst_0 = ec2.launch('ami-537e9a30')
inst_1 = ec2.launch('ami-537e9a30', instance_type='i3.metal', user_data=data)
vpc = ec2.get_or_create_vpc('private_vpc')
inst_2 = ec2.launch('ami-537e9a30', vpc=vpc)
```

If no VPC is specified the region's default VPC, including security group is used. See the Virtual Private Cloud (VPC) section below for more details on creating a custom VPC.

If further customization of an instance is required, a user can pass additional arguments to the launch command and have them passed on.

```python
inst = ec2.launch(
    'ami-537e9a30',
    UserData='#cloud-config\nfinal_message: "system up!"',
    Placement={
        'AvailabilityZone': 'us-west-2a'
    },
    SecurityGroupsIds=[
        'sg-1e838479',
        'sg-e6ef7d80'
    ]
)
```

By default, the launch method will wait for cloud-init to finish initializing before completing. When launching multiple instances a user may not wish to wait for each instance to come up by passing the `wait=False` option.

```python
instances = []
for inst in range(num_instances):
    instances.append(ec2.launch('ami-537e9a30', wait=False))

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
instance = ec2.get_instance('i-025795d8e55b055da')
```

## Snapshots

A snapshot of an instance is used to generate a new backing AMI image. The generated image can in turn get used to launch new instances. This allows for customization of an image and then re-use of that image.

```python
inst = ec2.launch('ami-537e9a30')
inst.update()
inst.execute('touch /etc/foobar')
snapshot = ec2.snapshot(instance.id)
inst_prime = ec2.launch(snapshot)
```

The snapshot function returns a string of the created AMI ID.

To delete the image when the snapshot is no longer required:

```python
ec2.image_delete(snapshot)
```

## Unique Operations

The following are unique operations to the EC2 cloud.

### Virtual Private Clouds

If a custom VPC is required for any reason, then one can be created
and then later used during instance creation.

```python
vpc = ec2.get_or_create_vpc(name, ipv4_cidr='192.168.1.0/20')
ec2.launch('ami-537e9a30', vpc=vpc)
```

If the VPC is destroyed, all instances will be deleted as well.

```python
vpc.delete()
```

### Hot Add Storage Volumes

An instance is capable of getting additional storage hot added to it:

```python
inst.add_volume(size=8, drive_type='gp2')
```

Volumes are attempted to be added at the next available location from `/dev/sd[f-z]`. However, NVMe devices will still be placed under `/dev/nvme#`.

Additional storage devices that were added will be deleted when the instance is removed.

### Hot Add Network Devices

It is possible to hot add network devices to an instance.

```python
inst.add_network_interface()
```

The instance will take the next available index. It is up to the user to configure the network devices once added.

Additional network devices that were added will be deleted when the instance is removed.
