"""Tests for pycloudlib's OCI Instance class."""

from unittest import mock

import pytest
import toml

from pycloudlib.config import Config
from pycloudlib.errors import PycloudlibError
from pycloudlib.oci.instance import OciInstance


@pytest.fixture
def oci_instance():
    """
    Fixture for OciInstance class.

    This fixture mocks the OCI configuration and the ComputeClient and VirtualNetworkClient classes
    so that a proper OciInstance object can be created and used for each test. The fixture also
    mocks the pycloudlib.config.parse_config function to return a Config object with the default
    values from the pycloudlib.toml.template file.
    """
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
    ) as mock_network_client_class, mock.patch(
        "pycloudlib.config.parse_config"
    ) as mock_parse_config:
        # mock loading the config file by just reading in the template, which we know will exist
        mock_parse_config.return_value = toml.load("pycloudlib.toml.template", _dict=Config)

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
        instance.compute_client.get_instance.return_value = mock.Mock(data=instance_data_mock)

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

        with mock.patch(
            "pycloudlib.oci.instance.oci.config.from_file"
        ) as mock_from_file, mock.patch(
            "pycloudlib.oci.instance.oci.core.ComputeClient"
        ) as mock_compute_client_class, mock.patch(
            "pycloudlib.oci.instance.oci.core.VirtualNetworkClient"
        ) as mock_network_client_class:
            # Mock the config and valid configuration details
            mock_from_file.return_value = {
                "user": "ocid1.user.oc1..exampleuniqueID",
                "fingerprint": "fingerprint",
                "key_file": "/path/to/key",
                "tenancy": "ocid1.tenancy.oc1..exampleuniqueID",
                "region": "us-phoenix-1",
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
                oci_config=None,
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
        """Fixture to mock VNIC operations and wait_till_ready.

        This super simple fixture mocks the behavior of the network_client and compute_client
        to allow for basic VNIC operations to be tested.
        """
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
            oci_instance.compute_client.attach_vnic.return_value = mock.Mock(
                data=vnic_attachment_mock
            )
            oci_instance.network_client.get_vnic.return_value = mock.Mock(
                data=mock.Mock(private_ip="192.168.1.10")
            )

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

        with pytest.raises(
            PycloudlibError,
            match="Network interface with ip_address=192.168.1.10 did not detach",
        ):
            oci_instance.remove_network_interface("192.168.1.10")

