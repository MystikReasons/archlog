def collect_changelog_data(package_information, package_handler, config_handler):
    """Collects changelog data for a list of packages using the provided handler.

    For each package:
    - Fetches the changelog via the package handler
    - Writes the changelog using the config handler
    - Returns a list of (package, changelog) pairs

    :param package_information: List of packages selected by the user.
    :type package_information: list[Package]
    :param package_handler: Handler instance used to retrieve changelogs.
    :type package_handler: PackageHandler
    :param config_handler: Handler used to write changelogs to disk.
    :type config_handler: ConfigHandler

    :return: List of tuples, each containing a package and its changelog.
    :rtype: list[tuple[Package, Optional[list[tuple[str, str, str, str, str, str]]]]]
    """
    package, changelog = package_handler.get_package_changelog(package_information)
    config_handler.write_changelog(package, changelog)

    return changelog
