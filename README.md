# archlog

## Description
archlog is a simple Python CLI tool that fetches upgradable official Arch Linux packages and retrieves changelogs for each.
It distinguishes between minor and major Arch package updates.

* Minor updates usually contain only Arch-specific changes (e.g., rebuilds, packaging changes).
* Major updates include both Arch-specific commits and upstream version changes (e.g., new Firefox version).

Currently, only official Arch packages are supported. AUR, Flatpak, and other sources are not supported.

## Table of Content
<!-- TOC -->
* [archlog](#archlog)
  * [Description](#description)
  * [Table of Content](#table-of-content)
  * [Minor release example](#minor-release-example)
  * [Major release example](#major-release-example)
  * [Installation](#installation)
  * [Update](#update)
  * [Development Setup](#development-setup)
  * [Support](#support)
<!-- TOC -->

### Minor release example
```json
"gdb": {
        "base package": "-",
        "current version": "15.2-1",
        "new version": "15.2-2",
        "versions": [
            {
                "version-tag": "15.2-2",
                "release-type": "minor",
                "compare-url-tags-arch": "https://gitlab.archlinux.org/archlinux/packaging/packages/gdb/-/compare/15.2-1...15.2-2",
                "compare-url-tags-origin": "- Not applicable, minor release -",
                "changelog": {
                    "changelog Arch package": [
                        {
                            "commit message": "Re-enable LTO",
                            "commit URL": "https://gitlab.archlinux.org/archlinux/packaging/packages/gdb/-/commit/..."
                        },
                        {
                            "commit message": "upgpkg: 15.2-2: re-add lto",
                            "commit URL": "https://gitlab.archlinux.org/archlinux/packaging/packages/gdb/-/commit/..."
                        }
                    ],
                    "changelog origin package": [
                        "- Not applicable, minor release -"
                    ]
                }
            }
        ]
    }
```

### Major release example
```json
"xorg-server": {
        "base package": "-",
        "current version": "21.1.13-1",
        "new version": "21.1.14-1",
        "versions": [
            {
                "version-tag": "21.1.14-1",
                "release-type": "major",
                "compare-url-tags-arch": "https://gitlab.archlinux.org/archlinux/packaging/packages/xorg-server/-/compare/21.1.13-1...21.1.14-1",
                "compare-url-tags-origin": "https://gitlab.freedesktop.org/xorg/xserver/-/compare/xorg-server-21.1.13...xorg-server-21.1.14",
                "changelog": {
                    "changelog Arch package": [
                        {
                            "commit message": "upgpkg: 21.1.14-1",
                            "commit URL": "https://gitlab.archlinux.org/archlinux/packaging/packages/xorg-server/-/commit/..."
                        }
                    ],
                    "changelog origin package": [
                        {
                            "commit message": "Don't crash if the client argv or argv[0] is NULL.",
                            "commit URL": "https://gitlab.freedesktop.org/xorg/xserver/-/commit/..."
                        },
                        {
                            "commit message": "Return NULL in *cmdname if the client argv or argv[0] is NULL",
                            "commit URL": "https://gitlab.freedesktop.org/xorg/xserver/-/commit/..."
                        },
                        {
                            "commit message": "Fix a double-free on syntax error without a new line.",
                            "commit URL": "https://gitlab.freedesktop.org/xorg/xserver/-/commit/..."
                        },
                        {
                            "commit message": "xkb: Fix buffer overflow in _XkbSetCompatMap()",
                            "commit URL": "https://gitlab.freedesktop.org/xorg/xserver/-/commit/..."
                        },
                    ]
                }
            }
        ]
    }
```

## Installation

You can either clone or download the repository manually:
```bash
git clone "https://github.com/MystikReasons/archlog.git"
```

Or download and extract via curl:
```bash
rm -rf archlog && curl -L "https://github.com/MystikReasons/archlog/archive/refs/heads/master.zip" -o "./archlog.zip" && unzip "./archlog.zip" -d "." && mv "archlog-master" "archlog" && rm -rf "./archlog.zip"
```

Move into the newly created directory:
```bash
cd archlog
```

Then install the tool using (`python-pipx` needs to be installed on your system):
```bash
pipx install .
```

You can now remove the `archlog` folder if you wish too.
```bash
rm -r archlog
```

Start the CLI with:
```bash
archlog
```

If the `archlog` command is not available after installation, your system might not have ~/.local/bin in its PATH.

To fix this, run:
```bash
pipx ensurepath
```

Then restart your terminal or run:
```bash
source ~/.bashrc   # or ~/.zshrc depending on your shell
```

## Update

To update, you can download or pull the appropriate branch from this repository, and run the following command inside the downloaded archlog folder:
```bash
pipx install . --force
``` 

You can now remove the `archlog` folder if you wish too.
```bash
rm -r archlog
```

## Development Setup

> It is recommended to use a virtual environment for development.

Create a virtual environment:
```bash
python -m venv .venv
```

Activate the virtual environment:
```bash
source .venv/bin/activate
```

Install dev dependencies:
```bash
pip install -e .[dev]
```

The project uses the [black](https://github.com/psf/black) formatter.

Please format your contributions before commiting them.
```bash
python -m black .
```

## Support

If you enjoy this project and would like to support its development, feel free to donate! Your support means a lot. 🙏

- [Donate via PayPal](https://paypal.me/MystikReasons)
