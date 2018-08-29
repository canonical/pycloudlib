# SSH Key Setup

Clouds have different expectations of whether a key should be pre-loaded before launching instances or whether a key can be specified during launch. This page goes through a few different scenarios.

## Default Behavior

The default behavior of pycloudlib is to use the user's RSA key found in `/home/$USER/.ssh/`. On clouds where the key is referenced by a name (e.g. AWS EC2), then the value of `$USER` is used:

| Item        | Default Location              |
| ----------- | ----------------------------- |
| Public Key  | `/home/$USER/.ssh/id_rsa.pub` |
| Private Key | `/home/$USER/.ssh/id_rsa`     |
| Name        | `$USER`                       |

If any of these values are not correct, then the user will need to specify the key to use or upload a new key. See the following sections for more information.

## Use an Uploaded Key

Ideally if the user's SSH key as started above will not work, then the user will have already uploaded the key to be used with the cloud.

To prevent needing to upload and delete a key over-and-over a user can specify a previously uploaded key by again pointing at the public key and the name the cloud uses to reference the key:

```python
cloud.use_key('/tmp/id_rsa.pub', '/tmp/private', 'powersj_tmp')
'using SSH key powersj_tmp'
```

| Item        | Default Location     |
| ----------- | -------------------- |
| Public Key  | `/tmp/id_rsa.pub`    |
| Private Key | `/tmp/private`       |
| Name        | `powersj_tmp`        |

## Upload a New Key

This is not available on all clouds, only those that require a key to be uploaded.

On AWS EC2 for example, on-the-fly SSH key usage is not allowed as a key must have been previously uploaded to the cloud. As such a user can upload a key by pointing at the public key and giving it a name. The following both uploads and tells pycloudlib which key to use in one command:

```python
cloud.upload_key('/tmp/id_rsa.pub', 'powersj_tmp')
'uploading SSH key powersj_tmp'
'using SSH key powersj_tmp'
```

Uploading a key with a name that already exists will fail. Hence having the user have the keys in place before running and using `use_key()` is the preferred method.

## Deleting an Uploaded Key

This is not available on all clouds, only those that require a key to be uploaded.

Finally, to delete an uploaded key:

```python
cloud.delete_key('powersj_tmp')
'deleting SSH key powersj_tmp'
```
