from archlog.config_handler import ConfigHandler
from archlog.package_handler import PackageHandler
from archlog.logic import collect_changelog_data


def main():
    config_handler = ConfigHandler()
    logger = config_handler.logger
    package_handler = PackageHandler(logger, config_handler)

    logger.info("Package Changelog Viewer")
    logger.info("------------------------")
    logger.debug("Logger is set up")

    packages_to_update = package_handler.get_upgradable_packages()
    if not packages_to_update:
        logger.info("No packages to upgrade")
        exit()

    max_package_name_length = max(len(package.package_name) for package in packages_to_update)
    max_package_current_version = max(len(package.current_version) for package in packages_to_update)
    max_package_new_version = max(len(package.new_version) for package in packages_to_update)
    max_package_count = len(str(len(packages_to_update)))

    logger.info(f"Upgradable packages ({len(packages_to_update)}):")
    logger.info("--------------------")
    for index, package in enumerate(packages_to_update, start=1):
        logger.info(
            f"[{str(index).ljust(max_package_count)}] "
            f"{package.package_name.ljust(max_package_name_length)} "
            f"{package.current_version.ljust(max_package_current_version)} -> "
            f"{package.new_version.ljust(max_package_new_version)}"
        )
    logger.info("--------------------")

    logger.info("Choose package(s) from which to check for the changelog")

    valid_input = False
    while not valid_input:
        chosen_packages = input("Enter package indices (comma separated), or 0 to select all: ")

        if chosen_packages == "0":
            selected_packages = packages_to_update
            valid_input = True
        else:
            selected_indices = []
            for index in chosen_packages.split(","):
                index = index.strip()
                if index.isdigit():
                    index = int(index) - 1
                    if 0 <= index < len(packages_to_update):
                        selected_indices.append(index)
                else:
                    selected_indices = []
                    break

            if selected_indices:
                selected_packages = [packages_to_update[index] for index in selected_indices]
                valid_input = True
            else:
                logger.info("Invalid input. Please enter valid package indices.")

    if selected_packages and chosen_packages != "0":
        logger.info("Selected packages for changelog check:")
        for package in selected_packages:
            logger.info(f"{package.package_name} {package.current_version} -> {package.new_version}")
    logger.info("--------------------")

    result = collect_changelog_data(selected_packages, package_handler, config_handler)

    for package, package_changelog in result:
        if package_changelog:
            logger.info("Changelog:")
            for message, url, *_ in package_changelog:
                logger.info(f"- {message}")
                logger.info(f"\t{url}")
        else:
            logger.info(f"[Info]: No changelog for package: {package.package_name} found.")

        logger.info("--------------------------------")
