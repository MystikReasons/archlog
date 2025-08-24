import pytest
import tomllib
from unittest.mock import Mock, patch
from archlog.package_handler import PackageHandler


@pytest.fixture
def handler():
    mock_logger = Mock()
    mock_config = Mock()
    mock_config.config = {"arch-repositories": []}

    with patch("archlog.package_handler.WebScraper"):
        return PackageHandler(mock_logger, mock_config)


def test_extract_upstream_url_nvchecker_gitlab_archlinux(handler):
    nvchecker_content = """
    [archlinux-keyring]
    source = "gitlab"
    gitlab = "archlinux/archlinux-keyring"
    host = "gitlab.archlinux.org"
    use_max_tag = true
    prefix = "v"
    """

    parsed_content = tomllib.loads(nvchecker_content)
    assert (
        handler.extract_upstream_url_nvchecker(parsed_content, "archlinux-keyring")
        == "https://gitlab.archlinux.org/archlinux/archlinux-keyring"
    )


def test_extract_upstream_url_nvchecker_github_case_1(handler):
    nvchecker_content = """
    [docker]
    source = "github"
    github = "moby/moby"
    prefix = "v"
    use_max_tag = true
    exclude_regex = ".*(rc|alpha|beta).*"
    """

    parsed_content = tomllib.loads(nvchecker_content)
    assert handler.extract_upstream_url_nvchecker(parsed_content, "docker") == "https://github.com/moby/moby"


def test_extract_upstream_url_nvchecker_github_case_2(handler):
    nvchecker_content = r"""
    [curl]
    source = "git"
    git = "https://github.com/curl/curl.git"
    use_latest_tag = true
    from_pattern = '''curl-(\d+)_(\d+)_(\d+)'''
    to_pattern = '''\1.\2.\3'''
    exclude_regex = ".*(tiny|beta).*"
    """

    parsed_content = tomllib.loads(nvchecker_content)
    assert handler.extract_upstream_url_nvchecker(parsed_content, "curl") == "https://github.com/curl/curl"


def test_extract_upstream_url_nvchecker_key_mismatch(handler):
    nvchecker_content = r"""
    [sqlite]
    source = "regex"
    regex = "Version (\\d+.\\d+.\\d+)"
    url = "https://www.sqlite.org/index.html"
    """

    parsed_content = tomllib.loads(nvchecker_content)
    assert handler.extract_upstream_url_nvchecker(parsed_content, "lib32-sqlite") == None


def test_extract_upstream_url_nvchecker_multiple_sources(handler):
    nvchecker_content = """
    [archlinux-keyring]
    source = "gitlab"
    gitlab = "archlinux/archlinux-keyring"
    host = "gitlab.archlinux.org"
    use_max_tag = true
    prefix = "v"
    [docker]
    source = "github"
    github = "moby/moby"
    prefix = "v"
    use_max_tag = true
    exclude_regex = ".*(rc|alpha|beta).*"
    """

    parsed_content = tomllib.loads(nvchecker_content)
    assert handler.extract_upstream_url_nvchecker(parsed_content, "docker") == "https://github.com/moby/moby"
