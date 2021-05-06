# Azure

The following page documents the Azure cloud integration in pycloudlib.

## Credentials

To access Azure via the API requires users to have four different keys:

* client id
* client secret id
* tenant id
* subscription id

To obtain this info, there are two ways supported in pycloudlib

### Azure login

By using the Azure CLI, you can login into your Azure account through it. Once you logged in, the
CLI will create folder in your home directory which will contain all of the necessary information
to use the API. To login into you Azure using the CLI, just run the following command:

```shell
az login
```

### Passed Directly

All of these four credentials can also be provided directly when initializing the Azure object:

```python
azure = pycloudlib.Azure(
    client_id='ID_VALUE',
    client_secret_id='ID_VALUE',
    tenant_id='ID_VALUE',
    subscription_id='ID_VALUE',
)
```

This way we can create different Azure instances with different configurations.

## SSH Keys

Azure requires an SSH key to be uploaded before using it. See the SSH Key page for more details.

## Image Lookup

To find latest daily Azure image for a release of Ubuntu:

```python
azure.daily_image('xenial')
"Canonical:UbuntuServer:16.04-DAILY-LTS"
```

The return Azure image can then be used for launching instances.

## Instances

Launching an instance requires at a minimum an Azure image.

```python
inst_0 = azure.launch('Canonical:UbuntuServer:14.04.0-LTS')
inst_1 = azure.launch('Canonical:UbuntuServer:18.04-DAILY-LTS')
```

If further customization of an instance is required, a user can pass additional arguments to the launch command and have them passed on.

```python
inst = azure.launch(
    image_id='Canonical:UbuntuServer:14.04.0-LTS',
    user_data='#cloud-config\nfinal_message: "system up!"',
)
```

By default, the launch method will wait for cloud-init to finish initializing before completing. When launching multiple instances a user may not wish to wait for each instance to come up by passing the `wait=False` option.

```python
instances = []
for inst in range(num_instances):
    instances.append(
        azure.launch('Canonical:UbuntuServer:18.04-DAILY-LTS', wait=False))

for instance in instances:
    instance.wait()
```

Similarly, when deleting an instance, the default action will wait for the instance to complete termination. Otherwise, the `wait=False` option can be used to start the termination of a number of instances:

```python
inst.delete()

for instance in instances:
    instance.delete(wait=False)
```

An existing instance can get used by providing an instance-id.

```python
instance = azure.get_instance('my-azure-vm')
```

## Snapshots

A snapshot of an instance is used to generate a new backing Azure image. The generated image can in turn get used to launch new instances. This allows for customization of an image and then re-use of that image.

```python
inst = azure.launch('Canonical:UbuntuServer:14.04.0-LTS')
inst.execute('touch /etc/foobar')
image_id_snapshot = azure.snapshot(inst)
inst_prime = azure.launch(image_id_snapshot)
```

The snapshot function returns a string of the created AMI ID.

To delete the image when the snapshot is no longer required:

```python
azure.image_delete(image_id_snapshot)
```
