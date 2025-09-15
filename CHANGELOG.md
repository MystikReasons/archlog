# 1.2 ()

### Features and enhancements

- **Changelog** Display package description in the changelog file for each package
- **Package Handler** Refactor and normalize underscores for tags in get_closest_package_tag() for proper matching
- **Package Handler** Add further KDE package category "network"
- **Package Handler** Break out of the loop if a KDE category was found instead of looping until the end
- **GitLab API** Fix GitLab URL extraction; handle multi-segment paths and /-/suffixes

### Bug fixes

# 1.1 (2025-09-09)

### Features and enhancements

- **ArchLinux API** Implement retry mechanism if the user runs into problems
- **Changelog** Added base package in changelog output
- **General** Improve the logic of getting each package changelog
- **General** Refactoring
- **Package Handler** Sort KDE package categories and add further category sdk
- **GitHub API** Enable follow redirects and update retry logic to include 403 responses triggered by GitHub primary rate limits. Retry only when x-ratelimit-remaining=0 and x-ratelimit-reset headers are present
- **GitHub API** Add page_size parameter to __get for pagination control. Changed default page size of get_package_tags to 100
- **Package Handler** Refactor get_arch_package_compare_information and better handle source URL's from .SRCINFO when no nvchecker.toml file is available
- **Config** Change default language of architecture-wording to english
- **Config** Add new field "github-personal-access-token" for later use
- **General** Refactor some log messages
- **GitHub API** Increase page size for getting commits from 30 to 100
- **GitHub API** Add pagination support

### Bug fixes

- **ArchLinux API** Prevent errors when response or results is None/empty
- **Logger** Change logger level back to WARNING
- **Package Handler** Harden extract_upstream_url_nvchecker against missing package keys
- **Config Handler** Preserve default config key order when merging user config

# 1.0.9 (2025-07-24)

### Features and enhancements

- **Web Scraper** Add extraction of repository hosting URL in .nvchecker.toml as an prioritized alternative to the upstream URL
- **GitLab API** Add method to fetch and decode file content from GitLab API
- **GitLab API** Refactor error handling
- **Test** Add tests for getting the closest package tag
- **Test** Add tests for extracting information for GitLab upstream URL's
- **GitLab API** extract_upstream_url_information now extracts the TLD too
- **GitLab API** extract_upstream_url_information can now also handle KDE URL's
- **Package Handler, GitLab API, Test** KDE packages now use the GitLab REST API instead of the old playwright implementation
- **Package Handler** Don't throw an exit when the package was found in multiple repositories, return None instead
- **GitLab API** Remove the extraction of the creation date of package tags since it is currently not relevant and not used
- **Web Scraper** Remove all references regarding the creation date of package tags since it is currently not relevant and not used
- **General** Change changelog filename from "%Y-%m-%d-changelog.json" to "%Y%m%d-%H%M-changelog.json" in order to create multiple changelog files per day
- **GitHub API** Initial version of the GitHub REST API implementation
- **Package Handler**, **Test** Extend regex of get_closest_package_tag and tests to handle additional cases
- **Package Handler** Move logic of nvchecker.toml URL extraction into a separate function and handle additional cases
- **Test** Add tests for extracting the URL out of the content of nvchecker.toml
- **General** Removed playwright as a method of extraction

### Bug fixes

- **Package Handler** Improve method to get the closest package tag. This fixes some KDE packages
- **Package Handler** Improve package tag and package changelog detection for gitlab.com URL's
- **Package Handler** Fix GitLab API URL construction for package tag retrieval and package changelog retrieval
- **General** Use the same datetime for creating and reading the changelog files
- **Package Handler** Fix wrong compare-url-tags-arch URL for the changelog file
- **Package Handler** Fix wrong compare-url-tags-origin URL for the changelog file when facing for example KDE packages
- **Package Handler** Correct docstring of find_intermediate_tags
- **Package Handler** Fixed crash regarding intermediate tags where it wanted to access the it with the outdated structure

# 1.0.8 (2025-06-15)

### Features and enhancements

- **README** Updated installation instruction
- **Config** Remove hardcoded default config and instead load the config from the supplied default config file
- **Web Scraper** Replace requests with httpx for potential future async operation
- **Web Scraper** Replaced some functions that get HTML code from websites using playwright with httpx
- **Web Scraper** Added `follow_redirects=True` for httpx to not throw errors when the URL is not exactly set up correctly
- **GitLab API** Initial version of the GitLab REST API implementation
- **ArchLinux API** Initial version of the ArchLinux API implementation
- **Package Handler** Replace complicated arch package name extraction with the local package name
- **Package Handler** ArchLinux API: First usage implementation
- **GitLab API** Add more logging output, get_commits_between_tags also send back the commit URL now and make the get function private
- **Package Handler** Replace current GitLab logic in get_package_tags() with the new GitLab API logic
- **README** Updated README
- **Package Handler** Replace difflib get_close_matches for tag comparison with rapidfuzz process for better results
- **General** Refactoring, improve GitLab API usage
- **GitLab API** Refactoring, implement retry mechanic, add a function that extracts certain information from the upstream url
- **Package Handler** Debug: Log the upstream package tags and improve some logging regarding the upstream package tags

### Bug fixes

- **Config** Add default paths to config and move config into archlog/ to be correctly included with the installation
- **Package Handler** Use package base instead of package name if available for Arch packages
- **Package Handler** Added missing parameters

# 1.0.7 (2025-05-04)

### Features and enhancements

- **General** Updated README and pyproject.toml
- **README** Added update section to README
- **General** Replaced sys.exit with exit since we log either way
- **General** Move logging into a separate file
- **Output** Added option to open changelog file after generation
- **General** Refactoring, moved code, cleanups

### Bug fixes

- **Logger** Removed redundant logging output
- **Web Scraper** Make sure that playwright will be installed when using the tool for the first time
- **Web Scraper** Quit the program directly if the architecture-wording is not set correctly due to different system language
- **Output** Make sure that the changelog is printed for each package itself instead of the entire changelog at the end
- **Web Scraper** Do not throw a CalledProcessError when `checkupdates` does not find any upgradable packages
- **General** fix: call main() in __main__.py for debugging

# 1.0.6 (2025-04-08)

### Features and enhancements

- **Package Handler** Reduced multiple similar code into a single new function: `get_package_changelog_upstream_source`
- **Package Handler** Refactoring, removed unused code, some cleanups
- **Package Handler** Improved error handling and added logging for missing responses
- **Package Handler** Refactored package tag parsing using split_package_tag and using them too with KDE packages
- **Package Handler** Refactor: Consolidate two functions regarding getting source url and source tag into one
- **Entire Script** Refactor: Standardize logging output across all files
- **Package Handler** Refactor: Simplified package source url old and new
- **Package Handler** Added the ability to get the changelog for git.kernel.org packages
- **Web Scraper** Refactor: Added and updated docstrings and type annotations
- **Web Scraper** Added custom user agent to better avoid bot-detection when using playwright
- **Package Handler** Replaced `pacman -Sy` and `pacman -Qu` commands with `checkupdates`
- **Entire Project** Refactor: restructure CLI entrypoint, XDG paths, pyproject config and dev setup

### Bug fixes

- **Package Handler** Reduce cutoff in get_close_matches to improve the detection of similar tags
- **Package Handler** Improved URL regex to handle cases without fragments
- **Package Handler** Fixed missing source tag extraction for git. URL's
- **Package Handler** Fixed wrong source url regex which did not handle all cases

# 1.0.5 (2025-02-14)

### Features and enhancements

- **Web Scraper** Reduced webscraper delay from 5 seconds to 3 seconds
- **Package Handler** Added further replacement values for Arch Gitlab packages (example gjs)
- **Package Handler** Added a check to verify if the upstream package tags differ from the Arch package tags
- **Config Handler** Added sphinx docstrings
- **Web Scraper** Move check_website_availabilty from package_handler to web_scraper
- **Package Handler** Moved the KDE package changelog logic into a separate function
- **Package Handler** Improved the detection of KDE package changelog
- **Changelog** Added compare tags URL's for arch/minor and major packages

### Bug fixes

- **Package Handler** Fix: Trailing slash handling for compare tags URLs
- **Package Handler** Fix: Handle find_all_elements for compare tags URL correctly between Github and GitLab
- **Package Handler** Fix: Switched return statements in get_upgradable_packages to exit statements
- **Package Handler** Fix: Correct condition logic for source data validation
- **Package Handler** Fix: Correct web_scraper instance for website availability check in get_package_repository
- Many small improvements
- **Config Handler** Fix: Parse UTF-8 characters correctly in the changelog file

# 1.0.4 (2025-01-02)

### Features and enhancements

- **Changelog** Added error message when no major origin package changelog was found
- **Changelog** Added package list in changelog output
- **Menu** Added a package changelog selection menu to check either single, multiple or all packages
- **Config** Added the option to change the package architecture dependent word in the config instead of in the code
- **Config** Added the option to change the delay for the web scraping in the config instead of in the code
- **README** Updated README

### Bug fixes

- **Package Handler** Removed unused variable
- **Package Handler** Fix: Call to non existent variable in get_package_architecture
- **Package Handler** Fix: NameError for 'package_architecture' when no matching line is found in the output
- **Changelog** Fix: If a changelog file from today already exists, delete it
- **External package** Fix: Updated needed playwright version due to a build error with greenlet

# 1.0.3 (2024-11-16)

### Features and enhancements

- **Logger** Changed: Default displayed logging level is now INFO instead of DEBUG
- **README** Updated README
- **LICENSE** Added LICENSE
- **Package Handler** Refactor: Added and modified logger messages
- **Package Handler** Extended KDE package changelog detection
- **Package Handler** Organized code snippets in intermediate tag handling more logically
- **Package Handler** Simplified the differentiation between github and gitlab projects since it uses the same code
- **Package Handler** Added first version of getting the changelog of Github hosted projects

### Bug fixes

- **Web Scraper** Fix: Limit Playwright to only use English as locale when crawling websites
- **Web Scraper** Fix: Added missing logger instance which could result in a crash
- **Changelog** Fix: In cases of major releases the changelog writer was confused with where to write the Arch package changelog and where to write the origin package changelog
- **Changelog** Fix: In some cases where the arch package tag and the origin package tag weren't the same it could have confused the changelog writer
- **Changelog** Fix: In case of a minor intermediate tage it was possible that the version tag was not set with the Arch tag
- **Changelog** Fix: More wrongly handed over tags in intermediate tag handling which could have led to wrong changelog tag sections
- **Package Handler** Fix: Minor label got mistaken as major in a specific case
- **Package Handler** Fix: A return case where it did not check if there already was package changelog stored and always returned None
- **Package Handler** Fix: Prevent crash in intermediate tag handling by replacing invalid list operation with string slicing

# 1.0.2 (2024-11-07)

### Features and enhancements

- **Changelog** The changelog now differentiates between Arch changes and origin package changes
- **Web Scraper** Reduce default timeout from 15s to 5s after multiple test runs
- **Package Handler** Differentiate the regex extraction regarding if the source url is a .git url or not
- **Package Handler** Differentiate between different KDE package groups to selext the correct source control URL
- **Package Handler** Refactor: Moved the code to handle intermediate tags into a separate function for better overview
- **Package Handler** Refactor: Simplified the changelog handling
- **Package Handler** Refactor: Many enhancements and fixes to the intermediate tags handling
- **Entire codebase** Refactor: Formatted the entire codebase with the Black formatter
- **Package Handler** Added: Further information in the changelog json files regarding major/minor release
- **README** Updated README
- **Package Handler** Added: More docstrings for functions and type annotations for function parameters

### Bug fixes

- **Package Handler** Fix: Prevent TypeError when appending None to package_changelog by checking return value before concatenation
- **Package Handler** Fix: Corrected access to intermediate_tags, which was mistakenly accessed through the package object
- **Package Handler** Fix: Corrected order of intermediate tags to be checked with current tag
- **Package Handler** Fix: Rare cases of no package changelog could lead to a TypeError
- **Package Handler** Fix: Change default package architecture search string to English
- **Package Handler** Fix: Missing import for type annotation types
- **Package Handler** Removed: Wrong type annotation for logger

# 1.0.1 (2024-10-06)

### Bug fixes

- **Logger:** Revert: Remove StreamHandler duplicate check as it caused issues

# 1.0.0 (2024-10-05)

### Features and enhancements

- First release