import sqlite3
import docker
import asyncio

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message,
    CallbackQuery,
    BotCommand
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from settings import BOT_TOKEN
from config_generator import generate_config

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

waiting_for_url = set()


async def set_commands():
    commands = [
        BotCommand(
            command="start",
            description="Главное меню"
        ),
        BotCommand(
            command="list",
            description="Мои поиски"
        ),
        BotCommand(
            command="reload",
            description="Перезапустить парсер"
        ),
    ]

    await bot.set_my_commands(commands)


def restart_parser():
    client = docker.from_env()
    container = client.containers.get("avito")
    container.restart()


def get_main_keyboard():
    builder = InlineKeyboardBuilder()

    builder.button(
        text="➕ Добавить поиск",
        callback_data="add"
    )

    builder.button(
        text="📄 Мои поиски",
        callback_data="list"
    )

    builder.button(
        text="🔄 Перезапустить парсер",
        callback_data="reload"
    )

    builder.button(
        text="❌ Удалить поиск",
        callback_data="delete"
    )

    builder.adjust(1)

    return builder.as_markup()


@dp.message(Command("start"))
async def start(message: Message):
    await message.answer(
        "📋 Avito Manager",
        reply_markup=get_main_keyboard()
    )


@dp.message(Command("list"))
async def list_command(message: Message):

    conn = sqlite3.connect("searches.db")
    cur = conn.cursor()

    cur.execute(
        "SELECT id, url FROM searches"
    )

    rows = cur.fetchall()

    conn.close()

    if not rows:
        await message.answer("Поисков нет")
        return

    text = "📄 Активные поиски\n\n"

    for row in rows:
        text += f"{row[0]}. {row[1]}\n\n"

    await message.answer(text)


@dp.message(Command("reload"))
async def reload_command(message: Message):

    try:
        generate_config()
        restart_parser()

        await message.answer(
            "✅ Конфиг обновлён\n✅ Парсер перезапущен"
        )

    except Exception as e:

        await message.answer(
            f"❌ Ошибка:\n{e}"
        )


@dp.callback_query(F.data == "add")
async def add_search(callback: CallbackQuery):

    waiting_for_url.add(
        callback.from_user.id
    )

    await callback.message.answer(
        "Отправь ссылку поиска Авито"
    )

    await callback.answer()


@dp.message()
async def save_url(message: Message):

    if message.from_user.id not in waiting_for_url:
        return

    waiting_for_url.remove(
        message.from_user.id
    )

    url = message.text.strip()

    conn = sqlite3.connect("searches.db")
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO searches(url) VALUES(?)",
        (url,)
    )

    conn.commit()
    conn.close()

    generate_config()
    restart_parser()

    await message.answer(
        "✅ Поиск добавлен\n"
        "✅ Конфиг обновлён\n"
        "✅ Парсер перезапущен",
        reply_markup=get_main_keyboard()
    )


@dp.callback_query(F.data == "list")
async def list_searches(callback: CallbackQuery):

    conn = sqlite3.connect("searches.db")
    cur = conn.cursor()

    cur.execute(
        "SELECT id, url FROM searches"
    )

    rows = cur.fetchall()

    conn.close()

    if not rows:
        await callback.message.answer(
            "Поисков нет"
        )

        await callback.answer()
        return

    text = "📄 Активные поиски\n\n"

    for row in rows:
        text += f"{row[0]}. {row[1]}\n\n"

    await callback.message.answer(text)

    await callback.answer()


@dp.callback_query(F.data == "delete")
async def delete_menu(callback: CallbackQuery):

    conn = sqlite3.connect("searches.db")
    cur = conn.cursor()

    cur.execute(
        "SELECT id, url FROM searches"
    )

    rows = cur.fetchall()

    conn.close()

    if not rows:

        await callback.message.answer(
            "Удалять нечего"
        )

        await callback.answer()
        return

    builder = InlineKeyboardBuilder()

    for row in rows:

        builder.button(
            text=f"❌ Удалить #{row[0]}",
            callback_data=f"del_{row[0]}"
        )

    builder.adjust(1)

    await callback.message.answer(
        "Выберите поиск для удаления",
        reply_markup=builder.as_markup()
    )

    await callback.answer()


@dp.callback_query(F.data.startswith("del_"))
async def delete_search(callback: CallbackQuery):

    search_id = int(
        callback.data.replace(
            "del_",
            ""
        )
    )

    conn = sqlite3.connect("searches.db")
    cur = conn.cursor()

    cur.execute(
        "DELETE FROM searches WHERE id=?",
        (search_id,)
    )

    conn.commit()
    conn.close()

    generate_config()
    restart_parser()

    await callback.message.answer(
        "✅ Поиск удалён\n"
        "✅ Конфиг обновлён\n"
        "✅ Парсер перезапущен",
        reply_markup=get_main_keyboard()
    )

    await callback.answer()


@dp.callback_query(F.data == "reload")
async def reload_parser(callback: CallbackQuery):

    try:

        generate_config()
        restart_parser()

        await callback.message.answer(
            "✅ Конфиг обновлён\n"
            "✅ Парсер перезапущен",
            reply_markup=get_main_keyboard()
        )

    except Exception as e:

        await callback.message.answer(
            f"❌ Ошибка:\n{e}"
        )

    await callback.answer()


async def main():
    await set_commands()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
