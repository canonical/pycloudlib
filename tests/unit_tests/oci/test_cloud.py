from unittest import mock
import oci
import pytest

from pycloudlib.oci.cloud import OCI
from pycloudlib.errors import InstanceNotFoundError, PycloudlibException, CloudSetupError
from pycloudlib.oci.instance import OciInstance


class FakeOCI(OCI):
    """Fake OCI Cloud Class that doesn't load config or make requests during __init__."""

    # pylint: disable=super-init-not-called
    def __init__(self, *_, **__):
        """Fake __init__ that sets mocks for needed variables."""
        self._log = mock.MagicMock()
        self.config = {}
        self.key_pair = mock.Mock()
        self.created_instances = []
        self.created_images = []
        self.compartment_id = "test-compartment-id"
        self.availability_domain = "PHX-AD-1"
        self.region = "us-phoenix-1"
        self.vcn_name = "test-vcn"
        # Mock OCI clients
        self.compute_client = mock.Mock()
        self.network_client = mock.Mock()
        self.oci_config = {
            "user": "ocid1.user.oc1..example",
            "fingerprint": "mock-fingerprint",
            "key_file": "/path/to/key",
            "tenancy": "ocid1.tenancy.oc1..example",
            "region": "us-phoenix-1",
        }

@pytest.fixture
def mock_oci():
    yield FakeOCI()

class TestOciInit:
    """Tests for OCI Cloud __init__."""

    def test_init_valid(self):
        """Test __init__ with valid parameters."""
        # Ensure that oci.config.from_file is mocked with a valid configuration
        valid_config = {
            "user": "ocid1.user.oc1..example",
            "fingerprint": "mock-fingerprint",
            "key_file": "/path/to/key",
            "tenancy": "ocid1.tenancy.oc1..example",
            "region": "us-phoenix-1"
        }
        with mock.patch("pycloudlib.oci.cloud.oci.config.from_file", return_value=valid_config
            ), mock.patch("pycloudlib.oci.cloud.oci.config.validate_config", return_value=True):
            oci_cloud = OCI(
                tag="test-instance",
                timestamp_suffix=True,
                availability_domain="PHX-AD-1",
                compartment_id="test-compartment-id",
            )
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

    def test_delete_image(self, mock_oci):
        """Test delete_image method."""
        mock_oci.delete_image("test-image-id")
        mock_oci.compute_client.delete_image.assert_called_once_with("test-image-id")

    def test_released_image(self, mock_oci):
        """Test released_image calls daily_image."""
        with mock.patch.object(mock_oci, "daily_image", return_value="image-id"):
            assert mock_oci.released_image("20.04") == "image-id"

    def test_daily_image(self, mock_oci):
        """Test daily_image method for Ubuntu images."""
        mock_oci.compute_client.list_images.return_value = mock.Mock(
            data=[mock.Mock(display_name="Canonical Ubuntu 20.04", id="image-id")]
        )
        assert mock_oci.daily_image("20.04") == "image-id"
        mock_oci.compute_client.list_images.assert_called_once_with(
            "test-compartment-id",
            operating_system="Canonical Ubuntu",
            operating_system_version="20.04",
            sort_by="TIMECREATED",
            sort_order="DESC",
        )

    def test_invalid_release(self, mock_oci):
        """Test daily_image with an invalid release version."""
        with pytest.raises(ValueError, match="Invalid release"):
            mock_oci.daily_image("invalid-release")

    def test_image_serial_not_implemented(self, mock_oci):
        """Test image_serial raises NotImplementedError."""
        with pytest.raises(NotImplementedError):
            mock_oci.image_serial("image-id")

    def test_get_image_id_from_name(self, mock_oci):
        """Test get_image_id_from_name method."""
        mock_oci.compute_client.list_images.return_value = mock.Mock(
            data=[mock.Mock(id="image-id")]
        )
        assert mock_oci.get_image_id_from_name("test-image") == "image-id"
        mock_oci.compute_client.list_images.assert_called_once_with(
            "test-compartment-id", display_name="test-image"
        )

    def test_get_image_id_from_name_not_found(self, mock_oci):
        """Test get_image_id_from_name raises error when no image is found."""
        mock_oci.compute_client.list_images.return_value = mock.Mock(data=[])
        with pytest.raises(PycloudlibException, match="Image with name test-image not found"):
            mock_oci.get_image_id_from_name("test-image")

    @mock.patch("pycloudlib.oci.cloud.wait_till_ready")
    def test_snapshot(self, mock_wait_till_ready, mock_oci):
        """Test snapshot method."""
        instance = mock.Mock()
        mock_oci.compute_client.create_image.return_value = mock.Mock(data=mock.Mock(id="image-id"))
        mock_oci.compute_client.get_image.return_value = mock.Mock(data=mock.Mock())
        mock_wait_till_ready.return_value = mock.Mock()

        mock_oci.snapshot(instance, clean=True, name="snapshot-name")
        instance.clean.assert_called_once()
        mock_oci.compute_client.create_image.assert_called_once()
        mock_oci.compute_client.get_image.assert_called_once()

class TestOciInstances:
    """Tests for OCI Cloud instance-related functions."""

    @mock.patch("oci.config.from_file")
    def test_get_instance(self, mock_from_file, mock_oci):
        """Test get_instance method with valid instance."""
        valid_config = {
            "user": "ocid1.user.oc1..example",
            "fingerprint": "mock-fingerprint",
            "key_file": "/path/to/key",
            "tenancy": "ocid1.tenancy.oc1..example",
            "region": "us-phoenix-1"
        }
        # Mock oci.config.from_file to return the valid configuration
        mock_from_file.return_value = valid_config

        mock_oci.compute_client.get_instance.return_value = mock.Mock()
        instance = mock_oci.get_instance("test-instance-id", username="opc")
        assert isinstance(instance, OciInstance)
        mock_oci.compute_client.get_instance.assert_called_once_with("test-instance-id")

    @mock.patch("oci.config.from_file")
    def test_get_instance_not_found(self, mock_from_file, mock_oci):
        """Test get_instance raises InstanceNotFoundError when instance does not exist."""
        valid_config = {
            "user": "ocid1.user.oc1..example",
            "fingerprint": "mock-fingerprint",
            "key_file": "/path/to/key",
            "tenancy": "ocid1.tenancy.oc1..example",
            "region": "us-phoenix-1"
        }
        mock_from_file.return_value = valid_config

        mock_oci.compute_client.get_instance.side_effect = oci.exceptions.ServiceError(
            status=404, code="NotFound", message="Instance not found", headers={}, target_service=None
        )
        with pytest.raises(InstanceNotFoundError):
            mock_oci.get_instance("test-instance-id")

    @mock.patch("pycloudlib.oci.cloud.wait_till_ready")
    def test_launch_instance(self, mock_wait_till_ready, mock_oci):
        """Test launch method with valid inputs."""
        mock_oci.key_pair.public_key_content = "ssh-public-key"
        mock_oci.compute_client.launch_instance.return_value = mock.Mock(data=mock.Mock(id="instance-id"))
        mock_oci.get_instance = mock.Mock(return_value=mock.Mock())

        instance = mock_oci.launch("test-image-id", instance_type="VM.Standard2.1")
        mock_oci.compute_client.launch_instance.assert_called_once()
        assert instance is not None
        mock_oci.get_instance.assert_called_once()

    def test_launch_instance_invalid_image(self, mock_oci):
        """Test launch method raises ValueError when no image_id is provided."""
        with pytest.raises(ValueError, match="launch requires image_id param"):
            mock_oci.launch(None)
