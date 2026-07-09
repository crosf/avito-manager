import re
import subprocess
from pathlib import Path

PARSER_PATH = Path("/opt/parser_avito")
REMOTE_NAME = "origin"
REMOTE_BRANCH = "master"
VERSION_FILE = "version.py"
VERSION_PATTERN = re.compile(r'VERSION\s*=\s*["\']([^"\']+)["\']')
README_VERSION_PATTERN = re.compile(r'В версии\s+([0-9]+(?:\.[0-9]+)+)')


class ParserManagerError(Exception):
    pass


def run_git_command(*args):
    result = subprocess.run(
        ["git", "-C", str(PARSER_PATH), *args],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise ParserManagerError(message)

    return result.stdout.strip()


def parse_version(content):
    match = VERSION_PATTERN.search(content)

    if not match:
        return "unknown"

    return match.group(1)


def parse_readme_version(content):
    match = README_VERSION_PATTERN.search(content)

    if not match:
        return "unknown"

    return match.group(1)


def get_local_version():
    version_path = PARSER_PATH / VERSION_FILE

    if not version_path.exists():
        return "unknown"

    return parse_version(
        version_path.read_text(encoding="utf-8")
    )


def fetch_updates():
    run_git_command("fetch", REMOTE_NAME, REMOTE_BRANCH, "--tags")


def get_latest_version():
    fetch_updates()

    readme_content = run_git_command(
        "show",
        f"{REMOTE_NAME}/{REMOTE_BRANCH}:README.md",
    )
    readme_version = parse_readme_version(readme_content)

    if readme_version != "unknown":
        return readme_version

    version_content = run_git_command(
        "show",
        f"{REMOTE_NAME}/{REMOTE_BRANCH}:{VERSION_FILE}",
    )

    return parse_version(version_content)


def has_local_changes():
    return bool(run_git_command("status", "--short"))


def get_version_info():
    local_version = get_local_version()
    latest_version = get_latest_version()

    return {
        "local_version": local_version,
        "latest_version": latest_version,
        "update_available": local_version != latest_version,
    }


def update_parser():
    local_version = get_local_version()
    latest_version = get_latest_version()

    if local_version == latest_version:
        return {
            "updated": False,
            "local_version": local_version,
            "latest_version": latest_version,
            "output": "Установлена актуальная версия. Обновление не требуется.",
        }

    output = run_git_command(
        "pull",
        "--ff-only",
        "--autostash",
        REMOTE_NAME,
        REMOTE_BRANCH,
    )

    return {
        "updated": True,
        "local_version": get_local_version(),
        "latest_version": latest_version,
        "output": output or "Парсер обновлён",
    }
