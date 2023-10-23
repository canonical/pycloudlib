from unittest import mock

from pycloudlib.errors import CleanupError
from pycloudlib.qemu.instance import QemuInstance


def test_qmp_no_socket(caplog):
    with mock.patch("time.sleep") as m_sleep:
        instance = QemuInstance(None, instance_id="abc::123::456")
    assert instance.qmp is None
    assert "Failed to find QMP socket" in caplog.text
    assert m_sleep.call_count == 10


@mock.patch(
    "pycloudlib.qemu.instance.QmpConnection", side_effect=AssertionError
)
@mock.patch("pycloudlib.qemu.instance.Path")
def test_qmp_error(m_path, m_qmp, caplog):
    assert QemuInstance(None, instance_id="abc::123::456").qmp is None
    assert "QMP socket not working as expected" in caplog.text


@mock.patch("pycloudlib.qemu.instance.Path")
@mock.patch(
    "pycloudlib.qemu.instance.QemuInstance._setup_qmp", return_value=None
)
@mock.patch("shutil.rmtree")
def test_delete_no_qmp(m_rmtree, m_qmp, m_path):
    m_handle = mock.Mock()
    instance = QemuInstance(None, instance_id="abc::123::456", handle=m_handle)
    errors = instance.delete()
    assert errors == []
    assert m_handle.kill.call_count == 1
    m_rmtree.assert_called_once_with(instance.instance_dir)


@mock.patch("pycloudlib.qemu.instance.Path")
@mock.patch(
    "pycloudlib.qemu.instance.QemuInstance._setup_qmp", return_value=None
)
@mock.patch("shutil.rmtree")
def test_delete_no_handle(m_rmtree, m_qmp, m_path):
    instance = QemuInstance(None, instance_id="abc::123::456")
    errors = instance.delete()
    assert len(errors) == 1
    assert isinstance(errors[0], CleanupError)
    assert (
        str(errors[0])
        == "No QMP connection or process handle. Manual cleanup required"
    )
    m_rmtree.assert_called_once_with(instance.instance_dir)


@mock.patch("pycloudlib.qemu.instance.Path")
@mock.patch(
    "pycloudlib.qemu.instance.QemuInstance._setup_qmp", return_value=None
)
@mock.patch("pycloudlib.qemu.instance.QemuInstance.execute")
def test_shutdown_no_qmp(m_execute, m_qmp, m_path, caplog):
    instance = QemuInstance(None, instance_id="abc::123::456")
    instance.shutdown()
    assert m_execute.call_args == mock.call("shutdown now", use_sudo=True)
    assert "No QMP connection. Doing a soft shutdown" in caplog.text
