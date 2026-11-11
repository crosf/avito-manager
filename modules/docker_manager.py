import docker
from settings import PARSER_CONTAINER_NAME


def get_docker_client():
    return docker.from_env()


def get_container():
    client = get_docker_client()
    return client.containers.get(PARSER_CONTAINER_NAME)


def restart_parser():
    container = get_container()
    container.restart()


def get_parser_status() -> str:
    try:
        container = get_container()
        return container.status
    except docker.errors.NotFound:
        return "не найден (not found)"
    except Exception as e:
        return f"ошибка: {e}"


def get_parser_logs(tail: int = 40) -> str:
    try:
        container = get_container()
        logs = container.logs(tail=tail).decode("utf-8", errors="replace")
        return logs if logs.strip() else "Логи пусты."
    except docker.errors.NotFound:
        return f"Контейнер '{PARSER_CONTAINER_NAME}' не найден."
    except Exception as e:
        return f"Ошибка при получении логов: {e}"
