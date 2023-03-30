# VMWare

The VMWare support in pycloudlib is specific to vSphere. In particular, vSphere 7 was tested.

## Prerequisites

VMWare usage in Pycloudlib requires the [govc](https://github.com/vmware/govmomi/tree/main/govc) command line tool to be available on the PATH. See [VMWare docs](https://docs.vmware.com/en/VMware-Telco-Cloud-Operations/1.4.0/deployment-guide-140/GUID-5249E662-D792-4A1A-93E6-CF331552364C.html) for installation information.

## Available Images

To create new instances, pycloudlib will clone an existing VM within vSphere that is designated as the image source. In order to quality, the VM must meet the following requirements:

- A standard (non-template) VM.
- Powered off
- In the same folder that new VMs will be deployed to (see `folder` in `pycloudlib.toml`)
- Have the "InjectOvfEnv" setting be `false`.
- Be named appropriately: `TEMPLATE-cloud-init-<release>`

As of this writing, `TEMPLATE-cloud-init-focal` and `TEMPLATE-cloud-init-jammy` are valid source VMs.

To create the Ubuntu-based source images, the following procedure was followed for a Jammy image:

- Download the `.ova` for the release from the [release server](https://cloud-images.ubuntu.com/releases/server/jammy/release/)
- `govc import.spec ubuntu-jammy-server-cloudimg-amd64.ova | python -m json.tool > ubuntu.json`
- Modify the json file appropriately
- `govc import.ova -options=ubuntu.json ./ubuntu-jammy-server-cloudimg-amd64.ova`

Example ubuntu.json:

```
{
    "DiskProvisioning": "thin",
    "IPAllocationPolicy": "dhcpPolicy",
    "IPProtocol": "IPv4",
    "PropertyMapping": [
        {
            "Key": "instance-id",
            "Value": ""
        },
        {
            "Key": "hostname",
            "Value": ""
        },
        {
            "Key": "seedfrom",
            "Value": ""
        },
        {
            "Key": "public-keys",
            "Value": ""
        },
        {
            "Key": "user-data",
            "Value": ""
        },
        {
            "Key": "password",
            "Value": ""
        }
    ],
    "NetworkMapping": [
        {
            "Name": "VM Network",
            "Network": "VLAN_2763"
        }
    ],
    "MarkAsTemplate": false,
    "PowerOn": false,
    "InjectOvfEnv": false,
    "WaitForIP": false,
    "Name": "TEMPLATE-cloud-init-jammy"
}
```

## SSH Keys

To avoid cloud-init detecting an instance as an OVF datasource, passing a public key through ovf xml is not supported. Rather, when the instance is created, the pycloudlib managed ssh public key is added to the cloud-config user data of the instance. This means that the user data on the launched instance will always contain an extra public key compared to what was passed to pycloudlib.

## Blocking calls

Since calls to `govc` are blocking, specifying `wait=False` to enable non-blocking calls will not work.
