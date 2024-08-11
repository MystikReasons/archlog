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

    if not packages_to_update:
        logger.info("No packages to upgrade")
        exit()

    logger.info(f"Upgradable packages ({len(packages_to_update)}):")
    logger.info("--------------------")
    for package in packages_to_update:
        logger.info(f"{package.package_name} {package.current_version} -> {package.new_version}")
        package_changelog = package_handler.get_package_changelog(package) # TODO Check if it returns False

        if package_changelog:
            logger.info("Changelog:")
            for commit_message, commit_url in package_changelog:
                logger.info(f"- {commit_message}")
                logger.info(f"\t{commit_url}")
        logger.info("--------------------------------")

if __name__ == "__main__":
    main()
