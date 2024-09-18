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
    def test_type_from_raw_instance(
        self, client, raw_instance, inst_id, zone_id, inst_type
    ):
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

    @mock.patch(M_PATH + "VpcV1", autospec=True)
    def test_attach_floating_ip(self, client, caplog):
        """
        retry attach_floating_ip until VpcV1 lists non-empty floating_ips."""

        inst = IBMInstance.from_raw_instance(
            key_pair=None,
            client=client,
            instance=SAMPLE_RAW_INSTANCE,
        )
        metal_floating_ips = mock.Mock(
            get_result=mock.Mock(
                side_effect=[
                    {"floating_ips": []},
                    {
                        "floating_ips": [
                            {"id": "floatingid1", "name": "floatingname"}
                        ]
                    },
                ]
            )
        )
        with mock.patch.object(
            client,
            "list_bare_metal_server_network_interface_floating_ips",
            return_value=metal_floating_ips,
        ), mock.patch.object(
            inst,
            "_choose_from_existing_floating_ips",
            return_value={"name": "ci-ip-match-5", "id": "floatingid1"},
        ):
            inst.attach_floating_ip(floating_ip_substring="ci-ip-match")
        for expected_log in [
            "Failed to attach floating ip: ci-ip-match-5.",
            "Successfully attached floating ip: floatingname",
        ]:
            assert expected_log in caplog.text
        assert 2 == metal_floating_ips.get_result.call_count
