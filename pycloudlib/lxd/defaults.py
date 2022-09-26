# This file is part of pycloudlib. See LICENSE file for license information.
"""LXD default values to be used by cloud and instance modules."""
import textwrap

LXC_PROFILE_VERSION = "v3"


# For Xenial and Bionic vendor-data required to setup lxd-agent in a vm
LXC_SETUP_VENDORDATA = textwrap.dedent(
    """\
    config:
      user.vendor-data: |
        #cloud-config
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
              c3RhcnQgbHhkLWFnZW50CiAgICAgICAgICAgIDs7CiAgICAgICAgKikKICAgIGVzYWMKZmkK
   """
)

VM_PROFILE_TMPL = textwrap.dedent(
    """\
    {vendordata}
    description: Pycloudlib LXD profile for {series} VMs
    devices:
      {config_device}
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


# LP: #1988401 dropped NoCloud metadata templates to allow detecting LXD
# datsource in cloud-init. Bionic doesn't have an active lxd-agent.service.
# and our CI use-case on Bionic VMs provide supplemental profiles which set
# user.vendor-data which can only be provided via NoCloud datasource.
# This change in behavior on Bionic VMs forces pycloudlib to repopulate
# NoCloud metadata templates if they don't exist to ensure the lxd-agent is
# running on Bionic VMs and that network-config, meta-data and vendor-data are
# appropriately setup in /var/lib/cloud/seed/nocloud-net.
BIONIC_VM_METADATA_CONFIG_NOCLOUD = {
    "/var/lib/cloud/seed/nocloud-net/meta-data": {
        "when": ["create", "copy"],
        "create_only": False,
        "template": "cloud-init-meta.tpl",
        "properties": {},
    },
    "/var/lib/cloud/seed/nocloud-net/network-config": {
        "when": ["create", "copy"],
        "create_only": False,
        "template": "cloud-init-network.tpl",
        "properties": {},
    },
    "/var/lib/cloud/seed/nocloud-net/user-data": {
        "when": ["create", "copy"],
        "create_only": False,
        "template": "cloud-init-user.tpl",
        "properties": {"default": "#cloud-config\n{}\n"},
    },
    "/var/lib/cloud/seed/nocloud-net/vendor-data": {
        "when": ["create", "copy"],
        "create_only": False,
        "template": "cloud-init-vendor.tpl",
        "properties": {"default": "#cloud-config\n{}\n"},
    },
}

BIONIC_VM_TEMPLATES_NOCLOUD = {
    "cloud-init-meta.tpl": textwrap.dedent(
        """\
        instance-id: {{ container.name }}
        local-hostname: {{ container.name }}
        {{ config_get("user.meta-data", "") }}
        """
    ),
    "cloud-init-network.tpl": textwrap.dedent(
        """\
        {% if config_get("user.network-config", "") == "" %}version: 1
        config:
            - type: physical
              name: eth0
              subnets:
                  - type: {% if config_get("user.network_mode", "") == "link-local" %}manual{% else %}dhcp{% endif %}
                    control: auto{% else %}{{ config_get("user.network-config", "") }}{% endif %}
        """  # noqa: E501
    ),
    "cloud-init-user.tpl": textwrap.dedent(
        """\
        {{ config_get("user.user-data", properties.default) }}

        """
    ),
    "cloud-init-vendor.tpl": textwrap.dedent(
        """\
        {{ config_get("user.vendor-data", properties.default) }}
        """
    ),
}


def _make_vm_profile(
    series: str, *, install_agent: bool, config_cloudinit: bool
) -> str:
    config_device = ""
    vendordata = "config: {}"
    if config_cloudinit:
        # We need to mount the config drive so that cloud-init finds the
        # vendor-data instructing it to install the agent
        config_device = "config: {source: cloud-init:config, type: disk}"
    if install_agent:
        vendordata = LXC_SETUP_VENDORDATA
    return VM_PROFILE_TMPL.format(
        config_device=config_device, series=series, vendordata=vendordata
    )


base_vm_profiles = {
    "xenial": _make_vm_profile(
        "xenial", install_agent=False, config_cloudinit=True
    ),
    "bionic": _make_vm_profile(
        "bionic", install_agent=True, config_cloudinit=True
    ),
    "default": _make_vm_profile(
        "default", install_agent=False, config_cloudinit=False
    ),
}
