import os
import subprocess

from archlog.logger_manager import LoggerManager
from archlog.config_handler import ConfigHandler
from archlog.package_handler import PackageHandler
from archlog.logic import collect_changelog_data


def main():
    logger_manager = LoggerManager()
    logger = logger_manager.get_logger()
    config_handler = ConfigHandler(logger)

    log_path = config_handler.path_manager.get_logs_path()

    package_handler = PackageHandler(logger, config_handler)

    logger.info("archlog")
    logger.info("------------------------")
    logger.debug("Logger is set up")

    packages_to_update = package_handler.get_upgradable_packages()
    if not packages_to_update:
        logger.info("No packages to upgrade")
        exit(1)

    max_package_name_length = max(
        len(package["package_name"]) for package in packages_to_update.values()
    )
    max_package_current_version = max(
        len(package["current_version"]) for package in packages_to_update.values()
    )
    max_package_new_version = max(
        len(package["new_version"]) for package in packages_to_update.values()
    )
    max_package_count = len(str(len(packages_to_update)))

    logger.info(f"Upgradable packages ({len(packages_to_update)}):")
    logger.info("--------------------")
    for index, package in packages_to_update.items():
        logger.info(
            f"[{str(index).ljust(max_package_count)}] "
            f"{package['package_name'].ljust(max_package_name_length)} "
            f"{package['current_version'].ljust(max_package_current_version)} -> "
            f"{package['new_version'].ljust(max_package_new_version)}"
        )
    logger.info("--------------------")

    logger.info("Choose package(s) from which to check for the changelog")

    valid_input = False
    while not valid_input:
        chosen_packages = input(
            "Enter package indices (comma separated), or 0 to select all: "
        )

        if chosen_packages == "0":
            selected_packages = packages_to_update
            valid_input = True
        else:
            selected_indices = []
            for index in chosen_packages.split(","):
                index = index.strip()
                if index.isdigit():
                    index = int(index)
                    if 0 <= index < len(packages_to_update):
                        selected_indices.append(index)
                else:
                    selected_indices = []
                    break

            if selected_indices:
                selected_packages = {
                    index: packages_to_update[index] for index in selected_indices
                }
                valid_input = True
            else:
                logger.info("Invalid input. Please enter valid package indices.")

    if selected_packages and chosen_packages != "0":
        logger.info("Selected packages for changelog check:")
        for index, package in selected_packages.items():
            logger.info(
                f"{package['package_name']} {package['current_version']} -> {package['new_version']}"
            )
    logger.info("--------------------")

    for index, package in selected_packages.items():
        logger.info(
            f"{package['package_name']} {package['current_version']} -> {package['new_version']}"
        )
        package_changelog = collect_changelog_data(
            package, package_handler, config_handler
        )

        if package_changelog:
            logger.info("Changelog:")
            for message, url, *_ in package_changelog:
                logger.info(f"- {message}")
                logger.info(f"\t{url}")
        else:
            logger.info(
                f"[Info]: No changelog for package: {package['package_name']} found."
            )

        logger.info("--------------------------------")

    open_changelog_input = input("Do you want to open the changelog file? [y]|[n]: ")

    if open_changelog_input == "y":
        open_file_with_default_app(
            logger,
            (
                config_handler.path_manager.get_changelog_path()
                / config_handler.path_manager.get_changelog_filename()
            ),
        )
    elif open_changelog_input == "n":
        pass
    else:
        logger.error(f"[Error]: Invalid input.")


def open_file_with_default_app(logger, filepath: str) -> None:
    "Opens a file with the default set application on Linux."
    if not os.path.exists(filepath):
        logger.error(f"[Error]: The file {filepath} does not exist.")
        return

    try:
        subprocess.run(["xdg-open", filepath], check=True)
    except FileNotFoundError:
        logger.error(f"[Error]: 'xdg-open' is not installed.")
    except subprocess.CalledProcessError:
        logger.error(f"[Error]: Something went wrong while opening the file {filepath}")
    except Exception as ex:
        logger.error(f"[Error]: Unknown error: {ex}")


if __name__ == "__main__":
    main()
