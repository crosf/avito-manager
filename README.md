# Avito Manager

Telegram-бот для управления Parser Avito.

## Возможности

- Добавление поисков Авито
- Просмотр активных поисков
- Удаление поисков
- Генерация `config.toml` для Parser Avito
- Перезапуск контейнера парсера
- Просмотр статуса контейнера парсера
- Просмотр текущей и последней версии Parser Avito
- Обновление Parser Avito из GitHub

## Команды бота

- `/start` — главное меню
- `/list` — список активных поисков
- `/reload` — обновить конфиг и перезапустить парсер
- `/version` — показать текущую и последнюю версию парсера
- `/update` — обновить парсер и перезапустить контейнер

## Стек

- Python 3
- Aiogram 3
- Docker
- SQLite
- Git

## Структура проекта

- `bot.py` — основная логика Telegram-бота и обработчики команд
- `config_generator.py` — генерация `config.toml` для Parser Avito
- `init_db.py` — создание SQLite-базы `searches.db`
- `modules/database.py` — работа с SQLite
- `modules/docker_manager.py` — работа с Docker-контейнером парсера
- `modules/parser_manager.py` — проверка версии и обновление Parser Avito

## Parser Avito

Бот работает с Parser Avito, установленным в директории:

```text
/opt/parser_avito
```

Для обновления парсера используется Git-репозиторий Parser Avito:

```text
https://github.com/Duff89/parser_avito
```

Перед обновлением бот проверяет наличие локальных изменений в папке парсера. Если локальные изменения есть, обновление останавливается, чтобы не потерять данные.

## Docker

Avito Manager работает в контейнере `avito_manager` и управляет контейнером парсера `avito` через Docker socket.

Основные volume-подключения:

- `./searches.db:/app/searches.db`
- `/var/run/docker.sock:/var/run/docker.sock`
- `/opt/parser_avito:/opt/parser_avito`

## Версии

- `v1.0` — первая стабильная версия: управление поисками, генерация конфига и перезапуск парсера
- `v1.1` — просмотр версии Parser Avito и обновление парсера из GitHub
- `v1.2` — просмотр логов
- `v1.3` — настройки

## Статус проекта

Текущая стабильная версия: **v1.0**

Текущая версия в разработке: **v1.1**
