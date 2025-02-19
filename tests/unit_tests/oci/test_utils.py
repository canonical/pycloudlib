import pytest
from unittest.mock import MagicMock, mock_open, patch
from pycloudlib.oci.utils import (
    get_subnet_id,
    get_subnet_id_by_name,
    parse_oci_config_from_env_vars,
    _load_and_preprocess_oci_toml_file,
    generate_create_vnic_details,
)
from pycloudlib.types import NetworkingConfig, NetworkingType
from pycloudlib.errors import PycloudlibError
from oci.retry import DEFAULT_RETRY_STRATEGY  # pylint: disable=E0611,E0401
import os
import toml


class TestGetSubnetId:
    @pytest.fixture
    @patch("pycloudlib.oci.utils.DEFAULT_RETRY_STRATEGY", None)
    def setup_environment(self):
        """
        Set up the test environment.

        This fixture is called before each test function execution.

        It mocks the network client and sets up the compartment ID and availability domain.
        """
        network_client = MagicMock()
        compartment_id = "compartment_id"
        availability_domain = "availability_domain"
        return network_client, compartment_id, availability_domain

    def test_get_subnet_id_fails_with_vcn_name_not_found(self, setup_environment):
        """Test get_subnet_id fails when VCN name is not found."""
        network_client, compartment_id, availability_domain = setup_environment
        network_client.list_vcns.return_value.data = []
        with pytest.raises(PycloudlibError, match="Unable to determine vcn name"):
            get_subnet_id(
                network_client=network_client,
                compartment_id=compartment_id,
                availability_domain=availability_domain,
                vcn_name="vcn_name",
            )

    def test_get_subnet_id_fails_with_multiple_vcns_found(self, setup_environment):
        """Test get_subnet_id fails when multiple VCNs with the same name are found."""
        network_client, compartment_id, availability_domain = setup_environment
        network_client.list_vcns.return_value.data = [MagicMock(), MagicMock()]
        with pytest.raises(PycloudlibError, match="Found multiple vcns with name"):
            get_subnet_id(
                network_client=network_client,
                compartment_id=compartment_id,
                availability_domain=availability_domain,
                vcn_name="vcn_name",
            )

    def test_get_subnet_id_fails_with_no_vcns_found(self, setup_environment):
        """Test get_subnet_id fails when no VCNs are found."""
        network_client, compartment_id, availability_domain = setup_environment
        network_client.list_vcns.return_value.data = []
        with pytest.raises(PycloudlibError, match="No VCNs found in compartment"):
            get_subnet_id(
                network_client=network_client,
                compartment_id=compartment_id,
                availability_domain=availability_domain,
            )

    def test_get_subnet_id_fails_with_no_suitable_subnet_found(self, setup_environment):
        """Test get_subnet_id fails when no suitable subnet is found."""
        network_client, compartment_id, availability_domain = setup_environment
        vcn = MagicMock()
        vcn.id = "vcn_id"
        vcn.display_name = "vcn_name"
        network_client.list_vcns.return_value.data = [vcn]
        network_client.list_subnets.return_value.data = []
        with pytest.raises(PycloudlibError, match="Unable to find suitable subnet in VCN"):
            get_subnet_id(
                network_client=network_client,
                compartment_id=compartment_id,
                availability_domain=availability_domain,
            )

    def test_get_subnet_id_fails_with_private_subnet(self, setup_environment):
        """Test that passing private=False ignores private subnets."""
        network_client, compartment_id, availability_domain = setup_environment
        vcn = MagicMock()
        vcn.id = "vcn_id"
        vcn.display_name = "vcn_name"
        network_client.list_vcns.return_value.data = [vcn]
        subnet = MagicMock()
        subnet.prohibit_internet_ingress = True
        network_client.list_subnets.return_value.data = [subnet]
        with pytest.raises(PycloudlibError, match="Unable to find suitable subnet"):
            get_subnet_id(
                network_client=network_client,
                compartment_id=compartment_id,
                availability_domain=availability_domain,
                networking_config=NetworkingConfig(private=False),
            )

    def test_get_subnet_id_fails_with_different_availability_domain(self, setup_environment):
        """Test get_subnet_id fails when the subnet is in a different availability domain."""
        network_client, compartment_id, availability_domain = setup_environment
        vcn = MagicMock()
        vcn.id = "vcn_id"
        vcn.display_name = "vcn_name"
        network_client.list_vcns.return_value.data = [vcn]
        subnet = MagicMock()
        subnet.prohibit_internet_ingress = False
        subnet.availability_domain = "different_availability_domain"
        network_client.list_subnets.return_value.data = [subnet]
        with pytest.raises(PycloudlibError, match="Unable to find suitable subnet in VCN"):
            get_subnet_id(
                network_client=network_client,
                compartment_id=compartment_id,
                availability_domain=availability_domain,
            )

    def test_get_subnet_id_suceeds_without_vcn_name(self, setup_environment):
        """Test get_subnet_id suceeds without specifying a VCN name."""
        network_client, compartment_id, availability_domain = setup_environment
        vcn1 = MagicMock()
        vcn1.id = "vcn1_id"
        vcn1.display_name = "vcn1_name"
        vcn2 = MagicMock()
        vcn2.id = "vcn2_id"
        vcn2.display_name = "vcn2_name"
        network_client.list_vcns.return_value.data = [vcn1, vcn2]
        subnet = MagicMock()
        subnet.prohibit_internet_ingress = False
        subnet.availability_domain = None
        subnet.id = "subnet_id"
        network_client.list_subnets.return_value.data = [subnet]
        result = get_subnet_id(
            network_client=network_client,
            compartment_id=compartment_id,
            availability_domain=availability_domain,
        )
        assert result == "subnet_id"
        # Ensure that list_subnets is called with the first VCN's ID, not the second
        network_client.list_subnets.assert_called_with(
            compartment_id=compartment_id,
            vcn_id="vcn1_id",
            retry_strategy=DEFAULT_RETRY_STRATEGY,
        )

    def test_get_subnet_id_suceeds_with_vcn_name(self, setup_environment):
        """Test get_subnet_id suceeds with specifying a VCN name."""
        network_client, compartment_id, availability_domain = setup_environment
        vcn = MagicMock()
        vcn.id = "vcn_id"
        vcn.display_name = "vcn_name"
        network_client.list_vcns.return_value.data = [vcn]
        subnet = MagicMock()
        subnet.prohibit_internet_ingress = False
        subnet.availability_domain = None
        subnet.id = "subnet_id"
        network_client.list_subnets.return_value.data = [subnet]
        result = get_subnet_id(
            network_client=network_client,
            compartment_id=compartment_id,
            availability_domain=availability_domain,
            vcn_name="vcn_name",
        )
        assert result == "subnet_id"
        # Ensure that list_subnets is called with the specified VCN's ID
        network_client.list_subnets.assert_called_with(
            compartment_id=compartment_id,
            vcn_id="vcn_id",
            retry_strategy=DEFAULT_RETRY_STRATEGY,
        )

    def test_get_subnet_id_succeeds_with_private_subnet(self, setup_environment):
        """Test that passing private=True picks a private subnet if available."""
        network_client, compartment_id, availability_domain = setup_environment
        vcn = MagicMock()
        vcn.id = "vcn_id"
        vcn.display_name = "vcn_name"
        network_client.list_vcns.return_value.data = [vcn]
        private_subnet = MagicMock()
        private_subnet.prohibit_internet_ingress = True
        private_subnet.availability_domain = None
        private_subnet.id = "private_subnet_id"
        public_subnet = MagicMock()
        public_subnet.prohibit_internet_ingress = False
        public_subnet.availability_domain = None
        public_subnet.id = "public_subnet_id"
        network_client.list_subnets.return_value.data = [public_subnet, private_subnet]
        result = get_subnet_id(
            network_client=network_client,
            compartment_id=compartment_id,
            availability_domain=availability_domain,
            networking_config=NetworkingConfig(private=True),
        )
        assert result == "private_subnet_id"


class TestConfigPathFromEnv:
    @pytest.fixture(autouse=True)
    def clear_env(self):
        """Ensure environment variables are cleared before each test."""
        with patch.dict(os.environ, {}, clear=True):
            yield

    def test_no_env_var_returns_none(self):
        """Should return None if PYCLOUDLIB_OCI_CONFIG_FILE_PATH is not set."""
        assert parse_oci_config_from_env_vars() is None

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data="invalid toml data",
    )
    @patch(
        "toml.loads",
        side_effect=toml.TomlDecodeError("Invalid TOML", "invalid toml data", 0),
    )
    def test_invalid_config_file_raises_error(
        self,
        mock_toml_load,
        mock_file,
    ):
        """Should raise PycloudlibError when the config file is invalid."""
        with patch.dict(os.environ, {"PYCLOUDLIB_OCI_CONFIG_FILE_PATH": "/path/to/config"}):
            with pytest.raises(PycloudlibError, match="Failed to load OCI config dict"):
                parse_oci_config_from_env_vars()

        mock_file.assert_called_once_with("/path/to/config", encoding="utf-8")
        mock_toml_load.assert_called_once()

    @pytest.mark.parametrize(
        "key_file_entry_in_config, has_header, key_file_env_var",
        [
            pytest.param(
                None,
                True,
                None,
                id="no_key_file_with_header",
            ),
            pytest.param(
                None,
                True,
                "/custom/key/path",
                id="no_key_file_with_header_env_var",
            ),
            pytest.param(None, False, None, id="no_key_file_no_header"),
            pytest.param(
                None,
                False,
                "/custom/key/path",
                id="no_key_file_no_header_env_var",
            ),
            pytest.param(
                "/i/should/be/overridden",
                True,
                None,
                id="key_file_in_config_with_header",
            ),
            pytest.param(
                "/i/should_be/overridden",
                True,
                "/custom/key/path",
                id="key_file_in_config_with_header_env_var",
            ),
            pytest.param(
                "/i/should_be/overridden",
                False,
                None,
                id="key_file_in_config_no_header",
            ),
            pytest.param(
                "/i/should_be/overridden",
                False,
                "/custom/key/path",
                id="key_file_in_config_no_header_env_var",
            ),
        ],
    )
    def test_key_file_path_overrides(
        self,
        caplog,
        tmp_path,
        key_file_env_var,
        has_header,
        key_file_entry_in_config,
    ):
        """
        This tests the usage of the PYCLOUDLIB_OCI_KEY_FILE_PATH environment variable to either
        override or add the key_file path to the config dict.

        Test cases:
            1. key_file entry not present in the config file
            2. key_file entry present in the config file
        """

        toml_str = f"""
        {'[DEFAULT]' if has_header else ''}
        region=us-phoenix-1
        tenancy=ocid1.tenancy.oc1..aaaaaaa
        """

        config_file = tmp_path / "config.toml"
        with open(config_file, encoding="utf-8", mode="w") as f:
            f.write(toml_str)
            if key_file_entry_in_config:
                f.write(f'key_file="{key_file_entry_in_config}"\n')

        env_vars = {"PYCLOUDLIB_OCI_CONFIG_FILE_PATH": str(config_file)}
        if key_file_env_var:
            env_vars["PYCLOUDLIB_OCI_KEY_FILE_PATH"] = key_file_env_var

        with patch.dict(
            os.environ,
            env_vars,
        ):
            result = parse_oci_config_from_env_vars()

        expected_config_dict = {
            "region": "us-phoenix-1",
            "tenancy": "ocid1.tenancy.oc1..aaaaaaa",
        }
        if key_file_entry_in_config or key_file_env_var:
            expected_config_dict["key_file"] = key_file_env_var or key_file_entry_in_config

        assert result == expected_config_dict, "Key file path not correctly overridden in config"

        if key_file_entry_in_config and key_file_env_var:
            assert (
                "Replacing existing key_file path in OCI config" in caplog.text
            ), "Key file path not replaced in config"
        else:
            assert (
                not "Replacing existing key_file path in OCI config" in caplog.text
            ), "Key file path replaced in config when not present"
        if key_file_env_var:
            assert (
                "Using OCI key file path from environment variable $PYCLOUDLIB_OCI_KEY_FILE_PATH"
                in caplog.text
            ), "Key file path not read from environment variable"


class TestLoadAndPreprocessOciTomlFile:
    def test_load_and_preprocess_oci_toml_file_with_profile(self):
        """Test _load_and_preprocess_oci_toml_file with a profile name."""
        toml_str = """
        [DEFAULT]
        region=us-phoenix-1
        tenancy=ocid1.tenancy.oc1..aaaaaaa
        """
        expected_config = {
            "region": "us-phoenix-1",
            "tenancy": "ocid1.tenancy.oc1..aaaaaaa",
        }
        result = _load_and_preprocess_oci_toml_file(toml_str)
        assert result == expected_config

    def test_load_and_preprocess_oci_toml_file_without_profile(self):
        """Test _load_and_preprocess_oci_toml_file without a profile name."""
        toml_str = """
        region=us-phoenix-1
        tenancy=ocid1.tenancy.oc1..aaaaaaa
        """
        expected_config = {
            "region": "us-phoenix-1",
            "tenancy": "ocid1.tenancy.oc1..aaaaaaa",
        }
        result = _load_and_preprocess_oci_toml_file(toml_str)
        assert result == expected_config

    def test_load_and_preprocess_oci_toml_file_with_unquoted_values(self):
        """Test _load_and_preprocess_oci_toml_file with unquoted values."""
        toml_str = """
        region=us-phoenix-1
        tenancy=ocid1.tenancy.oc1..aaaaaaa
        key_file=/path/to/key
        """
        expected_config = {
            "region": "us-phoenix-1",
            "tenancy": "ocid1.tenancy.oc1..aaaaaaa",
            "key_file": "/path/to/key",
        }
        result = _load_and_preprocess_oci_toml_file(toml_str)
        assert result == expected_config

    def test_load_and_preprocess_oci_toml_file_with_quoted_values(self):
        """Test _load_and_preprocess_oci_toml_file with quoted values."""
        toml_str = """
        region="us-phoenix-1"
        tenancy="ocid1.tenancy.oc1..aaaaaaa"
        key_file="/path/to/key"
        """
        expected_config = {
            "region": "us-phoenix-1",
            "tenancy": "ocid1.tenancy.oc1..aaaaaaa",
            "key_file": "/path/to/key",
        }
        result = _load_and_preprocess_oci_toml_file(toml_str)
        assert result == expected_config

    def test_load_and_preprocess_oci_toml_file_with_invalid_toml(self):
        """Test _load_and_preprocess_oci_toml_file with invalid TOML data."""
        toml_str = """
        region=us-phoenix-1
        tenancy=ocid1.tenancy.oc1..aaaaaaa
        key_file=/path/to/key
        invalid_toml = 
        """
        with pytest.raises(toml.TomlDecodeError):
            _load_and_preprocess_oci_toml_file(toml_str)


class TestGetSubnetIdByName:
    def test_get_subnet_id_by_name_fails_no_subnet(self):
        network_client = MagicMock()
        network_client.list_subnets.return_value.data = []
        with pytest.raises(PycloudlibError, match="Unable to determine subnet name"):
            get_subnet_id_by_name(network_client, "compartment_id", "missing_subnet")

    def test_get_subnet_id_by_name_fails_multiple_subnets(self):
        network_client = MagicMock()
        network_client.list_subnets.return_value.data = [MagicMock(), MagicMock()]
        with pytest.raises(PycloudlibError, match="Found multiple subnets with name"):
            get_subnet_id_by_name(network_client, "compartment_id", "duplicate_subnet")

    def test_get_subnet_id_by_name_succeeds(self):
        network_client = MagicMock()
        subnet_mock = MagicMock()
        subnet_mock.id = "subnet_id"
        network_client.list_subnets.return_value.data = [subnet_mock]
        result = get_subnet_id_by_name(network_client, "compartment_id", "single_subnet")
        assert result == "subnet_id"


class TestGetSubnetIdParameterized:
    @pytest.fixture
    def setup_environment(self):
        """Set up the test environment."""
        network_client = MagicMock()
        compartment_id = "compartment_id"
        availability_domain = "availability_domain"
        vcn = MagicMock()
        vcn.id = "vcn_id"
        vcn.display_name = "vcn_name"
        network_client.list_vcns.return_value.data = [vcn]
        return network_client, compartment_id, availability_domain, vcn

    @pytest.mark.parametrize(
        "networking_type, private, expected_subnet_id",
        [
            (NetworkingType.IPV4, False, "ipv4_public_subnet_id"),
            (NetworkingType.IPV4, True, "ipv4_private_subnet_id"),
            (NetworkingType.IPV6, False, "ipv6_public_subnet_id"),
            (NetworkingType.IPV6, True, "ipv6_private_subnet_id"),
            (NetworkingType.DUAL_STACK, False, "dual_stack_public_subnet_id"),
            (NetworkingType.DUAL_STACK, True, "dual_stack_private_subnet_id"),
        ],
    )
    def test_get_subnet_id_parameterized(
        self,
        setup_environment,
        networking_type,
        private,
        expected_subnet_id,
    ):
        """Test get_subnet_id with different networking types and private flag."""
        (
            network_client,
            compartment_id,
            availability_domain,
            vcn,
        ) = setup_environment

        # Create subnet mocks based on the parameters
        ipv4_public_subnet = MagicMock()
        ipv4_public_subnet.availability_domain = None
        ipv4_public_subnet.prohibit_internet_ingress = False
        ipv4_public_subnet.cidr_block = "10.0.0.0/24"
        ipv4_public_subnet.ipv6_cidr_block = None
        ipv4_public_subnet.id = "ipv4_public_subnet_id"

        ipv4_private_subnet = MagicMock()
        ipv4_private_subnet.availability_domain = None
        ipv4_private_subnet.prohibit_internet_ingress = True
        ipv4_private_subnet.cidr_block = "10.0.1.0/24"
        ipv4_private_subnet.ipv6_cidr_block = None
        ipv4_private_subnet.id = "ipv4_private_subnet_id"

        ipv6_public_subnet = MagicMock()
        ipv6_public_subnet.availability_domain = None
        ipv6_public_subnet.prohibit_internet_ingress = False
        ipv6_public_subnet.cidr_block = None
        ipv6_public_subnet.ipv6_cidr_block = "2603:c020:400d:5d7e::/64"
        ipv6_public_subnet.id = "ipv6_public_subnet_id"

        ipv6_private_subnet = MagicMock()
        ipv6_private_subnet.availability_domain = None
        ipv6_private_subnet.prohibit_internet_ingress = True
        ipv6_private_subnet.cidr_block = None
        ipv6_private_subnet.ipv6_cidr_block = "2603:c020:400d:5d7f::/64"
        ipv6_private_subnet.id = "ipv6_private_subnet_id"

        dual_stack_public_subnet = MagicMock()
        dual_stack_public_subnet.availability_domain = None
        dual_stack_public_subnet.prohibit_internet_ingress = False
        dual_stack_public_subnet.cidr_block = "10.0.2.0/24"
        dual_stack_public_subnet.ipv6_cidr_block = "2603:c020:400d:5d80::/64"
        dual_stack_public_subnet.id = "dual_stack_public_subnet_id"

        dual_stack_private_subnet = MagicMock()
        dual_stack_private_subnet.availability_domain = None
        dual_stack_private_subnet.prohibit_internet_ingress = True
        dual_stack_private_subnet.cidr_block = "10.0.3.0/24"
        dual_stack_private_subnet.ipv6_cidr_block = "2603:c020:400d:5d81::/64"
        dual_stack_private_subnet.id = "dual_stack_private_subnet_id"

        network_client.list_subnets.return_value.data = [
            ipv4_public_subnet,
            ipv4_private_subnet,
            ipv6_public_subnet,
            ipv6_private_subnet,
            dual_stack_public_subnet,
            dual_stack_private_subnet,
        ]

        networking_config = NetworkingConfig(
            networking_type=networking_type,
            private=private,
        )

        result = get_subnet_id(
            network_client=network_client,
            compartment_id=compartment_id,
            availability_domain=availability_domain,
            networking_config=networking_config,
        )

        assert result == expected_subnet_id


class TestGenerateCreateVnicDetails:
    subnet_id = "subnet_id"

    def test_generate_create_vnic_details_default(self):
        """Test generate_create_vnic_details with default parameters."""

        vnic_details = generate_create_vnic_details(self.subnet_id)
        assert vnic_details.subnet_id == self.subnet_id
        assert vnic_details.assign_ipv6_ip is False
        assert vnic_details.assign_public_ip is True

    def test_generate_create_vnic_details_ipv4_public(self):
        """Test generate_create_vnic_details with IPv4 public configuration."""
        networking_config = NetworkingConfig(networking_type=NetworkingType.IPV4, private=False)
        vnic_details = generate_create_vnic_details(self.subnet_id, networking_config)
        assert vnic_details.subnet_id == self.subnet_id
        assert vnic_details.assign_ipv6_ip is False
        assert vnic_details.assign_public_ip is True

    def test_generate_create_vnic_details_ipv4_private(self):
        """Test generate_create_vnic_details with IPv4 private configuration."""
        networking_config = NetworkingConfig(networking_type=NetworkingType.IPV4, private=True)
        vnic_details = generate_create_vnic_details(self.subnet_id, networking_config)
        assert vnic_details.subnet_id == self.subnet_id
        assert vnic_details.assign_ipv6_ip is False
        assert vnic_details.assign_public_ip is False

    def test_generate_create_vnic_details_ipv6(self):
        """Test generate_create_vnic_details with IPv6 configuration."""
        networking_config = NetworkingConfig(networking_type=NetworkingType.IPV6)
        vnic_details = generate_create_vnic_details(self.subnet_id, networking_config)
        assert vnic_details.subnet_id == self.subnet_id
        assert vnic_details.assign_ipv6_ip is True
        assert vnic_details.assign_public_ip is False

    def test_generate_create_vnic_details_dual_stack_public(self):
        """Test generate_create_vnic_details with dual stack public configuration."""
        networking_config = NetworkingConfig(
            networking_type=NetworkingType.DUAL_STACK, private=False
        )
        vnic_details = generate_create_vnic_details(self.subnet_id, networking_config)
        assert vnic_details.subnet_id == self.subnet_id
        assert vnic_details.assign_ipv6_ip is True
        assert vnic_details.assign_public_ip is True

    def test_generate_create_vnic_details_dual_stack_private(self):
        """Test generate_create_vnic_details with dual stack private configuration."""
        networking_config = NetworkingConfig(
            networking_type=NetworkingType.DUAL_STACK, private=True
        )
        vnic_details = generate_create_vnic_details(self.subnet_id, networking_config)
        assert vnic_details.subnet_id == self.subnet_id
        assert vnic_details.assign_ipv6_ip is True
        assert vnic_details.assign_public_ip is False
