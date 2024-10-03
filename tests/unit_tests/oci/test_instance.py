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

class TestOciInstanceInit:
    """Tests for the OciInstance __init__ function."""

    def test_init(self, oci_instance):
        """Test instance initialization."""
        assert oci_instance.instance_id == "ocid1.instance.oc1..exampleuniqueID"
        assert oci_instance.compartment_id == "ocid1.compartment.oc1..exampleuniqueID"
        assert oci_instance.availability_domain == "Uocm:PHX-AD-1"
        assert oci_instance.username == "opc"
        assert oci_instance._ip is None
        assert oci_instance._fault_domain is None

    def test_init_uses_default_config(self):
        """Test that the default config is used if oci_config is None."""
        key_pair = mock.Mock()

        with mock.patch("pycloudlib.oci.instance.oci.config.from_file") as mock_from_file, \
             mock.patch("pycloudlib.oci.instance.oci.core.ComputeClient") as mock_compute_client_class, \
             mock.patch("pycloudlib.oci.instance.oci.core.VirtualNetworkClient") as mock_network_client_class:
            # Mock the config and valid configuration details
            mock_from_file.return_value = {
                "user": "ocid1.user.oc1..exampleuniqueID",
                "fingerprint": "fingerprint",
                "key_file": "/path/to/key",
                "tenancy": "ocid1.tenancy.oc1..exampleuniqueID",
                "region": "us-phoenix-1"
            }

            # Mock the clients that will be initialized using the config
            mock_compute_client = mock.Mock()
            mock_network_client = mock.Mock()
            mock_compute_client_class.return_value = mock_compute_client
            mock_network_client_class.return_value = mock_network_client

            # Create an instance without passing oci_config, relying on the default
            instance = OciInstance(
                key_pair,
                "ocid1.instance.oc1..exampleuniqueID",
                "ocid1.compartment.oc1..exampleuniqueID",
                "Uocm:PHX-AD-1",
                oci_config=None
            )

            # Assert that the default config was used
            assert instance.compute_client == mock_compute_client
            assert instance.network_client == mock_network_client
            mock_from_file.assert_called_once_with("~/.oci/config")


class TestOciInstanceProperties:
    """Tests for the properties in OciInstance."""

    def test_instance_id(self, oci_instance):
        """Test the 'id' property."""
        assert oci_instance.id == oci_instance.instance_id

    def test_instance_name(self, oci_instance):
        """Test the 'name' property."""
        assert oci_instance.name == oci_instance.instance_id

    def test_instance_fault_domain(self, oci_instance):
        """Test the 'fault_domain' property."""
        # Set up mocked instance_data
        instance_data_mock = mock.Mock()
        instance_data_mock.fault_domain = "FAULT-DOMAIN-1"
        oci_instance.compute_client.get_instance.return_value = mock.Mock(data=instance_data_mock)

        # Initially, _fault_domain should be None
        assert oci_instance._fault_domain is None

        # When accessing fault_domain, it should be set
        assert oci_instance.fault_domain == "FAULT-DOMAIN-1"
        assert oci_instance._fault_domain == "FAULT-DOMAIN-1"

        # The cached value should be returned on subsequent accesses
        assert oci_instance.fault_domain == "FAULT-DOMAIN-1"


class TestOciInstanceVnicOperations:
    """Tests for VNIC operations in OciInstance."""

    @pytest.fixture(autouse=True)
    def setup_vnic_mocks(self, oci_instance):
        """Fixture to mock VNIC operations and wait_till_ready."""
        with mock.patch("pycloudlib.oci.instance.wait_till_ready", return_value=mock.Mock()):
            # Mock the behavior of network_client.list_vcns()
            vcn_mock = mock.Mock()
            vcn_mock.id = "vcn-id"
            oci_instance.network_client.list_vcns.return_value = mock.Mock(data=[vcn_mock])

            # Mock list_subnets to return an iterable of subnets
            subnet_mock = mock.Mock()
            subnet_mock.id = "subnet-id"
            oci_instance.network_client.list_subnets.return_value = mock.Mock(data=[subnet_mock])

            # Mock attach_vnic and get_vnic
            vnic_attachment_mock = mock.Mock()
            vnic_attachment_mock.vnic_id = "vnic-id"
            oci_instance.compute_client.attach_vnic.return_value = mock.Mock(data=vnic_attachment_mock)
            oci_instance.network_client.get_vnic.return_value = mock.Mock(data=mock.Mock(private_ip="192.168.1.10"))

            yield oci_instance

    @pytest.fixture
    def mock_vnic_pagination(self):
        """Mock oci.pagination.list_call_get_all_results_generator for VNIC attachments."""
        with mock.patch("oci.pagination.list_call_get_all_results_generator") as mock_pagination:
            yield mock_pagination

    def test_add_network_interface(self, setup_vnic_mocks):
        """Test add_network_interface() method."""
        oci_instance = setup_vnic_mocks

        # Call add_network_interface and check result
        result = oci_instance.add_network_interface()
        assert result == "192.168.1.10"
        oci_instance.compute_client.attach_vnic.assert_called_once()

    def test_remove_network_interface_success(self, oci_instance, mock_vnic_pagination):
        """Test remove_network_interface() method when the VNIC is found and successfully removed."""
        # Mock VNIC attachment list and get_vnic call
        vnic_attachment_mock = mock.Mock()
        vnic_attachment_mock.vnic_id = "vnic-id"
        vnic_attachment_mock.id = "attachment-id"
        vnic_data_mock = mock.Mock()
        vnic_data_mock.private_ip = "192.168.1.10"

        # Mock the pagination result to return the VNIC attachment
        mock_vnic_pagination.return_value = [vnic_attachment_mock]
        oci_instance.network_client.get_vnic.return_value = mock.Mock(data=vnic_data_mock)

        # Call remove_network_interface and check it removes the correct VNIC
        oci_instance.remove_network_interface("192.168.1.10")
        oci_instance.compute_client.detach_vnic.assert_called_once_with("attachment-id")

    def test_remove_network_interface_not_found(self, oci_instance, mock_vnic_pagination):
        """Test remove_network_interface() raises an error if the VNIC is not found."""
        # Mock an empty VNIC attachment list
        mock_vnic_pagination.return_value = []

        with pytest.raises(PycloudlibError, match="Network interface with ip_address=192.168.1.10 did not detach"):
            oci_instance.remove_network_interface("192.168.1.10")


class TestOciInstanceIp:
    def setup_mock_vnic(self, oci_instance, vnic_data_list):
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
        self,
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
        self.setup_mock_vnic(oci_instance, vnics_ordered)

        if expect_error:
            with pytest.raises(
                PycloudlibError,
                match="No public ipv4 address or ipv6 address found",
            ):
                _ = oci_instance.ip
        else:
            assert oci_instance.ip == expected_ip
