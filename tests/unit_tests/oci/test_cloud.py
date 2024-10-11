"""Tests for pycloudlib's OCI Cloud class."""

from unittest import mock

import oci
import pytest
import toml

from pycloudlib.config import Config
from pycloudlib.errors import (
    InstanceNotFoundError,
    PycloudlibException,
)
from pycloudlib.oci.cloud import OCI
from pycloudlib.oci.instance import OciInstance


@pytest.fixture
def oci_cloud():
    """
    Fixture for OCI Cloud class.
    
    This fixture mocks the oci.config.validate_config function to not raise an error. It also
    mocks the oci.core.ComputeClient and oci.core.VirtualNetworkClient classes to return mock
    instances of the clients. The fixture also mocks the pycloudlib.config.parse_config function
    to return a Config object with the default values from the pycloudlib.toml.template file.
    """
    oci_config = {
        "user": "ocid1.user.oc1..example",
        "fingerprint": "mock-fingerprint",
        "key_file": "/path/to/key",
        "tenancy": "ocid1.tenancy.oc1..example",
        "region": "us-phoenix-1",
    }

    with mock.patch(
        "pycloudlib.oci.cloud.oci.config.validate_config",
        return_value=oci_config,
    ), mock.patch(
        "pycloudlib.oci.cloud.oci.core.ComputeClient"
    ) as mock_compute_client_class, mock.patch(
        "pycloudlib.oci.cloud.oci.core.VirtualNetworkClient"
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
        oci_cloud = OCI(
            "test-instance",
            timestamp_suffix=True,
            availability_domain="PHX-AD-1",
            compartment_id="test-compartment-id",
            region="us-phoenix-1",
            config_dict=oci_config,
        )

        oci_cloud._log = mock.MagicMock()

        # Assign the mocked clients to the instance
        oci_cloud.compute_client = mock_compute_client
        oci_cloud.network_client = mock_network_client

        yield oci_cloud


class TestOciInit:
    """Tests for OCI Cloud __init__."""

    def test_init_valid(self, oci_cloud):
        """Test __init__ with valid parameters."""
        # Ensure that oci.config.from_file is mocked with a valid configuration
        assert oci_cloud.availability_domain == "PHX-AD-1"
        assert oci_cloud.compartment_id == "test-compartment-id"
        assert oci_cloud.region == "us-phoenix-1"

    def test_init_invalid_config(self):
        """Test __init__ with invalid OCI configuration."""
        with mock.patch("oci.config.from_file", side_effect=oci.exceptions.InvalidConfig):
            with pytest.raises(ValueError, match="Config dict is invalid"):
                OCI(tag="test-instance", config_dict={"invalid": "config"})


class TestOciImages:
    """Tests for OCI Cloud image-related functions."""

    def test_delete_image(self, oci_cloud):
        """Test delete_image method."""
        oci_cloud.delete_image("test-image-id")
        oci_cloud.compute_client.delete_image.assert_called_once_with("test-image-id")

    def test_released_image(self, oci_cloud):
        """Test released_image calls daily_image."""
        with mock.patch.object(oci_cloud, "daily_image", return_value="image-id"):
            assert oci_cloud.released_image("20.04") == "image-id"

    def test_daily_image(self, oci_cloud):
        """Test daily_image method for Ubuntu images."""
        oci_cloud.compute_client.list_images.return_value = mock.Mock(
            data=[mock.Mock(display_name="Canonical Ubuntu 20.04", id="image-id")]
        )
        assert oci_cloud.daily_image("20.04") == "image-id"
        oci_cloud.compute_client.list_images.assert_called_once_with(
            "test-compartment-id",
            operating_system="Canonical Ubuntu",
            operating_system_version="20.04",
            sort_by="TIMECREATED",
            sort_order="DESC",
        )

    def test_invalid_release(self, oci_cloud):
        """Test daily_image with an invalid release version."""
        with pytest.raises(ValueError, match="Invalid release"):
            oci_cloud.daily_image("invalid-release")

    def test_image_serial_not_implemented(self, oci_cloud):
        """Test image_serial raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            oci_cloud.image_serial("image-id")

    def test_get_image_id_from_name(self, oci_cloud):
        """Test get_image_id_from_name method."""
        oci_cloud.compute_client.list_images.return_value = mock.Mock(
            data=[mock.Mock(id="image-id")]
        )
        assert oci_cloud.get_image_id_from_name("test-image") == "image-id"
        oci_cloud.compute_client.list_images.assert_called_once_with(
            "test-compartment-id", display_name="test-image"
        )

    def test_get_image_id_from_name_not_found(self, oci_cloud):
        """Test get_image_id_from_name raises error when no image is found."""
        oci_cloud.compute_client.list_images.return_value = mock.Mock(data=[])
        with pytest.raises(PycloudlibException, match="Image with name test-image not found"):
            oci_cloud.get_image_id_from_name("test-image")

    @mock.patch("pycloudlib.oci.cloud.wait_till_ready")
    def test_snapshot(self, mock_wait_till_ready, oci_cloud):
        """Test snapshot method."""
        instance = mock.Mock()
        oci_cloud.compute_client.create_image.return_value = mock.Mock(
            data=mock.Mock(id="image-id")
        )
        mock_wait_till_ready.return_value = mock.Mock()

        oci_cloud.snapshot(instance, clean=True, name="snapshot-name")
        instance.clean.assert_called_once()
        oci_cloud.compute_client.create_image.assert_called_once()


class TestOciInstances:
    """Tests for OCI Cloud instance-related functions."""

    @mock.patch("oci.config.from_file")
    def test_get_instance(self, mock_from_file, oci_cloud):
        """Test get_instance method with valid instance."""
        valid_config = {
            "user": "ocid1.user.oc1..example",
            "fingerprint": "mock-fingerprint",
            "key_file": "/path/to/key",
            "tenancy": "ocid1.tenancy.oc1..example",
            "region": "us-phoenix-1",
        }
        # Mock oci.config.from_file to return the valid configuration
        mock_from_file.return_value = valid_config

        oci_cloud.compute_client.get_instance.return_value = mock.Mock()
        instance = oci_cloud.get_instance("test-instance-id", username="opc")
        assert isinstance(instance, OciInstance)
        oci_cloud.compute_client.get_instance.assert_called_once_with("test-instance-id")

    @mock.patch("oci.config.from_file")
    def test_get_instance_not_found(self, mock_from_file, oci_cloud):
        """Test get_instance raises InstanceNotFoundError when instance does not exist."""
        valid_config = {
            "user": "ocid1.user.oc1..example",
            "fingerprint": "mock-fingerprint",
            "key_file": "/path/to/key",
            "tenancy": "ocid1.tenancy.oc1..example",
            "region": "us-phoenix-1",
        }
        mock_from_file.return_value = valid_config

        oci_cloud.compute_client.get_instance.side_effect = oci.exceptions.ServiceError(
            status=404,
            code="NotFound",
            message="Instance not found",
            headers={},
            target_service=None,
        )
        with pytest.raises(InstanceNotFoundError):
            oci_cloud.get_instance("test-instance-id")

    @mock.patch("pycloudlib.oci.cloud.wait_till_ready")
    def test_launch_instance(self, mock_wait_till_ready, oci_cloud):
        """Test launch method with valid inputs."""
        # mock the key pair
        oci_cloud.key_pair = mock.Mock()
        oci_cloud.key_pair.public_key_content = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC"
        oci_cloud.compute_client.launch_instance.return_value = mock.Mock(
            data=mock.Mock(id="instance-id")
        )
        oci_cloud.get_instance = mock.Mock(return_value=mock.Mock())
        # mock pycloudlib.oci.utils.get_subnet_id
        with mock.patch("pycloudlib.oci.cloud.get_subnet_id") as m_subnet:
            m_subnet.return_value = "subnet-id"
            instance = oci_cloud.launch("test-image-id", instance_type="VM.Standard2.1")
        oci_cloud.compute_client.launch_instance.assert_called_once()
        assert instance is not None
        m_subnet.assert_called_once()
        oci_cloud.get_instance.assert_called_once()

    def test_launch_instance_invalid_image(self, oci_cloud):
        """Test launch method raises ValueError when no image_id is provided."""
        with pytest.raises(ValueError, match="launch requires image_id param"):
            oci_cloud.launch(None)
