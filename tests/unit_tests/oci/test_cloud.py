from typing import List
import mock
import pytest

from pycloudlib.errors import InvalidTagNameError
from pycloudlib.oci.cloud import OCI


class FakeOCI(OCI):
    """Fake IBM Classic Class that doesn't load config or make requests during __init__."""

    # pylint: disable=super-init-not-called
    def __init__(self, *_, **__):
        """Fake __init__ that sets mocks for needed variables."""
        self._log = mock.MagicMock()
        # create rest of mocks as necessary


@pytest.fixture
def mock_oci():
    yield FakeOCI()
