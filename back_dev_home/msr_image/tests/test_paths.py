import pytest

from back_dev_home.msr_image.errors import InvalidLocator, InvalidToolIp
from back_dev_home.msr_image.paths import (
    cond_path,
    image_dir,
    image_path,
    validate_locator,
    validate_segment,
    validate_tool_ip,
)


@pytest.mark.parametrize("bad", ["..", "../etc", "a/b", "a\\b", "", ".", " x", "x\n", "\x00"])
def test_validate_segment_rejects_traversal_and_separators(bad):
    with pytest.raises(InvalidLocator):
        validate_segment(bad, "name")


def test_validate_segment_accepts_normal_name():
    assert validate_segment("MSR_1_shot01.jpeg", "name") == "MSR_1_shot01.jpeg"


def test_validate_locator_rejects_traversal_in_any_segment():
    with pytest.raises(InvalidLocator):
        validate_locator("ADI", "MSR_1", "../../../etc/passwd")
    with pytest.raises(InvalidLocator):
        validate_locator("..", "MSR_1", "shot.jpeg")


def test_image_dir_uses_hitachi_template():
    assert image_dir("ADI", "MSR_123") == "/HITACHI/DEVICE/HD/ADI/images/MSR_123"


def test_image_path_joins_name():
    assert (
        image_path("ADI", "MSR_123", "shot01.jpeg")
        == "/HITACHI/DEVICE/HD/ADI/images/MSR_123/shot01.jpeg"
    )


def test_cond_path_is_hidden_sidecar_dir():
    p = image_path("ADI", "MSR_123", "shot01.jpeg")
    assert cond_path(p) == "/HITACHI/DEVICE/HD/ADI/images/MSR_123/.shot01.jpeg/cond.txt"


def test_validate_tool_ip_accepts_ipv4():
    assert validate_tool_ip("10.0.0.1") == "10.0.0.1"


def test_validate_tool_ip_rejects_garbage():
    with pytest.raises(InvalidToolIp):
        validate_tool_ip("not-an-ip")


def test_validate_tool_ip_rejects_outside_subnet():
    with pytest.raises(InvalidToolIp):
        validate_tool_ip("192.168.1.5", allowed_subnets=["10.0.0.0/8"])


def test_validate_tool_ip_accepts_inside_subnet():
    assert validate_tool_ip("10.1.2.3", allowed_subnets=["10.0.0.0/8"]) == "10.1.2.3"
