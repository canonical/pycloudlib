from typing import List
import mock
import pytest

from pycloudlib.errors import InvalidTagNameError
from pycloudlib.ibm_classic.cloud import IBMClassic
from pycloudlib.ibm_classic.errors import IBMClassicException


class FakeClassic(IBMClassic):
    """Fake IBM Classic Class that doesn't load config or make requests during __init__."""

    # pylint: disable=super-init-not-called
    def __init__(self, *_, **__):
        """Fake __init__ that sets mocks for needed variables."""
        self._log = mock.MagicMock()
        self._client = mock.MagicMock()
        self._virtual_server_manager = mock.MagicMock()
        self._image_manager = mock.MagicMock()
        self._ssh_key_manager = mock.MagicMock()
        self._network_manager = mock.MagicMock()
        self._created_keys = []
        self._created_security_groups = []
        self._domain_name = "test.domain"


@pytest.fixture
def mock_ibmclassic():
    yield FakeClassic()


@pytest.mark.parametrize(
    "directions, ipv6, port, protocol, expected_call_count",
    [
        (["ingress"], False, None, None, 1),
        (["egress"], False, None, None, 1),
        (["ingress", "egress"], True, None, None, 4),
        (["ingress", "egress"], False, None, None, 2),
        (["ingress"], True, 22, "TCP", 2),
        (["egress"], True, 80, "UDP", 2),
    ],
)
def test_add_rules_valid_input(
    mock_ibmclassic, directions, ipv6, port, protocol, expected_call_count
):
    mock_ibmclassic._add_rules_to_security_group(
        group_id="sg-1234",
        directions=directions,
        ipv6=ipv6,
        port=port,
        protocol=protocol,
    )

    assert (
        mock_ibmclassic._network_manager.add_securitygroup_rule.call_count
        == expected_call_count
    )


def test_add_rules_invalid_direction(mock_ibmclassic):
    with pytest.raises(ValueError):
        mock_ibmclassic._add_rules_to_security_group(
            group_id="sg-1234", directions=["invalid_direction"], ipv6=False
        )


def test_get_image_id_from_name(mock_ibmclassic):
    mock_ibmclassic._image_manager.list_private_images.return_value = [
        {"globalIdentifier": "image-id-1234"},
    ]
    assert (
        mock_ibmclassic.get_image_id_from_name("image-name") == "image-id-1234"
    )


def test_get_datacenter(mock_ibmclassic):
    mock_ibmclassic._network_manager.get_list_datacenter.return_value = [
        {"name": "dal11"},
        {"name": "dal13"},
        {"name": "fra05"},
        {"name": "fra03"},
    ]
    assert mock_ibmclassic._get_datacenter("dal") == "dal11"
    assert mock_ibmclassic._get_datacenter("fra") == "fra05"


def test_get_datacenter_invalid(mock_ibmclassic):
    mock_ibmclassic._network_manager.get_list_datacenter.return_value = [
        {"name": "dal11"},
        {"name": "dal13"},
        {"name": "fra05"},
        {"name": "fra03"},
    ]
    with pytest.raises(IBMClassicException):
        mock_ibmclassic._get_datacenter("invalid")


rule1 = "All letters must be lowercase"
rule2 = "Must be between 1 and 63 characters long"
rule3 = "Must not start or end with a hyphen or period"
rule4 = "Must be alphanumeric, periods, and hyphens only"
rule5 = "Must not contain only numbers"


@pytest.mark.parametrize(
    "tag, rules_failed",
    [
        ("tag", []),
        ("TAG", [rule1]),
        ("TAG-", [rule1, rule3]),
        ("TAG.", [rule1, rule3]),
        ("-tag_", [rule3, rule4]),
        (".tag_", [rule3, rule4]),
        ("-", [rule3]),
        ("x" * 64, [rule2]),
        ("", [rule2]),
        ("x" * 63, []),
        ("x", []),
        ("t a_g", [rule4]),
        ("123456", [rule5]),
        ("123.456-789", []),
    ],
)
def test_validate_tag(tag: str, rules_failed: List[str]):
    if len(rules_failed) == 0:
        # test that no exception is raised
        IBMClassic._validate_tag(tag)
    else:
        with pytest.raises(InvalidTagNameError) as exc_info:
            IBMClassic._validate_tag(tag)
        assert tag in str(exc_info.value)
        for rule in rules_failed:
            assert rule in str(exc_info.value)
