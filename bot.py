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
from modules import database
from modules import docker_manager
from modules import parser_manager

ADMIN_ID = 434877678

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

waiting_for_url = set()

def is_admin(user_id):
    return user_id == ADMIN_ID


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
        BotCommand(
            command="version",
            description="Версия парсера"
        ),
        BotCommand(
            command="update",
            description="Обновить парсер"
        ),
    ]

    await bot.set_my_commands(commands)

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
        text="📦 Версия парсера",
        callback_data="version"
    )

    builder.button(
        text="⬆️ Обновить парсер",
        callback_data="update"
    )

    builder.button(
        text="📊 Статус парсера",
        callback_data="status"
    )

    builder.button(
        text="❌ Удалить поиск",
        callback_data="delete"
    )

    builder.adjust(1)

    return builder.as_markup()

def format_version_message(info):
    if info["update_available"]:
        status = "⬆️ Доступно обновление"
    else:
        status = "✅ Установлена актуальная версия"

    return (
        "📦 Версия парсера\n\n"
        f"Текущая версия: {info['local_version']}\n"
        f"Последняя версия: {info['latest_version']}\n"
        f"Статус: {status}"
    )


async def send_parser_version(message):
    try:

        info = parser_manager.get_version_info()

        await message.answer(
            format_version_message(info),
            reply_markup=get_main_keyboard()
        )

    except Exception as e:

        await message.answer(
            f"❌ Ошибка проверки версии:\n{e}"
        )


async def update_parser_and_restart(message):
    try:

        result = parser_manager.update_parser()
        info = {
            "local_version": result["local_version"],
            "latest_version": result["latest_version"],
            "update_available": result["local_version"] != result["latest_version"],
        }

        if result["updated"]:
            docker_manager.restart_parser()
            title = "✅ Парсер обновлён\n✅ Парсер перезапущен"
        else:
            title = "✅ Обновление не требуется\n✅ Парсер не перезапускался"

        await message.answer(
            f"{title}\n\n"
            f"{format_version_message(info)}\n\n"
            f"Git:\n{result['output']}",
            reply_markup=get_main_keyboard()
        )

    except Exception as e:

        await message.answer(
            f"❌ Ошибка обновления парсера:\n{e}"
        )

@dp.message(Command("start"))
async def start(message: Message):

    if not is_admin(message.from_user.id):
        return

    await message.answer(
        "📋 Avito Manager",
        reply_markup=get_main_keyboard()
    )

@dp.message(Command("list"))
async def list_command(message: Message):

    if not is_admin(message.from_user.id):
        return

    rows = database.get_searches()

    if not rows:
        await message.answer("Поисков нет")
        return

    text = "📄 Активные поиски\n\n"

    for num, row in enumerate(rows, start=1):
        text += f"{num}. {row[1]}\n\n"

    await message.answer(text)

@dp.message(Command("reload"))
async def reload_command(message: Message):

    if not is_admin(message.from_user.id):
        return

    try:

        generate_config()
        docker_manager.restart_parser()

        await message.answer(
            "✅ Конфиг обновлён\n✅ Парсер перезапущен"
        )

    except Exception as e:

        await message.answer(
            f"❌ Ошибка:\n{e}"
        )

@dp.message(Command("version"))
async def version_command(message: Message):

    if not is_admin(message.from_user.id):
        return

    await send_parser_version(message)

@dp.message(Command("update"))
async def update_command(message: Message):

    if not is_admin(message.from_user.id):
        return

    await update_parser_and_restart(message)

@dp.callback_query(F.data == "add")
async def add_search(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён")
        return

    waiting_for_url.add(
        callback.from_user.id
    )

    await callback.message.answer(
        "Отправь ссылку поиска Авито"
    )

    await callback.answer()

@dp.message()
async def save_url(message: Message):

    if not is_admin(message.from_user.id):
        return

    if message.from_user.id not in waiting_for_url:
        return

    waiting_for_url.remove(
        message.from_user.id
    )

    url = message.text.strip()

    database.add_search(url)

    generate_config()
    docker_manager.restart_parser()

    await message.answer(
        "✅ Поиск добавлен\n"
        "✅ Конфиг обновлён\n"
        "✅ Парсер перезапущен",
        reply_markup=get_main_keyboard()
    )

@dp.callback_query(F.data == "list")
async def list_searches(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён")
        return

    rows = database.get_searches()

    if not rows:
        await callback.message.answer(
            "Поисков нет"
        )

        await callback.answer()
        return

    text = "📄 Активные поиски\n\n"

    for num, row in enumerate(rows, start=1):
        text += f"{num}. {row[1]}\n\n"

    await callback.message.answer(text)

    await callback.answer()

@dp.callback_query(F.data == "delete")
async def delete_menu(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён")
        return

    rows = database.get_searches()

    if not rows:

        await callback.message.answer(
            "Удалять нечего"
        )

        await callback.answer()
        return

    builder = InlineKeyboardBuilder()

    for row in rows:

        url = row[1]

        if "q=" in url:
            title = url.split("q=")[-1][:30]
        else:
            title = url.split("/")[-1][:30]

        builder.button(
            text=f"❌ {title}",
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

    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён")
        return

    search_id = int(
        callback.data.replace(
            "del_",
            ""
        )
    )

    database.delete_search(search_id)

    generate_config()
    docker_manager.restart_parser()

    await callback.message.answer(
        "✅ Поиск удалён\n"
        "✅ Конфиг обновлён\n"
        "✅ Парсер перезапущен",
        reply_markup=get_main_keyboard()
    )

    await callback.answer()

@dp.callback_query(F.data == "reload")
async def reload_parser(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён")
        return

    try:

        generate_config()
        docker_manager.restart_parser()

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

@dp.callback_query(F.data == "version")
async def parser_version(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён")
        return

    await send_parser_version(callback.message)

    await callback.answer()

@dp.callback_query(F.data == "update")
async def update_parser(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён")
        return

    await update_parser_and_restart(callback.message)

    await callback.answer()

@dp.callback_query(F.data == "status")
async def parser_status(callback: CallbackQuery):

    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён")
        return

    try:

        status = docker_manager.get_parser_status()
        count = database.count_searches()

        await callback.message.answer(
            f"📊 Статус парсера\n\n"
            f"Контейнер: avito\n"
            f"Статус: {status}\n"
            f"Поисков: {count}"
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
