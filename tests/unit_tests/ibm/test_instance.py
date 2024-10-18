"""Module for IBM instance tests."""

import pytest
from unittest import mock

from pycloudlib.ibm.instance import IBMInstance, _IBMInstanceType

SAMPLE_RAW_INSTANCE = {
    "id": "ibm1",
    "primary_network_interface": {"id": "nic1"},
    "profile": {"name": "metal"},
    "zone": {"name": "zone1"},
}
M_PATH = "pycloudlib.ibm.instance."


class TestIBMInstance:
    @pytest.mark.parametrize(
        "raw_instance,inst_id,zone_id,inst_type",
        (
            (
                SAMPLE_RAW_INSTANCE,
                "ibm1",
                "zone1",
                _IBMInstanceType.BARE_METAL_SERVER,
            ),
        ),
    )
    @mock.patch(M_PATH + "VpcV1", autospec=True)
    def test_type_from_raw_instance(self, client, raw_instance, inst_id, zone_id, inst_type):
        """Factory function inits the appropriate IBMInstanceType."""
        inst = IBMInstance.from_raw_instance(
            key_pair=None,
            client=client,
            instance=raw_instance,
        )
        assert client == inst._client
        assert inst_id == inst.id
        assert zone_id == inst.zone
        assert inst_type == inst._ibm_instance_type

    @mock.patch("time.sleep")  # bypass the time.sleep call in _attach_floating_ip()
    @mock.patch(M_PATH + "VpcV1", autospec=True)
    def test_attach_floating_ip(self, m_sleep, client, caplog):
        """
        retry attach_floating_ip until VpcV1 lists non-empty floating_ips."""

        inst = IBMInstance.from_raw_instance(
            key_pair=None,
            client=client,
            instance=SAMPLE_RAW_INSTANCE,
        )

        fi_name = "ci-ip-match-5"
        fi_id = "floatingid1"

        # make sure nic ID is set as expected since it is essential for the test
        assert inst._nic_id == "nic1"

        metal_floating_ips = mock.Mock(
            get_result=mock.Mock(
                side_effect=[
                    {  # there's no target
                        "name": "different-floating-ip",
                        "id": "different-id",
                    },
                    {  # there's a target, but its a different instance's nic
                        "target": {"id": "not-nic1", "name": "wrong_nic"},
                        "name": "different-floating-ip",
                        "id": "different-id",
                    },
                    {  # target is this instance's nic (correct)
                        "target": {"id": "nic1", "name": "correct-nic"},
                        "name": fi_name,
                        "id": fi_id,
                    },
                ]
            )
        )
        with mock.patch.object(
            client,
            "get_floating_ip",
            return_value=metal_floating_ips,
        ), mock.patch.object(
            inst,
            "_choose_from_existing_floating_ips",
            return_value={"name": fi_name, "id": fi_id},
        ):
            inst.attach_floating_ip(floating_ip_substring="ci-ip-match")

        assert 1 == caplog.text.count(f"Successfully attached floating ip: {fi_name}")
        assert 2 == caplog.text.count(f"Failed to attach floating ip: {fi_name}")
        assert 3 == metal_floating_ips.get_result.call_count

        assert inst._floating_ip["id"] == fi_id
        assert inst._floating_ip["name"] == fi_name
