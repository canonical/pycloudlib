# This file is part of pycloudlib. See LICENSE file for license information.
"""LXD default values to be used by cloud and instance modules."""
import textwrap


# For Xenial and Bionic vendor-data required to setup lxd-agent in a vm
LXC_SETUP_VENDORDATA = textwrap.dedent(
    """\
    config:
      user.vendor-data: |
        #cloud-config
        {custom_cfg}
        write_files:
        - path: /var/lib/cloud/scripts/per-once/setup-lxc.sh
          encoding: b64
          permissions: '0755'
          owner: root:root
          content: |
              IyEvYmluL3NoCmlmICEgZ3JlcCBseGRfY29uZmlnIC9wcm9jL21vdW50czsgdGhlbgogICAgbWtk
              aXIgLXAgL3J1bi9seGRhZ2VudAogICAgbW91bnQgLXQgOXAgY29uZmlnIC9ydW4vbHhkYWdlbnQK
              ICAgIFZJUlQ9JChzeXN0ZW1kLWRldGVjdC12aXJ0KQogICAgY2FzZSAkVklSVCBpbgogICAgICAg
              IHFlbXV8a3ZtKQogICAgICAgICAgICAoY2QgL3J1bi9seGRhZ2VudC8gJiYgLi9pbnN0YWxsLnNo
              KQogICAgICAgICAgICB1bW91bnQgL3J1bi9seGRhZ2VudAogICAgICAgICAgICBzeXN0ZW1jdGwg
              c3RhcnQgbHhkLWFnZW50LTlwIGx4ZC1hZ2VudAogICAgICAgICAgICA7OwogICAgICAgICopCiAg
              ICBlc2FjCmZpCg==
   """
)

VM_PROFILE_TMPL = textwrap.dedent(
    """\
    {vendordata}
    description: Default LXD profile for {series} VMs
    devices:
      config:
        source: cloud-init:config
        type: disk
      eth0:
        name: eth0
        network: lxdbr0
        type: nic
      root:
        path: /
        pool: default
        type: disk
    name: vm
    """
)


def _make_vm_profile(
    series: str, *, install_agent: bool, install_ssh: bool = False
) -> str:
    vendordata = "config: {}"
    if install_agent:
        custom_cfg = "packages: [openssh-server]" if install_ssh else ""
        vendordata = LXC_SETUP_VENDORDATA.format(custom_cfg=custom_cfg)
    return VM_PROFILE_TMPL.format(series=series, vendordata=vendordata)


base_vm_profiles = {
    "xenial": _make_vm_profile("xenial", install_agent=True, install_ssh=True),
    "bionic": _make_vm_profile("bionic", install_agent=True),
    "focal": _make_vm_profile("focal", install_agent=False),
}
