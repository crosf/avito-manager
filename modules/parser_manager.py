import re
import subprocess
from pathlib import Path
from settings import PARSER_PATH

REMOTE_NAME = "origin"
REMOTE_BRANCH = "master"
VERSION_FILE = "version.py"
VERSION_PATTERN = re.compile(r'VERSION\s*=\s*["\']([^"\']+)["\']')
README_VERSION_PATTERN = re.compile(r'В версии\s+([0-9]+(?:\.[0-9]+)+)')


class ParserManagerError(Exception):
    pass


def get_parser_dir() -> Path:
    return Path(PARSER_PATH)


def run_git_command(*args):
    parser_dir = get_parser_dir()
    if not parser_dir.exists():
        raise ParserManagerError(f"Директория парсера не найдена: {parser_dir}")

    result = subprocess.run(
        ["git", "-C", str(parser_dir), *args],
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 0:
        message = result.stderr.strip() or result.stdout.strip()
        raise ParserManagerError(message or f"Команда git {' '.join(args)} завершилась с ошибкой.")

    return result.stdout.strip()


def parse_version(content: str) -> str:
    match = VERSION_PATTERN.search(content)
    if not match:
        return "unknown"
    return match.group(1)


def parse_readme_version(content: str) -> str:
    match = README_VERSION_PATTERN.search(content)
    if not match:
        return "unknown"
    return match.group(1)


def get_local_version() -> str:
    version_path = get_parser_dir() / VERSION_FILE
    if not version_path.exists():
        return "unknown"

    return parse_version(version_path.read_text(encoding="utf-8"))


def fetch_updates():
    run_git_command("fetch", REMOTE_NAME, REMOTE_BRANCH, "--tags")


def get_latest_version() -> str:
    fetch_updates()

    try:
        readme_content = run_git_command(
            "show",
            f"{REMOTE_NAME}/{REMOTE_BRANCH}:README.md",
        )
        readme_version = parse_readme_version(readme_content)
        if readme_version != "unknown":
            return readme_version
    except Exception:
        pass

    try:
        version_content = run_git_command(
            "show",
            f"{REMOTE_NAME}/{REMOTE_BRANCH}:{VERSION_FILE}",
        )
        return parse_version(version_content)
    except Exception:
        return "unknown"


def has_local_changes() -> bool:
    output = run_git_command("status", "--short")
    return bool(output.strip())


def get_version_info() -> dict:
    local_version = get_local_version()
    latest_version = get_latest_version()

    return {
        "local_version": local_version,
        "latest_version": latest_version,
        "update_available": local_version != latest_version and latest_version != "unknown",
    }


def update_parser() -> dict:
    # Проверка на наличие локальных изменений перед обновлением
    if has_local_changes():
        raise ParserManagerError(
            "В директории парсера обнаружены локальные изменения!\n"
            "Обновление прервано, чтобы избежать потери данных или конфликтов."
        )

    local_version = get_local_version()
    latest_version = get_latest_version()

    if local_version == latest_version and latest_version != "unknown":
        return {
            "updated": False,
            "local_version": local_version,
            "latest_version": latest_version,
            "output": "Установлена актуальная версия. Обновление не требуется.",
        }

    output = run_git_command(
        "pull",
        "--ff-only",
        REMOTE_NAME,
        REMOTE_BRANCH,
    )

    return {
        "updated": True,
        "local_version": get_local_version(),
        "latest_version": latest_version,
        "output": output or "Парсер успешно обновлён",
    }
