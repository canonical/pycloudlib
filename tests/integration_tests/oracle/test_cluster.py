import logging
from pycloudlib.oci.instance import OciInstance
from pycloudlib.oci.cloud import OCI

logger = logging.getLogger(__name__)

def test_cluster_launch():
    with OCI(
        "pycl-oracle-test-cluster-integration-test"
    ) as cloud:
        instances = cloud.create_compute_cluster(
            image_id=cloud.released_image("noble"),
            instance_count=2,
        )
        assert len(instances) == 2
        for instance in instances:
            logger.info(f"Instance {instance.instance_id} launched at {instance.ip}")
            assert instance.ip
            assert instance.private_ip
            assert instance.private_ip not in [i.private_ip for i in instances if i != instance]
            assert instance.execute("true").ok
            rdma_link_show = instance.execute("rdma link show")
            logger.info(f"rdma link show: {rdma_link_show}")
            assert rdma_link_show.ok
            assert rdma_link_show.stdout
