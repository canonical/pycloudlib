# This file is part of pycloudlib. See LICENSE file for license information.
"""LXD default values to be used by cloud and instance modules."""
import base64
import textwrap

LXC_PROFILE_VERSION = "v4"

LXC_AGENT_PATH = "/lib/systemd/system/lxd-agent.service"
#  pylint: disable=anomalous-backslash-in-string
LXC_AGENT_SCRIPT = textwrap.dedent(
    """\
    #!/bin/sh
    if ! grep lxd_config /proc/mounts; then
        mkdir -p /run/lxdagent
        mount -t 9p config /run/lxdagent
        VIRT=$(systemd-detect-virt)
        case $VIRT in
            qemu|kvm)
                (cd /run/lxdagent/ && ./install.sh)
                umount /run/lxdagent

                # Currently, there is a regression on the lxd_agent
                # service. Until this fix is addressed through the
                # lxd snap, we need this hacky approach to allow
                # starting the agent on some Ubuntu series.
                sed -i '/^\(After\|Requires\)=run-lxd_agent\.mount$/d' {}
                systemctl daemon-reload

                systemctl start lxd-agent
                ;;
            *)
        esac
    fi
    """.format(  # noqa: W605
        LXC_AGENT_PATH
    )
)


# For Bionic vendor-data required to setup lxd-agent in a vm
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
          content: {base64_lxd_agent_script}
   """
)

VM_PROFILE_TMPL = textwrap.dedent(
    """\
    {vendordata}
    description: Default LXD profile for {series} VMs
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
        lxd_agent_script = base64.b64encode(LXC_AGENT_SCRIPT.encode("ascii"))
        vendordata = LXC_SETUP_VENDORDATA.format(
            base64_lxd_agent_script=lxd_agent_script.decode("ascii")
        )
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
    "focal": _make_vm_profile(
        "focal", install_agent=False, config_cloudinit=False
    ),
    "groovy": _make_vm_profile(
        "groovy", install_agent=False, config_cloudinit=False
    ),
    "hirsute": _make_vm_profile(
        "hirsute", install_agent=False, config_cloudinit=False
    ),
    "impish": _make_vm_profile(
        "impish", install_agent=False, config_cloudinit=False
    ),
    "jammy": _make_vm_profile(
        "jammy", install_agent=False, config_cloudinit=False
    ),
}
