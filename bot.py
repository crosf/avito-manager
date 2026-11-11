import asyncio
import html
import logging
from urllib.parse import urlparse

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    Message,
    CallbackQuery,
    BotCommand,
    InlineKeyboardMarkup
)
from aiogram.utils.keyboard import InlineKeyboardBuilder

from settings import BOT_TOKEN, is_admin
from config_generator import (
    generate_config,
    get_current_interval,
    set_interval,
    sync_telegram_credentials
)
from modules import database
from modules import docker_manager
from modules import parser_manager

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(name)s - %(message)s")
logger = logging.getLogger(__name__)

if not BOT_TOKEN:
    logger.warning("Внимание: BOT_TOKEN не задан! Укажите его в .env файле.")


class AddSearchState(StatesGroup):
    waiting_for_url = State()
    waiting_for_title = State()


class IntervalState(StatesGroup):
    waiting_for_minutes = State()


bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


async def set_commands():
    commands = [
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="list", description="Мои поиски"),
        BotCommand(command="interval", description="Интервал опроса"),
        BotCommand(command="reload", description="Перезапустить парсер"),
        BotCommand(command="logs", description="Логи парсера"),
        BotCommand(command="version", description="Версия парсера"),
        BotCommand(command="update", description="Обновить парсер"),
    ]
    await bot.set_my_commands(commands)


def get_main_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.button(text="➕ Добавить поиск", callback_data="add")
    builder.button(text="📄 Мои поиски", callback_data="list")
    builder.button(text="⏱ Интервал опроса", callback_data="interval_menu")
    builder.button(text="📊 Статус парсера", callback_data="status")
    builder.button(text="📋 Логи парсера", callback_data="logs")
    builder.button(text="🔄 Перезапустить парсер", callback_data="reload")
    builder.button(text="📦 Версия парсера", callback_data="version")
    builder.button(text="⬆️ Обновить парсер", callback_data="update")

    builder.adjust(2, 2, 2, 2)
    return builder.as_markup()


def get_cancel_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="❌ Отмена", callback_data="cancel_action")
    return builder.as_markup()


def get_title_step_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⏩ Пропустить (взять из ссылки)", callback_data="skip_title")
    builder.button(text="❌ Отмена", callback_data="cancel_action")
    builder.adjust(1)
    return builder.as_markup()


def get_interval_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    builder.button(text="5 мин", callback_data="set_int_300")
    builder.button(text="15 мин", callback_data="set_int_900")
    builder.button(text="30 мин", callback_data="set_int_1800")
    builder.button(text="1 час", callback_data="set_int_3600")
    builder.button(text="2 часа", callback_data="set_int_7200")
    builder.button(text="✏️ Ввести вручную", callback_data="custom_interval")
    builder.button(text="🔙 Назад в меню", callback_data="back_to_main")

    builder.adjust(3, 2, 1, 1)
    return builder.as_markup()


def format_version_message(info: dict) -> str:
    if info.get("update_available"):
        status = "⬆️ Доступно обновление"
    else:
        status = "✅ Установлена актуальная версия"

    return (
        "📦 <b>Версия парсера</b>\n\n"
        f"Текущая версия: <code>{html.escape(str(info.get('local_version', 'unknown')))}</code>\n"
        f"Последняя версия: <code>{html.escape(str(info.get('latest_version', 'unknown')))}</code>\n"
        f"Статус: {status}"
    )


# --- Команда /start ---
@dp.message(Command("start"))
async def start(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    await state.clear()
    total = await asyncio.to_thread(database.count_searches, False)
    active = await asyncio.to_thread(database.count_searches, True)
    interval_info = await asyncio.to_thread(get_current_interval)

    text = (
        "📋 <b>Avito Manager</b>\n"
        "Панель управления парсером Авито.\n\n"
        f"🔍 Активных поисков: <b>{active}</b> из {total}\n"
        f"⏱ Частота поиска: <b>{interval_info['human']}</b>"
    )
    await message.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())


# --- Раздел: Интервал поиска ---
async def render_interval_screen(target, is_callback: bool = True):
    interval_info = await asyncio.to_thread(get_current_interval)
    text = (
        "⏱ <b>Интервал опроса поисков</b>\n\n"
        f"Текущая частота: <b>{interval_info['human']}</b>\n"
        f"<i>(парсер проходит все активные ссылки и засыпает на это время перед новым кругом)</i>\n\n"
        "Выберите новый интервал кнопкой или введите вручную в минутах:"
    )
    markup = get_interval_keyboard()
    if is_callback:
        await target.edit_text(text, parse_mode="HTML", reply_markup=markup)
    else:
        await target.answer(text, parse_mode="HTML", reply_markup=markup)


@dp.callback_query(F.data == "interval_menu")
async def interval_menu_cb(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    await state.clear()
    await render_interval_screen(callback.message, is_callback=True)
    await callback.answer()


@dp.message(Command("interval"))
async def interval_command(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await render_interval_screen(message, is_callback=False)


@dp.callback_query(F.data.startswith("set_int_"))
async def set_preset_interval(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return

    seconds = int(callback.data.replace("set_int_", ""))
    await callback.message.edit_text("⏳ Применяем интервал и перезапускаем парсер...")

    try:
        await asyncio.to_thread(set_interval, seconds)
        await asyncio.to_thread(docker_manager.restart_parser)
        interval_info = await asyncio.to_thread(get_current_interval)

        await callback.message.edit_text(
            f"✅ <b>Интервал успешно установлен:</b> {interval_info['human']}!\n"
            f"✅ Парсер перезапущен с новым расписанием.",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        await callback.message.edit_text(
            f"❌ Ошибка установки интервала:\n<code>{html.escape(str(e))}</code>",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
    await callback.answer()


@dp.callback_query(F.data == "custom_interval")
async def custom_interval_cb(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return

    await state.set_state(IntervalState.waiting_for_minutes)
    await callback.message.edit_text(
        "✏️ <b>Введите интервал опроса в минутах:</b>\n"
        "(например: <code>10</code>, <code>45</code> или <code>120</code>)",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()


@dp.message(IntervalState.waiting_for_minutes)
async def process_custom_interval(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    text = message.text.strip()
    if not text.isdigit() or int(text) < 1:
        await message.answer(
            "⚠️ Пожалуйста, введите положительное целое число минут (минимум 1 мин):\n"
            "Попробуйте ещё раз или нажмите «Отмена».",
            reply_markup=get_cancel_keyboard()
        )
        return

    minutes = int(text)
    if minutes > 1440:  # максимум 24 часа
        await message.answer("⚠️ Максимальный интервал — 1440 минут (24 часа). Введите меньшее число.")
        return

    await state.clear()
    seconds = minutes * 60

    wait_msg = await message.answer("⏳ Сохраняем настройку и перезапускаем парсер...")
    try:
        await asyncio.to_thread(set_interval, seconds)
        await asyncio.to_thread(docker_manager.restart_parser)
        interval_info = await asyncio.to_thread(get_current_interval)

        await wait_msg.edit_text(
            f"✅ <b>Интервал успешно установлен:</b> {interval_info['human']}!\n"
            f"✅ Парсер перезапущен.",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        await wait_msg.edit_text(
            f"❌ Ошибка:\n<code>{html.escape(str(e))}</code>",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )


# --- Раздел: Добавление поиска (2 шага: Ссылка -> Название) ---
@dp.callback_query(F.data == "add")
async def add_search_handler(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return

    await state.set_state(AddSearchState.waiting_for_url)
    await callback.message.answer(
        "🔗 <b>Шаг 1 из 2: Отправьте ссылку на поиск Авито:</b>\n"
        "Например:\n<code>https://www.avito.ru/moskva/telefony?q=iphone+15</code>",
        parse_mode="HTML",
        reply_markup=get_cancel_keyboard()
    )
    await callback.answer()


@dp.message(AddSearchState.waiting_for_url)
async def process_save_url_step1(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    url = message.text.strip()
    parsed = urlparse(url)

    if not parsed.scheme or not parsed.netloc:
        await message.answer(
            "⚠️ Пожалуйста, отправьте корректную ссылку, начинающуюся с http:// или https://\n"
            "Попробуйте ещё раз или нажмите «Отмена».",
            reply_markup=get_cancel_keyboard()
        )
        return

    # Сохраняем url в контекст FSM и запрашиваем название
    await state.update_data(url=url)
    await state.set_state(AddSearchState.waiting_for_title)

    default_name = database.extract_default_title(url)
    await message.answer(
        f"🏷 <b>Шаг 2 из 2: Введите название для этого поиска:</b>\n\n"
        f"Автоматическое имя: <i>{html.escape(default_name)}</i>\n\n"
        f"Отправьте своё название (например: <code>iPhone 15 до 50k</code>) "
        f"или нажмите «⏩ Пропустить», чтобы использовать автоматическое.",
        parse_mode="HTML",
        reply_markup=get_title_step_keyboard()
    )


@dp.callback_query(F.data == "skip_title")
async def skip_title_handler(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return

    data = await state.get_data()
    url = data.get("url")
    if not url:
        await state.clear()
        await callback.message.answer("⚠️ Сессия истекла. Начните добавление заново.", reply_markup=get_main_keyboard())
        await callback.answer()
        return

    await state.clear()
    await finish_add_search(callback.message, url, title=None, edit=True)
    await callback.answer()


@dp.message(AddSearchState.waiting_for_title)
async def process_save_title_step2(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return

    title = message.text.strip()
    data = await state.get_data()
    url = data.get("url")
    await state.clear()

    if not url:
        await message.answer("⚠️ Ошибка: ссылка не найдена. Начните сначала.", reply_markup=get_main_keyboard())
        return

    await finish_add_search(message, url, title=title, edit=False)


async def finish_add_search(target_msg: Message, url: str, title: str = None, edit: bool = False):
    wait_text = "⏳ Сохраняем поиск, обновляем конфиг и перезапускаем парсер..."
    if edit:
        wait_msg = await target_msg.edit_text(wait_text)
    else:
        wait_msg = await target_msg.answer(wait_text)

    try:
        await asyncio.to_thread(database.add_search, url, title)
        count = await asyncio.to_thread(generate_config)
        await asyncio.to_thread(docker_manager.restart_parser)

        # Получаем добавленный поиск
        searches = await asyncio.to_thread(database.get_searches)
        saved_title = title or database.extract_default_title(url)

        await wait_msg.edit_text(
            f"✅ <b>Поиск успешно добавлен!</b>\n\n"
            f"🏷 Название: <b>{html.escape(saved_title)}</b>\n"
            f"🟢 Статус: <b>Активен (сканируется)</b>\n"
            f"📊 Всего активных поисков: <b>{count}</b>\n"
            f"✅ Конфиг обновлён и парсер перезапущен.",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        await wait_msg.edit_text(
            f"❌ Ошибка при добавлении:\n<code>{html.escape(str(e))}</code>",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )


# --- Раздел: Мои поиски (список, пауза/старт, удаление) ---
async def render_searches_list(target, is_callback: bool = True):
    rows = await asyncio.to_thread(database.get_searches)
    if not rows:
        text = "📭 У вас пока нет сохранённых поисков.\nНажмите <b>«➕ Добавить поиск»</b>, чтобы создать первый."
        if is_callback:
            await target.edit_text(text, parse_mode="HTML", reply_markup=get_main_keyboard())
        else:
            await target.answer(text, parse_mode="HTML", reply_markup=get_main_keyboard())
        return

    total = len(rows)
    active = sum(1 for r in rows if r[3] == 1)

    text = (
        f"📄 <b>Мои поиски ({active} активных из {total}):</b>\n\n"
        "🟢 — активен (сканируется парсером)\n"
        "⏸ — на паузе (временно выключен)\n\n"
        "<i>Нажмите на кнопку поиска ниже, чтобы поставить на паузу, запустить или удалить:</i>\n\n"
    )

    builder = InlineKeyboardBuilder()
    for num, row in enumerate(rows, start=1):
        s_id, url, title, is_active = row
        display_title = title or database.extract_default_title(url)
        status_icon = "🟢" if is_active == 1 else "⏸"

        text += f"{num}. {status_icon} <b>{html.escape(display_title)}</b>\n🔗 <a href=\"{html.escape(url)}\">Открыть на Avito</a>\n\n"
        btn_text = f"{status_icon} [{num}] {display_title[:24]}"
        builder.button(text=btn_text, callback_data=f"item_{s_id}")

    builder.button(text="➕ Добавить поиск", callback_data="add")
    builder.button(text="🔙 Главное меню", callback_data="back_to_main")
    builder.adjust(1)

    if is_callback:
        await target.edit_text(text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=builder.as_markup())
    else:
        await target.answer(text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=builder.as_markup())


@dp.callback_query(F.data == "list")
async def list_searches_cb(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return
    await state.clear()
    await render_searches_list(callback.message, is_callback=True)
    await callback.answer()


@dp.message(Command("list"))
async def list_command(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id):
        return
    await state.clear()
    await render_searches_list(message, is_callback=False)


# Меню конкретного поиска
@dp.callback_query(F.data.startswith("item_"))
async def search_item_menu(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return

    search_id = int(callback.data.replace("item_", ""))
    row = await asyncio.to_thread(database.get_search, search_id)

    if not row:
        await callback.answer("⚠️ Поиск не найден или был удалён", show_alert=True)
        await render_searches_list(callback.message, is_callback=True)
        return

    s_id, url, title, is_active = row
    display_title = title or database.extract_default_title(url)

    if is_active == 1:
        status_text = "🟢 <b>Активен</b> (проверяется парсером)"
        toggle_btn_text = "⏸ Поставить на паузу"
    else:
        status_text = "⏸ <b>На паузе</b> (временно не сканируется)"
        toggle_btn_text = "▶️ Включить поиск"

    text = (
        f"🔍 <b>Управление поиском</b>\n\n"
        f"🏷 <b>Название:</b> {html.escape(display_title)}\n"
        f"📊 <b>Статус:</b> {status_text}\n"
        f"🔗 <b>Ссылка:</b> <a href=\"{html.escape(url)}\">{html.escape(url)}</a>"
    )

    builder = InlineKeyboardBuilder()
    builder.button(text=toggle_btn_text, callback_data=f"toggle_{s_id}")
    builder.button(text="❌ Удалить этот поиск", callback_data=f"del_{s_id}")
    builder.button(text="🔙 К списку поисков", callback_data="list")
    builder.adjust(1)

    await callback.message.edit_text(text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=builder.as_markup())
    await callback.answer()


# Переключение активности поиска (Пауза / Старт)
@dp.callback_query(F.data.startswith("toggle_"))
async def toggle_search_status_cb(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return

    search_id = int(callback.data.replace("toggle_", ""))
    new_state = await asyncio.to_thread(database.toggle_search_active, search_id)

    if new_state is None:
        await callback.answer("⚠️ Поиск не найден", show_alert=True)
        return

    action_name = "включен" if new_state == 1 else "поставлен на паузу"
    await callback.message.edit_text(f"⏳ Поиск {action_name}. Обновляем конфигурацию...")

    try:
        count = await asyncio.to_thread(generate_config)
        await asyncio.to_thread(docker_manager.restart_parser)
        await callback.answer(f"Поиск {action_name}!", show_alert=False)
    except Exception as e:
        logger.error(f"Ошибка при перезапуске парсера: {e}")

    # Возвращаемся в карточку этого же поиска
    row = await asyncio.to_thread(database.get_search, search_id)
    if row:
        s_id, url, title, is_active = row
        display_title = title or database.extract_default_title(url)
        status_text = "🟢 <b>Активен</b> (проверяется парсером)" if is_active == 1 else "⏸ <b>На паузе</b> (не сканируется)"
        toggle_btn_text = "⏸ Поставить на паузу" if is_active == 1 else "▶️ Включить поиск"

        text = (
            f"🔍 <b>Управление поиском</b>\n\n"
            f"🏷 <b>Название:</b> {html.escape(display_title)}\n"
            f"📊 <b>Статус:</b> {status_text}\n"
            f"🔗 <b>Ссылка:</b> <a href=\"{html.escape(url)}\">{html.escape(url)}</a>\n\n"
            f"<i>Конфигурация парсера обновлена (активных ссылок: {count}).</i>"
        )
        builder = InlineKeyboardBuilder()
        builder.button(text=toggle_btn_text, callback_data=f"toggle_{s_id}")
        builder.button(text="❌ Удалить этот поиск", callback_data=f"del_{s_id}")
        builder.button(text="🔙 К списку поисков", callback_data="list")
        builder.adjust(1)

        await callback.message.edit_text(text, parse_mode="HTML", disable_web_page_preview=True, reply_markup=builder.as_markup())


# Удаление поиска
@dp.callback_query(F.data.startswith("del_"))
async def delete_search_cb(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return

    search_id = int(callback.data.replace("del_", ""))
    await callback.message.edit_text("⏳ Удаляем поиск и перезапускаем парсер...")

    try:
        await asyncio.to_thread(database.delete_search, search_id)
        count = await asyncio.to_thread(generate_config)
        await asyncio.to_thread(docker_manager.restart_parser)

        await callback.message.edit_text(
            f"✅ Поиск успешно удалён!\n"
            f"📊 Активных поисков осталось: <b>{count}</b>\n"
            f"✅ Конфиг обновлён и парсер перезапущен.",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        await callback.message.edit_text(
            f"❌ Ошибка при удалении:\n<code>{html.escape(str(e))}</code>",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
    await callback.answer()


# --- Перезапуск парсера ---
@dp.message(Command("reload"))
@dp.callback_query(F.data == "reload")
async def reload_parser_action(event):
    user_id = event.from_user.id
    if not is_admin(user_id):
        return

    msg = event.message if isinstance(event, CallbackQuery) else event
    wait_msg = await msg.answer("⏳ Обновляем конфигурацию и перезапускаем парсер...")
    try:
        count = await asyncio.to_thread(generate_config)
        await asyncio.to_thread(docker_manager.restart_parser)
        await wait_msg.edit_text(
            f"✅ Конфиг обновлён (активных поисков: <b>{count}</b>)\n"
            f"✅ Парсер успешно перезапущен",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        await wait_msg.edit_text(f"❌ Ошибка:\n<code>{html.escape(str(e))}</code>", parse_mode="HTML")

    if isinstance(event, CallbackQuery):
        await event.answer()


# --- Статус парсера ---
@dp.callback_query(F.data == "status")
async def parser_status_cb(callback: CallbackQuery):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return

    try:
        status = await asyncio.to_thread(docker_manager.get_parser_status)
        total = await asyncio.to_thread(database.count_searches, False)
        active = await asyncio.to_thread(database.count_searches, True)
        interval_info = await asyncio.to_thread(get_current_interval)

        await callback.message.answer(
            f"📊 <b>Статус парсера</b>\n\n"
            f"🐳 Контейнер: <code>avito</code>\n"
            f"⚙️ Состояние: <b>{html.escape(str(status))}</b>\n"
            f"⏱ Интервал опроса: <b>{interval_info['human']}</b>\n"
            f"🟢 Активных поисков: <b>{active}</b> (всего в базе: {total})",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка:\n<code>{html.escape(str(e))}</code>", parse_mode="HTML")

    await callback.answer()


# --- Логи парсера ---
@dp.message(Command("logs"))
@dp.callback_query(F.data == "logs")
async def parser_logs_action(event):
    user_id = event.from_user.id
    if not is_admin(user_id):
        return

    msg = event.message if isinstance(event, CallbackQuery) else event
    logs = await asyncio.to_thread(docker_manager.get_parser_logs, 35)
    if len(logs) > 3500:
        logs = logs[-3500:]

    escaped_logs = html.escape(logs)
    await msg.answer(
        f"📋 <b>Последние логи парсера:</b>\n<pre><code>{escaped_logs}</code></pre>",
        parse_mode="HTML",
        reply_markup=get_main_keyboard()
    )
    if isinstance(event, CallbackQuery):
        await event.answer()


# --- Версия и обновление парсера ---
async def send_parser_version(message: Message):
    wait_msg = await message.answer("⏳ Проверяем версию на GitHub...")
    try:
        info = await asyncio.to_thread(parser_manager.get_version_info)
        await wait_msg.edit_text(
            format_version_message(info),
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        await wait_msg.edit_text(f"❌ Ошибка проверки версии:\n<code>{html.escape(str(e))}</code>", parse_mode="HTML")


async def update_parser_and_restart(message: Message):
    wait_msg = await message.answer("⏳ Проверяем и обновляем парсер...")
    try:
        result = await asyncio.to_thread(parser_manager.update_parser)
        info = {
            "local_version": result["local_version"],
            "latest_version": result["latest_version"],
            "update_available": result["local_version"] != result["latest_version"],
        }

        if result["updated"]:
            await asyncio.to_thread(docker_manager.restart_parser)
            title = "✅ Парсер обновлён\n✅ Контейнер перезапущен"
        else:
            title = "✅ Обновление не требуется\n✅ Контейнер не перезапускался"

        output_text = html.escape(result.get("output", ""))
        await wait_msg.edit_text(
            f"{title}\n\n"
            f"{format_version_message(info)}\n\n"
            f"<b>Git:</b>\n<code>{output_text}</code>",
            parse_mode="HTML",
            reply_markup=get_main_keyboard()
        )
    except Exception as e:
        await wait_msg.edit_text(f"❌ Ошибка обновления парсера:\n<code>{html.escape(str(e))}</code>", parse_mode="HTML")


@dp.message(Command("version"))
@dp.callback_query(F.data == "version")
async def version_action(event):
    if not is_admin(event.from_user.id):
        return
    msg = event.message if isinstance(event, CallbackQuery) else event
    await send_parser_version(msg)
    if isinstance(event, CallbackQuery):
        await event.answer()


@dp.message(Command("update"))
@dp.callback_query(F.data == "update")
async def update_action(event):
    if not is_admin(event.from_user.id):
        return
    msg = event.message if isinstance(event, CallbackQuery) else event
    await update_parser_and_restart(msg)
    if isinstance(event, CallbackQuery):
        await event.answer()


# --- Отмена и Назад ---
@dp.callback_query(F.data == "cancel_action")
async def cancel_handler(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return

    await state.clear()
    await callback.message.edit_text("❌ Действие отменено.", reply_markup=get_main_keyboard())
    await callback.answer()


@dp.callback_query(F.data == "back_to_main")
async def back_to_main_cb(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id):
        await callback.answer("⛔ Доступ запрещён", show_alert=True)
        return

    await state.clear()
    total = await asyncio.to_thread(database.count_searches, False)
    active = await asyncio.to_thread(database.count_searches, True)
    interval_info = await asyncio.to_thread(get_current_interval)

    text = (
        "📋 <b>Avito Manager</b>\n"
        "Панель управления парсером Авито.\n\n"
        f"🔍 Активных поисков: <b>{active}</b> из {total}\n"
        f"⏱ Частота поиска: <b>{interval_info['human']}</b>"
    )
    await callback.message.edit_text(text, parse_mode="HTML", reply_markup=get_main_keyboard())
    await callback.answer()


async def main():
    logger.info("Инициализация базы данных...")
    database.init_db()

    # Синхронизируем токен и ID чата в конфиге парсера, если он доступен
    try:
        from settings import ADMIN_IDS
        sync_telegram_credentials(BOT_TOKEN, list(ADMIN_IDS))
        logger.info("Telegram credentials синхронизированы с конфигом парсера.")
    except Exception as e:
        logger.warning(f"Не удалось синхронизировать telegram credentials в config.toml: {e}")

    logger.info("Установка команд меню бота...")
    await set_commands()

    logger.info("Запуск polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Бот остановлен.")
