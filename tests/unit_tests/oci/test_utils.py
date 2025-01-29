import pytest
from unittest.mock import MagicMock, patch
from pycloudlib.oci.utils import get_subnet_id
from pycloudlib.errors import PycloudlibError
from oci.retry import DEFAULT_RETRY_STRATEGY  # pylint: disable=E0611,E0401


@pytest.fixture
@patch("pycloudlib.oci.utils.DEFAULT_RETRY_STRATEGY", None)
def setup_environment():
    """
    Set up the test environment.

    This fixture is called before each test function execution.

    It mocks the network client and sets up the compartment ID and availability domain.
    """
    network_client = MagicMock()
    compartment_id = "compartment_id"
    availability_domain = "availability_domain"
    return network_client, compartment_id, availability_domain


def test_get_subnet_id_fails_with_vcn_name_not_found(setup_environment):
    """Test get_subnet_id fails when VCN name is not found."""
    network_client, compartment_id, availability_domain = setup_environment
    network_client.list_vcns.return_value.data = []
    with pytest.raises(PycloudlibError, match="Unable to determine vcn name"):
        get_subnet_id(
            network_client,
            compartment_id,
            availability_domain,
            vcn_name="vcn_name",
        )


def test_get_subnet_id_fails_with_multiple_vcns_found(setup_environment):
    """Test get_subnet_id fails when multiple VCNs with the same name are found."""
    network_client, compartment_id, availability_domain = setup_environment
    network_client.list_vcns.return_value.data = [MagicMock(), MagicMock()]
    with pytest.raises(PycloudlibError, match="Found multiple vcns with name"):
        get_subnet_id(
            network_client,
            compartment_id,
            availability_domain,
            vcn_name="vcn_name",
        )


def test_get_subnet_id_fails_with_no_vcns_found(setup_environment):
    """Test get_subnet_id fails when no VCNs are found."""
    network_client, compartment_id, availability_domain = setup_environment
    network_client.list_vcns.return_value.data = []
    with pytest.raises(PycloudlibError, match="No VCNs found in compartment"):
        get_subnet_id(network_client, compartment_id, availability_domain)


def test_get_subnet_id_fails_with_no_suitable_subnet_found(setup_environment):
    """Test get_subnet_id fails when no suitable subnet is found."""
    network_client, compartment_id, availability_domain = setup_environment
    vcn = MagicMock()
    vcn.id = "vcn_id"
    vcn.display_name = "vcn_name"
    network_client.list_vcns.return_value.data = [vcn]
    network_client.list_subnets.return_value.data = []
    with pytest.raises(PycloudlibError, match="Unable to find suitable subnet in VCN"):
        get_subnet_id(network_client, compartment_id, availability_domain)


def test_get_subnet_id_fails_with_private_subnet(setup_environment):
    """Test get_subnet_id fails when the subnet is private."""
    network_client, compartment_id, availability_domain = setup_environment
    vcn = MagicMock()
    vcn.id = "vcn_id"
    vcn.display_name = "vcn_name"
    network_client.list_vcns.return_value.data = [vcn]
    subnet = MagicMock()
    subnet.prohibit_internet_ingress = True
    network_client.list_subnets.return_value.data = [subnet]
    with pytest.raises(PycloudlibError, match="Unable to find suitable subnet in VCN"):
        get_subnet_id(network_client, compartment_id, availability_domain)


def test_get_subnet_id_fails_with_different_availability_domain(setup_environment):
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
        get_subnet_id(network_client, compartment_id, availability_domain)


def test_get_subnet_id_suceeds_without_vcn_name(setup_environment):
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
    result = get_subnet_id(network_client, compartment_id, availability_domain)
    assert result == "subnet_id"
    # Ensure that list_subnets is called with the first VCN's ID, not the second
    network_client.list_subnets.assert_called_with(
        compartment_id, vcn_id="vcn1_id", retry_strategy=DEFAULT_RETRY_STRATEGY
    )


def test_get_subnet_id_suceeds_with_vcn_name(setup_environment):
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
    result = get_subnet_id(network_client, compartment_id, availability_domain, vcn_name="vcn_name")
    assert result == "subnet_id"
    # Ensure that list_subnets is called with the specified VCN's ID
    network_client.list_subnets.assert_called_with(
        compartment_id, vcn_id="vcn_id", retry_strategy=DEFAULT_RETRY_STRATEGY
    )
