#!/usr/bin/env bash
set -e

echo "=== Развертывание Avito Manager и Parser Avito на VPS ==="

# 1. Проверка прав root
if [ "$EUID" -ne 0 ]; then
  echo "Пожалуйста, запустите скрипт с правами root (sudo ./deploy.sh)"
  exit 1
fi

# 2. Установка необходимых системных пакетов
echo "--- Проверка системных пакетов (Docker, Git, curl)..."
apt-get update -qq
apt-get install -y -qq apt-transport-https ca-certificates curl gnupg lsb-release git

if ! command -v docker &> /dev/null; then
    echo "--- Установка Docker..."
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
fi

# 3. Подготовка Avito Manager
MANAGER_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$MANAGER_DIR"

if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo "--- Создание .env из .env.example..."
        cp .env.example .env
        echo "⚠️ Внимание: обязательно укажите свои BOT_TOKEN и ADMIN_IDS в файле $MANAGER_DIR/.env!"
    fi
fi

# Создаем файл базы данных до запуска контейнера, чтобы Docker не создал директорию
if [ ! -f searches.db ]; then
    touch searches.db
fi

# Читаем BOT_TOKEN и ADMIN_IDS из .env для синхронизации с парсером
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# 4. Подготовка и запуск Parser Avito (/opt/parser_avito)
PARSER_DIR="${PARSER_PATH:-/opt/parser_avito}"
if [ ! -d "$PARSER_DIR" ]; then
    echo "--- Клонирование репозитория Parser Avito в $PARSER_DIR..."
    git clone https://github.com/Duff89/parser_avito.git "$PARSER_DIR"
else
    echo "--- Директория парсера уже существует: $PARSER_DIR"
fi

cd "$PARSER_DIR"

# Подготовка необходимых файлов для Docker-контейнера парсера
if [ ! -f "config.toml" ]; then
    if [ -f "config.toml.example" ]; then
        cp config.toml.example config.toml
    else
        echo -e '[avito]\ntg_token = ""\ntg_chat_id = []\nurls = []\n' > config.toml
    fi
fi

touch database.db
mkdir -p result
if [ ! -f "cookies.json" ]; then
    echo "{}" > cookies.json
fi

# Настройка сборки из исходников в docker-compose.yml парсера для стабильной работы
if [ -f "docker-compose.yml" ]; then
    sed -i '/image: ghcr.io\/duff89\/parser_avito:latest/d' docker-compose.yml 2>/dev/null || true
    if ! grep -q "build:" docker-compose.yml; then
        sed -i '/container_name: avito/a \    build:\n      context: .\n      dockerfile: Dockerfile' docker-compose.yml
    fi
fi

# Если в .env задан BOT_TOKEN, синхронизируем его в config.toml парсера
if [ -n "$BOT_TOKEN" ] && [ -n "$ADMIN_IDS" ]; then
    echo "--- Синхронизация Telegram токена и ID чата в $PARSER_DIR/config.toml..."
    sed -i -E "s/tg_token\s*=\s*[\"'].*[\"']/tg_token = \"$BOT_TOKEN\"/g" config.toml
    sed -i -E "s/tg_chat_id\s*=\s*\[.*\]/tg_chat_id = [$ADMIN_IDS]/g" config.toml
fi

echo "--- Сборка и запуск контейнера парсера (avito)..."
docker compose build
docker compose up -d

# 5. Запуск Avito Manager
cd "$MANAGER_DIR"
echo "--- Сборка и запуск контейнера avito_manager..."
docker compose down || true
docker compose up -d --build

echo ""
echo "=== Развертывание успешно завершено! ==="
echo "Статус работающих контейнеров:"
docker ps --format "table {{.Names}}\t{{.Status}}\t{{.Image}}"
