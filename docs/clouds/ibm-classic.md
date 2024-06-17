# IBM Classic

The following page documents the IBM Classic cloud integration in pycloudlib.

## IBM Classic / SoftLayer Naming 

IBM Classic, often referred to as IBM SoftLayer, originates from IBM's acquisition of SoftLayer Technologies in 2013. SoftLayer was a cloud infrastructure provider known for its robust and flexible cloud services. After the acquisition, IBM integrated SoftLayer's technology and services into its own cloud offerings. For several years, IBM marketed these services under the SoftLayer brand, which led to the name "IBM SoftLayer" becoming synonymous with the classic IBM cloud infrastructure.

The term "IBM Classic" distinguishes these original SoftLayer-based services from IBM's newer cloud
solution, IBM VPC, which includes more advanced and updated cloud technologies. 
IBM Classic services are still available and widely used, especially by customers who have
long-standing services and infrastructure on the platform.

## Credentials

To operate on IBM VPC an IBM Cloud API key is required. This should be set in pycloudlib.toml
or passed to pycloudlib.IBM at initialization time.

## SSH Keys

IBM Classic requires an SSH key to be uploaded before using it. SSH Keys used on IBM VPC can also be used on IBM
Classic.  
For more information on SSH Keys, see the SSH Key page.

## Image Lookup

Note: IBM Classic does not contain daily Ubuntu images.

To find latest released image ID for a release of Ubuntu:

```python
ibm_classic.released_image('22.04', disk_size="25G")
'eac66200-0ccd-4497-aebe-168eafee9944'
```
* Note: This is the image Global Identifier (GID) and not the image ID. 

The returned image GID can then be used for launching instances.

## Instances

Launching an instance requires at a minimum an image GID or ID.

Optionally, a user can specify:
- instance type: type of instance to create. This value is
  combined with the disk_size to create the instance flavor. For
  example, B1_2X4 with disk_size of 25G would result in "B1_2X4X25".
- domain name: domain name for creating the FQDN for the instance. default is `pycloudlib.cloud`
- name: name to be given to the instance
- disk size: either "25G" or "100G". Default is "25G"
- datacenter: the datacenter to launch the instance in
- datacenter region: region to select datacenter from if datacenter is not specified

### Suggested instance flavors

#### For low cost operation:
- `U1_1X2` and `U1_2X4` 
- `B1_1X2` and `B1_2X4` 

### Example instance launches:

#### Minimum options:
```python
inst_0 = ibm_classic.launch(image_id='eac66200-0ccd-4497-aebe-168eafee9944')
```

#### Specify name
```python
inst_1 = ibm_classic.launch(
  image_id='eac66200-0ccd-4497-aebe-168eafee9944',
  name="test_instance",
)
```

#### Specify disk size
```python
inst_2 = ibm_classic.launch(
  image_id='eac66200-0ccd-4497-aebe-168eafee9944',
  disk_size="100G",
)
```

#### Specify instance type:
```python
inst_3 = ibm_classic.launch(
  image_id='eac66200-0ccd-4497-aebe-168eafee9944',
  instance_type='U1_1X2',
)
```

#### Specify all options:
```python
inst_4 = ibm_classic.launch(
  image_id='eac66200-0ccd-4497-aebe-168eafee9944',
  name="test_instance",
  instance_type='U1_1X2',
  disk_size="100G",
  datacenter='dal13',
  domain_name='yourdomain.com',
)
```
### Notes on waiting for instances

#### Waiting on launch
By default, the launch method will wait for cloud-init to finish initializing before completing. When launching multiple instances a user may not wish to wait for each instance to come up by passing the `wait=False` option.

```python
instances = []
for inst in range(num_instances):
    instances.append(ibm_classic.launch('eac66200-0ccd-4497-aebe-168eafee9944', wait=False))

for instance in instances:
    instance.wait()
```

#### Waiting on delete
Similarly, when deleting an instance, the default action will wait for the instance to complete termination. Otherwise, the `wait=False` option can be used to start the termination of a number of instances:

```python
inst.delete()

for instance in instances:
    instance.delete(wait=False)

for instance in instances:
    instance.wait_for_delete()
```

### Using an existing instance

An existing instance can get used by providing an instance-id from an existing instance:

```python
instance = ibm_classic.get_instance('i-025795d8e55b055da')
```

## Snapshots

A snapshot of an instance is used to generate a new backing Custom Image. The generated image can in turn get used to launch new instances. This allows for customization of an image and then re-use of that image.

```python
inst = ibm_classic.launch('r010-7334d328-7a1f-47d4-8dda-013e857a1f2b')
inst.update()
inst.execute('touch /etc/foobar')
snapshot = ibm_classic.snapshot(instance.id)
inst_prime = ibm_classic.launch(snapshot)
```

The snapshot function returns a string of the created Custom Image ID.

To delete the image when the snapshot is no longer required:

```python
ibm_classic.delete_image(snapshot)
```

