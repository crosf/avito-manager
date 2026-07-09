import docker

PARSER_CONTAINER_NAME = "avito"


def get_container():
    client = docker.from_env()
    return client.containers.get(PARSER_CONTAINER_NAME)


def restart_parser():
    container = get_container()
    container.restart()


def get_parser_status():
    container = get_container()
    return container.status


def get_parser_logs(tail=50):
    container = get_container()
    logs = container.logs(
        tail=tail,
        timestamps=True,
    )

    return logs.decode(
        "utf-8",
        errors="replace"
    ).strip()
