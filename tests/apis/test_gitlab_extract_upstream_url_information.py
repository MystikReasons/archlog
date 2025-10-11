import re
import pytest
from unittest.mock import Mock, patch
from archlog.apis.gitlab_api import GitLabAPI


@pytest.fixture
def handler():
    mock_logger = Mock()
    return GitLabAPI(mock_logger)


def test_freedesktop_url(handler):
    url = "https://gitlab.freedesktop.org/xorg/xserver/-/tags"
    assert handler.extract_upstream_url_information(url) == (
        "freedesktop",
        "org",
        "xorg",
        "xserver",
    )


def test_freedesktop2_url(handler):
    url = "https://gitlab.freedesktop.org/xorg/lib/libXScrnSaver"
    assert handler.extract_upstream_url_information(url) == (
        "freedesktop",
        "org",
        "xorg/lib",
        "libXScrnSaver",
    )


def test_native_url(handler):
    url = "https://gitlab.com/kernel-firmware/linux-firmware"
    assert handler.extract_upstream_url_information(url) == (
        None,
        "com",
        "kernel-firmware",
        "linux-firmware",
    )


def test_gnome_url(handler):
    url = "https://gitlab.gnome.org/GNOME/adwaita-icon-theme"
    assert handler.extract_upstream_url_information(url) == (
        "gnome",
        "org",
        "GNOME",
        "adwaita-icon-theme",
    )


def test_kde_url(handler):
    url = "https://invent.kde.org/plasma/spectacle/"
    assert handler.extract_upstream_url_information(url) == (
        "kde",
        "org",
        "plasma",
        "spectacle",
    )
