"""Unit tests for qemu/cloud.py.

Since the integration tests are the primary tests, these are mostly testing
error conditions and corner cases.
"""
from collections import namedtuple
from pathlib import Path
from unittest import mock

import pytest

from pycloudlib import Qemu
from pycloudlib.errors import ImageNotFoundError, PycloudlibError

BASIC_CONFIG = """\
[qemu]
image_dir = "{src}"
working_dir = "{dest}"
"""


@pytest.fixture
def qemu(tmp_path: Path):
    """Fixture to create a Qemu instance."""
    config_path = tmp_path / "config"
    image_dir = tmp_path / "src"
    image_dir.mkdir()
    dest_dir = tmp_path / "dest"
    dest_dir.mkdir()
    config_path.write_text(
        BASIC_CONFIG.format(src=str(image_dir), dest=str(dest_dir))
    )
    cloud = Qemu(tag="test", config_file=config_path)
    out = namedtuple("Qemu", "cloud image_dir dest_dir")
    yield out(cloud, image_dir, dest_dir)


def test_invalid_srcdir(tmp_path: Path):
    """Test that Qemu raises an error when image_dir is invalid."""
    config_path = tmp_path / "config"
    config_path.write_text("[qemu]\nimage_dir = '/does/not/exist'")
    with pytest.raises(
        ValueError,
        match="QEMU image_dir must be a valid path, not '/does/not/exist'",
    ):
        Qemu(tag="test", config_file=config_path)


def test_invalid_destdir(tmp_path: Path):
    """Test that Qemu raises an error when working_dir is invalid."""
    config_path = tmp_path / "config"
    config_path.write_text(
        "[qemu]\nimage_dir = '/tmp'\nworking_dir = '/does/not/exist'"
    )
    with pytest.raises(
        ValueError,
        match=("QEMU working_dir must be a valid path, not '/does/not/exist'"),
    ):
        Qemu(tag="test", config_file=config_path)


def test_get_available_dir(qemu, tmp_path: Path):
    """Test that _get_available_file works for dirs."""
    for i in range(5):
        next_path = qemu.cloud._get_available_file(tmp_path)
        assert str(next_path) == f"{tmp_path}-{i}"
        next_path.mkdir()


def test_get_available_file(qemu, tmp_path: Path):
    """Test that _get_available_file increments appropriately."""
    file_path = Path(tmp_path, "test.img")
    file_path.touch()
    for i in range(5):
        next_path = qemu.cloud._get_available_file(file_path)
        assert str(next_path) == f"{tmp_path}/test-{i}.img"
        next_path.touch()


def test_unparseable_release_page(qemu):
    """Test that _get_latest_image raises an error when page is unparseable."""
    with mock.patch(
        "pycloudlib.qemu.cloud.requests.get",
        return_value=mock.Mock(text="not html"),
    ):
        with pytest.raises(
            PycloudlibError,
            match=("Could not parse url: " "https://nonexistent"),
        ):
            qemu.cloud._get_latest_image(
                "https://nonexistent", "none", "none.img"
            )


@mock.patch(
    "pycloudlib.qemu.cloud.requests.get",
    return_value=mock.Mock(text="<title>Ubuntu daily [20231010]</title>"),
)
def test_image_already_downloaded(_m_get, qemu, caplog):
    """Test that _get_latest_image skips download if already exists."""
    image_dir: Path = qemu.image_dir / "none" / "20231010"
    image_dir.mkdir(parents=True)
    image1 = image_dir / "test1.img"
    image1.touch()
    image2 = image_dir / "test2.img"
    image2.touch()
    result = qemu.cloud._get_latest_image("https://none", "none", "none.img")
    assert result == str(image1.absolute())
    assert "Image already exists, skipping download" in caplog.text


def test_seed_iso_no_data(tmp_path: Path, qemu):
    """Test that _create_seed_iso returns None when no data is passed."""
    assert qemu.cloud._create_seed_iso(tmp_path, None, None, None) is None
    assert not Path(tmp_path, "user-data").exists()
    assert not Path(tmp_path, "meta-data").exists()
    assert not Path(tmp_path, "vendor-data").exists()


# @mock.patch("pycloudlib.qemu.cloud.subprocess")
@mock.patch("subprocess.run")
def test_seed_iso_only_vendordata(m_subp, qemu):
    """Test that _create_seed_iso works when only vendordata is passed."""
    tmp_path = qemu.dest_dir
    assert str(
        qemu.cloud._create_seed_iso(tmp_path, None, None, "vendor")
    ) == str(tmp_path / "seed.iso")
    assert Path(tmp_path, "user-data").exists()
    assert Path(tmp_path, "meta-data").exists()
    assert Path(tmp_path, "vendor-data").exists()

    assert m_subp.call_args[0] == (
        [
            "genisoimage",
            "-output",
            str(tmp_path / "seed.iso"),
            "-volid",
            "cidata",
            "-joliet",
            "-rock",
            "-input-charset",
            "UTF-8",
            str(tmp_path / "user-data"),
            str(tmp_path / "meta-data"),
            str(tmp_path / "vendor-data"),
        ],
    )


def test_no_kernel_found(qemu, caplog):
    """Test that _get_kernel_path raises an error when no kernel is found."""
    with pytest.raises(
        PycloudlibError, match="Could not find kernel for image_id: myid"
    ):
        qemu.cloud._get_kernel_path(
            kernel_path=None,
            kernel_cmdline="test",
            image_id="myid",
            base_image=qemu.dest_dir,
        )
    assert f"Unable to find kernel for image: {qemu.dest_dir}" in caplog.text


@pytest.mark.parametrize(
    "instance_type,expected",
    [
        ("c1m2", (1, 2)),
        ("c200m600", (200, 600)),
        ("rc2m5", ValueError),
        ("c5m2x", ValueError),
        ("c5", ValueError),
        ("m5", ValueError),
        ("cxmx", ValueError),
        ("test", ValueError),
    ],
)
def test_instance_type(instance_type, expected, qemu):
    """Test that _parse_instance_type works as expected."""
    if expected == ValueError:
        with pytest.raises(ValueError):
            qemu.cloud._parse_instance_type(instance_type)
    else:
        assert qemu.cloud._parse_instance_type(instance_type) == expected


def test_base_image(qemu):
    """Test that _find_base_image works as expected."""
    image_path = Path(qemu.image_dir, "image.img")
    image_path.touch()
    assert str(qemu.cloud._find_base_image("image.img")) == str(image_path)
    assert str(qemu.cloud._find_base_image(str(image_path))) == str(image_path)
    with pytest.raises(
        ImageNotFoundError,
        match=(
            "Could not find 'no.img' as absolute path or in "
            f"'{qemu.image_dir}'"
        ),
    ):
        qemu.cloud._find_base_image("no.img")
