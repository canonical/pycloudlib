# Images

By default, images used are based on Ubuntu's daily cloud images.

pycloudlib uses [simplestreams](https://launchpad.net/simplestreams) to determine the latest daily images using the appropriate images found at [Ubuntu Cloud Images](https://cloud-images.ubuntu.com/daily/) site.

## Filter

The image search is filtered based on a variety of options, which vary from cloud to cloud. Here is an example for Amazon's EC2:

```python
        filters = [
            'arch=%s' % arch,
            'endpoint=%s' % 'https://ec2.%s.amazonaws.com' % self.region,
            'region=%s' % self.region,
            'release=%s' % release,
            'root_store=%s' % root_store,
            'virt=hvm',
        ]
```

This allows for the root store to be configurable by the user.
