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


def test_unprocessed_gitlab_url(handler):
    unprocessed_url = (
        "+\tsource = git+https://gitlab.winehq.org/wine/wine.git?signed#tag=wine-10.13"
    )
    assert (
        handler.extract_base_git_url(unprocessed_url)
        == "https://gitlab.winehq.org/wine/wine"
    )


def test_unprocessed_github_url_1(handler):
    unprocessed_url = "https://github.com/libexpat/libexpat?signed#tag=R_2_7_0"
    assert (
        handler.extract_base_git_url(unprocessed_url)
        == "https://github.com/libexpat/libexpat"
    )


def test_unprocessed_github_url_2(handler):
    unprocessed_url = "https://github.com/abseil/abseil-cpp/archive/20250127.0/abseil-cpp-20250127.0.tar.gz"
    assert (
        handler.extract_base_git_url(unprocessed_url)
        == "https://github.com/abseil/abseil-cpp"
    )


def test_unprocessed_github_url_3(handler):
    unprocessed_url = (
        "-\tsource = git+https://github.com/electron/electron.git#tag=v36.8.1"
    )
    assert (
        handler.extract_base_git_url(unprocessed_url)
        == "https://github.com/electron/electron"
    )


def test_unprocessed_git_url(handler):
    unprocessed_url = (
        "https://git.kernel.org/pub/scm/utils/kernel/kmod/kmod.git#tag=v34.1?signed"
    )
    assert (
        handler.extract_base_git_url(unprocessed_url)
        == "https://git.kernel.org/pub/scm/utils/kernel/kmod/kmod"
    )
