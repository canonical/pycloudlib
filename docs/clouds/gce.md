# GCE

The following page documents the Google Cloud Engine (GCE) integration in
pycloudlib.

## Credentials

### Service Account

The preferred method of connecting to GCE is to use service account credentials. See the GCE [Authentication Getting Started](https://cloud.google.com/docs/authentication/getting-started) page for more information on creating one.

Once a service account is created, generate a key file and download it to your system. Export the credential file as a shell variable and the Google API will automatically read the environmental variable and discover the credentials:

```shell
export GOOGLE_APPLICATION_CREDENTIALS="[path to keyfile.json]"
```

### End User

A secondary method of GCE access is to use end user credentials directly. This is not the recommended method and Google will warn the user and suggest using a service account instead.

If you do wish to continue using end user credentials, then the first step is to install the [Google's Cloud SDK](https://cloud.google.com/sdk/). On Ubuntu, this can be installed quickly as a snap with the following:

```shell
sudo snap install google-cloud-sdk --classic
```

Next, is to authorize the system by getting a token. This command will launch a web-browser, have you login to you Google account, and accept any agreements:

```shell
gcloud auth application-default login
```

The Google API will automatically check first for the above environmental variable for a service account credential and fallback to this gcloud login as a secondary option.

## SSH Keys

GCE does not require any special key configuration. See the SSH Key page for more details.

## Image Lookup

To find latest daily image for a release of Ubuntu:

```python
gce.daily_image('bionic')
'ubuntu-1804-bionic-v20180823'
```

The return ID can then be used for launching instances.

## Instances

The only supported function at this time is launching an instance. No other actions, including deleting the instance are supported.
