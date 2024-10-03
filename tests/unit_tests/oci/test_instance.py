import pytest
from unittest import mock

from pycloudlib.oci.instance import OciInstance
from pycloudlib.errors import PycloudlibError


@pytest.fixture
def oci_instance():
    key_pair = mock.Mock()
    instance_id = "ocid1.instance.oc1..exampleuniqueID"
    compartment_id = "ocid1.compartment.oc1..exampleuniqueID"
    availability_domain = "Uocm:PHX-AD-1"

    # Mock OCI configuration
    oci_config = {
        "user": "user_ocid",
        "fingerprint": "fingerprint",
        "key_file": "path/to/key_file",
        "tenancy": "tenancy_ocid",
        "region": "us-phoenix-1",
    }

    with mock.patch(
        "pycloudlib.oci.instance.oci.config.from_file",
        return_value=oci_config,
    ), mock.patch(
        "pycloudlib.oci.instance.oci.core.ComputeClient"
    ) as mock_compute_client_class, mock.patch(
        "pycloudlib.oci.instance.oci.core.VirtualNetworkClient"
    ) as mock_network_client_class:
        # Instantiate mocked clients
        mock_compute_client = mock.Mock()
        mock_network_client = mock.Mock()
        mock_compute_client_class.return_value = mock_compute_client
        mock_network_client_class.return_value = mock_network_client

        # Create instance
        instance = OciInstance(
            key_pair,
            instance_id,
            compartment_id,
            availability_domain,
            username="opc",
        )

        # Assign the mocked clients to the instance
        instance.compute_client = mock_compute_client
        instance.network_client = mock_network_client

        # Mock get_instance data
        instance_data_mock = mock.Mock()
        instance_data_mock.id = instance_id
        instance.compute_client.get_instance.return_value = mock.Mock(
            data=instance_data_mock
        )

        yield instance


def setup_mock_vnic(oci_instance, vnic_data_list):
    """
    Helper function to mock VNIC attachments and VNIC data.
    vnic_data_list is a list of tuples:
        (vnic_id_suffix, is_primary, public_ip, ipv6_addresses)
    """
    vnic_attachments = []
    vnics_data = {}

    for (
        vnic_id_suffix,
        is_primary,
        public_ip,
        ipv6_addresses,
    ) in vnic_data_list:
        vnic_id = f"ocid1.vnic.oc1..vnicuniqueID{vnic_id_suffix}"
        # Create VNIC attachment mock
        vnic_attachment = mock.Mock()
        vnic_attachment.vnic_id = vnic_id
        vnic_attachments.append(vnic_attachment)

        # Create VNIC data mock
        vnic = mock.Mock()
        vnic.is_primary = is_primary
        vnic.public_ip = public_ip
        vnic.ipv6_addresses = ipv6_addresses
        vnics_data[vnic_id] = mock.Mock(data=vnic)

    oci_instance.compute_client.list_vnic_attachments.return_value = mock.Mock(
        data=vnic_attachments
    )

    # Mock get_vnic to return appropriate VNIC data based on vnic_id
    def get_vnic_side_effect(vnic_id):
        return vnics_data.get(vnic_id, mock.Mock(data=mock.Mock()))

    oci_instance.network_client.get_vnic.side_effect = get_vnic_side_effect


@pytest.mark.parametrize(
    [
        "primary_has_ipv4",
        "primary_has_ipv6",
        "secondary_has_ipv4",
        "secondary_has_ipv6",
        "primary_first",
        "expected_ip",
        "expect_error",
    ],
    [
        pytest.param(
            True,  # primary_has_ipv4
            False,  # primary_has_ipv6
            False,  # secondary_has_ipv4
            False,  # secondary_has_ipv6
            True,  # primary_first
            "203.0.113.1",  # expected_ip
            False,  # expect_error
            id="Primary VNIC has IPv4 (primary first)",
        ),
        pytest.param(
            False,  # primary_has_ipv4
            True,  # primary_has_ipv6
            False,  # secondary_has_ipv4
            False,  # secondary_has_ipv6
            False,  # primary_first
            "2001:db8::1",  # expected_ip
            False,  # expect_error
            id="Primary VNIC has IPv6 (primary not first)",
        ),
        pytest.param(
            False,  # primary_has_ipv4
            False,  # primary_has_ipv6
            True,  # secondary_has_ipv4
            False,  # secondary_has_ipv6
            True,  # primary_first
            None,  # expected_ip
            True,  # expect_error
            id="Primary VNIC no IPs, secondary has IPv4 (expect error)",
        ),
        pytest.param(
            False,  # primary_has_ipv4
            False,  # primary_has_ipv6
            False,  # secondary_has_ipv4
            True,  # secondary_has_ipv6
            False,  # primary_first
            None,  # expected_ip
            True,  # expect_error
            id="Primary VNIC no IPs, secondary has IPv6 (expect error)",
        ),
        pytest.param(
            False,  # primary_has_ipv4
            True,  # primary_has_ipv6
            True,  # secondary_has_ipv4
            False,  # secondary_has_ipv6
            True,  # primary_first
            "2001:db8::1",  # expected_ip
            False,  # expect_error
            id="Primary IPv6, secondary IPv4",
        ),
        pytest.param(
            True,  # primary_has_ipv4
            True,  # primary_has_ipv6
            False,  # secondary_has_ipv4
            False,  # secondary_has_ipv6
            True,  # primary_first
            "203.0.113.1",  # expected_ip
            False,  # expect_error
            id="Primary VNIC has both IPv4 and IPv6 (primary first)",
        ),
        pytest.param(
            True,  # primary_has_ipv4
            True,  # primary_has_ipv6
            False,  # secondary_has_ipv4
            False,  # secondary_has_ipv6
            False,  # primary_first
            "203.0.113.1",  # expected_ip
            False,  # expect_error
            id="Primary VNIC has both IPv4 and IPv6 (primary not first)",
        ),
        pytest.param(
            False,  # primary_has_ipv4
            False,  # primary_has_ipv6
            True,  # secondary_has_ipv4
            True,  # secondary_has_ipv6
            True,  # primary_first
            None,  # expected_ip
            True,  # expect_error
            id="Primary VNIC no IPs, secondary has both (expect error)",
        ),
        pytest.param(
            True,  # primary_has_ipv4
            False,  # primary_has_ipv6
            True,  # secondary_has_ipv4
            False,  # secondary_has_ipv6
            False,  # primary_first
            "203.0.113.1",  # expected_ip
            False,  # expect_error
            id="Both VNICs have IPv4 (primary not first)",
        ),
        pytest.param(
            False,  # primary_has_ipv4
            False,  # primary_has_ipv6
            False,  # secondary_has_ipv4
            False,  # secondary_has_ipv6
            True,  # primary_first
            None,  # expected_ip
            True,  # expect_error
            id="No VNICs have IPs (expect error)",
        ),
        pytest.param(
            False,  # primary_has_ipv4
            True,  # primary_has_ipv6
            True,  # secondary_has_ipv4
            False,  # secondary_has_ipv6
            False,  # primary_first
            "2001:db8::1",  # expected_ip
            False,  # expect_error
            id="Multiple primary VNICs, primary not first (IPv6)",
        ),
        pytest.param(
            True,  # primary_has_ipv4
            False,  # primary_has_ipv6
            False,  # secondary_has_ipv4
            False,  # secondary_has_ipv6
            False,  # primary_first
            "203.0.113.1",  # expected_ip
            False,  # expect_error
            id="Primary VNIC has IPv4 (primary not first)",
        ),
    ],
)
def test_oci_instance_ip_parametrized(
    oci_instance,
    primary_has_ipv4,
    primary_has_ipv6,
    secondary_has_ipv4,
    secondary_has_ipv6,
    primary_first,
    expected_ip,
    expect_error,
):
    # Prepare VNIC configurations
    # Primary VNIC configuration
    primary_vnic = (
        "1",  # vnic_id_suffix
        True,  # is_primary
        "203.0.113.1" if primary_has_ipv4 else None,  # public_ip
        ["2001:db8::1"] if primary_has_ipv6 else [],  # ipv6_addresses
    )

    # Secondary VNIC configuration
    secondary_vnic = (
        "2",  # vnic_id_suffix
        False,  # is_primary
        "203.0.113.2" if secondary_has_ipv4 else None,  # public_ip
        ["2001:db8::2"] if secondary_has_ipv6 else [],  # ipv6_addresses
    )

    # Arrange VNICs based on primary_first flag
    if primary_first:
        vnics_ordered = [primary_vnic, secondary_vnic]
    else:
        vnics_ordered = [secondary_vnic, primary_vnic]

    # Setup mock VNICs
    setup_mock_vnic(oci_instance, vnics_ordered)

    if expect_error:
        with pytest.raises(
            PycloudlibError,
            match="No public ipv4 address or ipv6 address found",
        ):
            _ = oci_instance.ip
    else:
        assert oci_instance.ip == expected_ip
