# Openstack

## Credentials

No connection information is directly passed to pycloudlib but rather relies **clouds.yaml** or **OS_** environment variables. See [the openstack configuration docs](https://docs.openstack.org/python-openstackclient/victoria/configuration/index.html) for more information.

## SSH Keys

Openstack can't launch instances unless an openstack managed keypair already exists. Since pycloudlib also manages keys, pycloudlib will attempt to use or create an openstack ssh keypair based on the pycloudlib keypair. If a key is provided to pycloudlib with the same name and public key that already exists in openstack, that key will be used. If no key information is provided, an openstack keypair will be created with the current user's username and public key.

## Image ID

The image id to use for a launch must be manually passed to pycloudlib rather than determined from release name. Given that each openstack deployment can have a different setup of images, it's not practical given the information we have to guess which image to use for any particular launch.

## Network ID

Network ID must be manually passed to pycloudlib. Since there can be multiple networks and no concept of a default network, we can't choose which network to create an instance on.

## Floating IPs

A floating IP is allocated and used per instance created. The IP is then deleted when the instance is deleted.
