import pytest
from unittest.mock import Mock, patch
from archlog.package_handler import PackageHandler


@pytest.fixture
def handler():
    mock_logger = Mock()
    mock_config = Mock()
    mock_config.config = {"arch-repositories": []}

    with (patch("archlog.package_handler.WebScraper"),):
        return PackageHandler(mock_logger, mock_config)


def test_exact_match(handler):
    tags = ["48.0", "48.1", "48.alpha", "48.beta"]
    assert handler.get_closest_package_tag("48.0", tags) == "48.0"


def test_close_match_suffix_1(handler):
    tags = ["48.0", "48.1", "48.alpha", "48.beta"]
    assert handler.get_closest_package_tag("48.0-1", tags) == "48.0"


def test_close_match_suffix_2(handler):
    tags = ["20250716", "20250707", "20250430.1", "20250430", "20250123.1"]
    assert handler.get_closest_package_tag("20250707-1", tags) == "20250707"


def test_close_match_suffix_3(handler):
    tags = ["v2_03_35", "v2_03_34", "v2_03_33", "v2_03_32", "v2_03_31"]
    assert handler.get_closest_package_tag("2.03.34-1", tags) == "v2_03_34"


def test_close_match_prefix_suffix(handler):
    tags = ["v6.3.1", "v6.3.0", "v6.2.90", "v6.2.91", "v6.3.90", "v6.3.91"]
    assert handler.get_closest_package_tag("1-6.3.90-1", tags) == "v6.3.90"


def test_close_match_release_candidate(handler):
    tags = ["v6.15.0", "v6.15.0-rc1", "v6.14.0", "v6.14.0-rc1"]
    assert handler.get_closest_package_tag("6.15.0-1", tags) == "v6.15.0"


def test_no_good_match(handler):
    tags = ["1.0", "2.0", "3.0"]
    assert handler.get_closest_package_tag("4.0", tags) is None
    assert handler.get_closest_package_tag("3.5", tags) is None
