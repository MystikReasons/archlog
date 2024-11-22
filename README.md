# Arch Linux changelog viewer

## Description
The Arch Linux changelog viewer is a simple Python script which gets the upgradable Arch packages and tries to get for each package individually the changelog.
The script differentiates between a minor Arch release and a major Arch release.

The minor Arch release typically only contains some commits on the Arch package source hosting website.

The major Arch release typically contains some commits on the Arch package source hosting website and an upgrade of the origin package (for example Firefox).

This script does currently only work with offical Arch packages, Flatpack, AUR etc. are not supported


### Minor release example
```json
"gdb": {
        "current version": "15.2-1",
        "new version": "15.2-2",
        "versions": [
            {
                "version-tag": "15.2-2",
                "release-type": "minor",
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
        "current version": "21.1.13-1",
        "new version": "21.1.14-1",
        "versions": [
            {
                "version-tag": "21.1.14-1",
                "release-type": "major",
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
- Clone or fork the repository
- Only once: in the project folder run `pip install -r requirements.txt`
    - If the environment is externally managed (default behaviour in Arch Linux) you need to install and enable the python virtual environment before running this command
- Run the program with `python main.py`

## Build documentation with Sphinx
If no /docs folder is available use the following command `sudo docker run -it --rm -v $(pwd)/docs:/docs sphinxdoc/sphinx sphinx-quickstart`

Once that is available, you can for example generate a .html file with `sudo docker run --rm -v $(pwd)/docs:/docs sphinxdoc/sphinx make html`

## Support

If you enjoy this project and would like to support its development, feel free to donate! Your support means a lot. 🙏

- [Donate via PayPal](https://paypal.me/MystikReasons)