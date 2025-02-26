"""Tests for pycloudlib's OCI Cloud class."""

from textwrap import dedent
from typing import List
from unittest import mock

import oci
import pytest
import toml

from pycloudlib.errors import (
    InstanceNotFoundError,
    InvalidTagNameError,
    PycloudlibException,
)
from pycloudlib.oci.cloud import OCI
from pycloudlib.oci.instance import OciInstance


@pytest.fixture
def oci_mock():
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
    ) as mock_network_client_class:
        # Instantiate mocked clients
        mock_compute_client = mock.Mock()
        mock_network_client = mock.Mock()
        mock_compute_client_class.return_value = mock_compute_client
        mock_network_client_class.return_value = mock_network_client

        yield mock_compute_client, mock_network_client, oci_config


@pytest.fixture
def oci_cloud(oci_mock, tmp_path):
    """
    Fixture for OCI Cloud class.

    This fixture mocks the oci.config.validate_config function to not raise an error. It also
    mocks the oci.core.ComputeClient and oci.core.VirtualNetworkClient classes to return mock
    instances of the clients.
    """
    pycloudlib_config = tmp_path / "pyproject.toml"
    pycloudlib_config.write_text("[oci]\n")

    mock_compute_client, mock_network_client, oci_config = oci_mock

    # Create instance
    oci_cloud = OCI(
        "test-instance",
        timestamp_suffix=True,
        config_file=pycloudlib_config,
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


OCI_PYCLOUDLIB_CONFIG = """\
[oci]
availability_domain = "PYCL-AD-1"
compartment_id = "pycloudlib-compartment-id"
region = "pycl-pheonix-1"
"""


@pytest.mark.mock_ssh_keys
class TestOciInit:
    """Tests for OCI Cloud __init__."""

    def test_init_valid(self, oci_cloud):
        """Test __init__ with valid parameters matches .oci/config over pycloudlib.toml."""
        assert oci_cloud.availability_domain == "PHX-AD-1"
        assert oci_cloud.compartment_id == "test-compartment-id"
        assert oci_cloud.region == "us-phoenix-1"

    def test_init_invalid_config(self, tmp_path):
        """Test __init__ with invalid OCI configuration raises ValueError."""
        pycloudlib_config = tmp_path / "pyproject.toml"
        pycloudlib_config.write_text(OCI_PYCLOUDLIB_CONFIG)
        with mock.patch("oci.config.from_file", side_effect=oci.exceptions.InvalidConfig):
            with pytest.raises(ValueError, match="Config dict is invalid"):
                OCI(
                    tag="test-instance",
                    config_file=pycloudlib_config,
                    config_dict={"invalid": "config"},
                )

    @pytest.mark.parametrize(
        ["vcn_name"],
        [
            pytest.param(
                "test-vcn",
                id="VCN entry provided",
            ),
            pytest.param(
                None,
                id="No VCN entry provided",
            ),
        ],
    )
    def test_config_toml(self, tmp_path, vcn_name, oci_mock):
        config_toml = dedent("""\
            [oci]
            availability_domain = "PYCL-AD-1"
            compartment_id = "pycloudlib-compartment-id"
            region = "pycl-pheonix-1"
        """)

        if vcn_name:
            config_toml += 'vcn_name = "test-vcn"\n'

        pycloudlib_config = tmp_path / "pyproject.toml"
        pycloudlib_config.write_text(config_toml)

        _, _, oci_config = oci_mock

        test_inst = OCI(
            tag="test-instance",
            config_file=pycloudlib_config,
            config_dict=oci_config,
        )

        assert test_inst.availability_domain == "PYCL-AD-1"
        assert test_inst.compartment_id == "pycloudlib-compartment-id"
        assert test_inst.region == "pycl-pheonix-1"
        assert test_inst.vcn_name == vcn_name

    def test_loading_from_env_vars(self, monkeypatch, oci_mock, tmp_path):
        oci_config = oci_mock[2]
        oci_config["key_file"] = None

        # create fake config file
        oci_config_file = tmp_path / "oci_config"
        oci_config_file.write_text(toml.dumps(oci_config))

        monkeypatch.setenv("PYCLOUDLIB_OCI_CONFIG_FILE_PATH", str(tmp_path / "oci_config"))
        monkeypatch.setenv("PYCLOUDLIB_OCI_KEY_FILE_PATH", "/PATH_FROM_ENV/TO/KEY")

        pycloudlib_config = tmp_path / "pyproject.toml"
        pycloudlib_config.write_text(OCI_PYCLOUDLIB_CONFIG)

        config_with_key_file = oci_config.copy()
        config_with_key_file["key_file"] = "/path/to/key"
        test_inst = OCI(tag="test-instance", config_file=pycloudlib_config)

        assert test_inst.oci_config["key_file"] == "/PATH_FROM_ENV/TO/KEY"


@pytest.mark.mock_ssh_keys
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


@pytest.mark.mock_ssh_keys
class TestOciInstances:
    """Tests for OCI Cloud instance-related functions."""

    def test_get_instance(self, oci_cloud):
        """Test get_instance method with valid instance."""

        oci_cloud.compute_client.get_instance.return_value = mock.Mock()
        instance = oci_cloud.get_instance("test-instance-id", username="opc")
        assert isinstance(instance, OciInstance)
        oci_cloud.compute_client.get_instance.assert_called_once_with("test-instance-id")

    def test_get_instance_not_found(self, oci_cloud):
        """Test get_instance raises InstanceNotFoundError when instance does not exist."""

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
    def test_launch_instance(self, mock_wait_till_ready, oci_cloud, oci_mock):
        """Test launch method with valid inputs."""
        _, mock_network_client, _ = oci_mock

        # mock the key pair
        oci_cloud.key_pair = mock.Mock(public_key_config="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC")
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

        # assert that subnet_name is obtained properly
        mock_network_client.list_subnets.return_value = mock.Mock(data=[mock.Mock(id="subnet-id")])
        instance = oci_cloud.launch(
            "test-image-id", instance_type="VM.Standard2.1", subnet_name="subnet-name"
        )
        mock_network_client.list_subnets.assert_called_once()
        assert oci_cloud.get_instance.call_count == 2

        # Ensure when a subnet_id is directly passed to launch
        # no functions to obtain a subnet-id are called.
        with mock.patch("pycloudlib.oci.cloud.get_subnet_id") as m_subnet_id, \
            mock.patch("pycloudlib.oci.cloud.get_subnet_id_by_name") as m_subnet_name:
            instance = oci_cloud.launch(
                "test-image-id", instance_type="VM.Standard2.1", subnet_id="subnet-id"
            )
            m_subnet_name.assert_not_called()
            m_subnet_id.assert_not_called()
        
        # The first arg is the LaunchInstanceDetails object
        args, _ = oci_cloud.compute_client.launch_instance.call_args
        launch_instance_details = args[0]
        assert launch_instance_details.subnet_id == "subnet-id"
        assert oci_cloud.get_instance.call_count == 3

    
    @mock.patch("pycloudlib.oci.cloud.wait_till_ready")
    def test_launch_custom_metadata(self, mock_wait_till_ready, oci_cloud):
        """Test launch method with valid inputs."""
        # mock the key pair
        oci_cloud.key_pair = mock.Mock(public_key_config="ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAABgQC")
        oci_cloud.compute_client.launch_instance.return_value = mock.Mock(
            data=mock.Mock(id="instance-id")
        )
        oci_cloud.get_instance = mock.Mock(return_value=mock.Mock())

        # Ensure metdata gets combined with defaults
        metadata = {"metadata_key": "metadata_value"}
        default_metadata = {"ssh_authorized_keys": oci_cloud.key_pair.public_key_content}
        expected_metadata = {**default_metadata, **metadata}
        instance = oci_cloud.launch(
           "test-image-id", instance_type="VM.Standard2.1", subnet_id="subnet-id",
            metadata=metadata,
        )
        
        # The first arg is the LaunchInstanceDetails object
        args, _ = oci_cloud.compute_client.launch_instance.call_args
        launch_instance_details = args[0]
        assert launch_instance_details.metadata == expected_metadata
        assert instance is not None
        oci_cloud.get_instance.assert_called_once()
        
        # Ensure default_metadata values can be overridden
        metadata = {"ssh_authorized_keys": "override", "metadata_key": "metadata_value"}
        expected_metadata = {**default_metadata, **metadata}
        instance = oci_cloud.launch(
           "test-image-id", instance_type="VM.Standard2.1", subnet_id="subnet-id",
            metadata=metadata,
        )
        
        # The first arg is the LaunchInstanceDetails object
        args, _ = oci_cloud.compute_client.launch_instance.call_args
        launch_instance_details = args[0]
        assert launch_instance_details.metadata == expected_metadata
        assert oci_cloud.get_instance.call_count == 2
        

    def test_launch_instance_invalid_image(self, oci_cloud):
        """Test launch method raises ValueError when no image_id is provided."""
        with pytest.raises(ValueError, match="launch requires image_id param"):
            oci_cloud.launch(None)


@pytest.mark.mock_ssh_keys
class TestBaseCloudOverrides:
    rule1 = "Must be between 1 and 255 characters long"
    rule2 = "Must not have leading or trailing whitespace"

    @pytest.mark.parametrize(
        "tag, rules_failed",
        [
            ("tag123", []),
            ("TAG", []),
            ("TAG-", []),
            ("-tag_", []),
            ("-", []),
            ("x" * 64, []),
            ("", [rule1]),
            (" ", [rule2]),
            (" X", [rule2]),
            ("X ", [rule2]),
            (" X ", [rule2]),
            ("x" * 63, []),
            ("x", []),
            ("t a_g", []),
            ("t.a.g", []),
            ("X" * 255, []),
            ("X" * 256, [rule1]),
            ("!@#$%^&*()", []),
        ],
    )
    def test_validate_tag(self, oci_cloud, tag: str, rules_failed: List[str]):
        """
        Test Oracle's implementation of the _validate_tag method.
        """
        if len(rules_failed) == 0:
            # test that no exception is raised
            oci_cloud._validate_tag(tag)
        else:
            with pytest.raises(InvalidTagNameError) as exc_info:
                oci_cloud._validate_tag(tag)
            assert tag in str(exc_info.value)
            for rule in rules_failed:
                assert rule in str(exc_info.value)
