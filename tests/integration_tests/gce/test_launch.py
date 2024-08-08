import pytest
from pycloudlib.gce.cloud import GCE


@pytest.fixture
def gce_instance():
    with GCE(tag="test-launch") as gce:
        yield gce


def test_gce_launch_updates_config(gce_instance: GCE):
    """Test that the launch method updates the config."""
    daily = gce_instance.daily_image("noble", arch="x86_64")
    description = "Test description for kwarg verification."
    with gce_instance.launch(daily, description=description) as inst:
        result = (
            gce_instance.compute.instances()
            .get(
                project=gce_instance.project,
                zone=gce_instance.zone,
                instance=inst.name,
            )
            .execute()
        )
        assert result["description"] == description
