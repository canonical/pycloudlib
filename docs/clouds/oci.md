# OCI

## Credentials
### Easy way
Run:
```bash
$ pip install oci-cli
$ oci setup config
```
When prompted:
```
location for your config: use default
user OCID: enter your user id found on the Oracle console at Identity>>Users>>User Details
tenancy OCID: enter your tenancy id found on the Oracle cnosole at Administration>>Tenancy Details
region: Choose something sensible
API Signing RSA key pair: use defaults for all prompts
* Note this ISN'T an SSH key pair
Follow instructions in your terminal for uploading your generated key
```

Now specify your `config_path` in pycloudlib.toml.

### Hard way

Construct your config file manually by filling in the appropriate entries
documented here: <br>
https://docs.cloud.oracle.com/en-us/iaas/Content/API/Concepts/sdkconfig.htm

### Compartment id
In addition to the OCI config, pycloudlib.toml also requires you provide the
compartment id. This can be found in the OCI console
from the menu at Identity>Compartments> <your compartment>

## SSH Keys

OCI does not require any special key configuration. See the SSH Key page for more details

## Image Lookup

OCI doesn't have a concept of releases vs daily images, so both API calls refer
to the same thing. To get the list for a release of Ubuntu:

```python
oci.released_image('focal')
'ocid1.compartment.oc1..aaaaaaaanz4b63fdemmuag77dg2pi22xfyhrpq46hcgdd3dozkvqfzwwjwxa'
```

The returned image id can then be used for launching instances.

##  Instances

Launching instances requires at minimum an image_id, though instance_type
(shape in Oracle terms) can also be specified, in addition to the other
parameters specified by the base API.

## Snapshots

A snapshot of an instance is used to generate a new backing image. The generated image can in turn get used to launch new instances. This allows for customization of an image and then re-use of that image.

```python
inst = oci.launch(image_id)
inst.execute('touch /etc/foobar')
snapshot = oci.snapshot(instance.id)
inst_prime = oci.launch(snapshot)
```
