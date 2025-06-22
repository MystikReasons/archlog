import pytest
from unittest.mock import Mock, patch
from archlog.package_handler import PackageHandler


@pytest.fixture
def handler():
    mock_logger = Mock()
    mock_config = Mock()
    mock_config.config = {"arch-repositories": []}

    with (
        patch("archlog.package_handler.WebScraper"),
        patch("archlog.package_handler.GitLabAPI"),
    ):
        return PackageHandler(mock_logger, mock_config)


def test_exact_match(handler):
    tags = ["48.0", "48.1", "48.alpha", "48.beta"]
    assert handler.get_closest_package_tag("48.0", tags) == "48.0"


def test_close_match(handler):
    tags = ["48.0", "48.1", "48.alpha", "48.beta"]
    assert handler.get_closest_package_tag("48.0-1", tags) == "48.0"


def test_close_match_release_candidate(handler):
    tags = ["v6.15.0", "v6.15.0-rc1", "v6.14.0", "v6.14.0-rc1"]
    assert handler.get_closest_package_tag("6.15.0-1", tags) == "v6.15.0"


def test_no_good_match(handler):
    tags = ["1.0", "2.0", "3.0"]
    assert handler.get_closest_package_tag("4.0", tags) is None
    assert handler.get_closest_package_tag("3.5", tags) is None
