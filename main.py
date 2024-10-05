#! /usr/bin/python3
from config_handler import ConfigHandler
from package_handler import PackageHandler

def main():
    config_handler = ConfigHandler()
    logger = config_handler.logger
    package_handler = PackageHandler(logger, config_handler)

    logger.info("Package Changelog Viewer")
    logger.info("------------------------")
    logger.info("Logger is set up")

    packages_to_update = package_handler.get_upgradable_packages()
    max_package_name_length = max(len(package.package_name) for package in packages_to_update)
    max_package_current_version = max(len(package.current_version) for package in packages_to_update)
    max_package_new_version = max(len(package.new_version) for package in packages_to_update)

    if packages_to_update is None:
        logger.info("No packages to upgrade")
        exit()

    logger.info(f"Upgradable packages ({len(packages_to_update)}):")
    logger.info("--------------------")
    for package in packages_to_update:
        logger.info(f"{package.package_name.ljust(max_package_name_length)} "
                    f"{package.current_version.ljust(max_package_current_version)} -> "
                    f"{package.new_version.ljust(max_package_new_version)}")
    logger.info("--------------------")

    for package in packages_to_update:
        logger.info(f"{package.package_name} {package.current_version} -> {package.new_version}")
        package_changelog = package_handler.get_package_changelog(package)

        if package_changelog:
            logger.info("Changelog:")
            for commit_message, commit_url, commit_tag in package_changelog:
                logger.info(f"- {commit_message}")
                logger.info(f"\t{commit_url}")
        else:
            logger.info(f"No changelog for package: {package.package_name} found.")

        config_handler.write_changelog(package, package_changelog)
        logger.info("--------------------------------")

if __name__ == "__main__":
    main()
