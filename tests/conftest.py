import logging
import pytest

from pycloudlib.key import KeyPair

logging.basicConfig(level=logging.NOTSET)


@pytest.fixture(name="fake_ssh_keys", autouse=True)
def fake_ssh_keys_fixture(mocker, request):
    """Fixture to mock `_get_ssh_keys` across all tests unless marked otherwise."""
    if (
        "mock_ssh_keys" in request.node.keywords
        and "dont_mock_ssh_keys" not in request.node.keywords
    ):
        mocker.patch(
            "pycloudlib.cloud.BaseCloud._get_ssh_keys",
            return_value=KeyPair(
                name="fake_key",
                public_key_path="/fake/public/key",
                private_key_path="/fake/private/key",
            ),
        )
