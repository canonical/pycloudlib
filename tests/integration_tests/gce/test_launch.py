import pytest
from pycloudlib.gce.cloud import GCE
from pycloudlib.gce.util import raise_on_error
from google.cloud import compute_v1
from google.api_core.exceptions import GoogleAPICallError


@pytest.fixture
def gce_instance():
    with GCE(tag="test-launch") as gce:
        yield gce


def test_gce_launch_updates_config(gce_instance: GCE):
    """Test that the launch method updates the config."""
    daily = gce_instance.daily_image("noble", arch="x86_64")
    description = "Test description for kwarg verification."
    with gce_instance.launch(daily, description=description) as inst:
        try:
            instance_get_request = compute_v1.GetInstanceRequest(
                project=gce_instance.project,
                zone=gce_instance.zone,
                instance=inst.name,
            )
            result = gce_instance._instances_client.get(instance_get_request)
            assert result.description == description
        except GoogleAPICallError as e:
            raise_on_error(e)
