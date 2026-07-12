import asyncio
import logging
import os
import random
import secrets
import sqlite3
from datetime import datetime
from html import escape
from pathlib import Path
from typing import Any

import gspread
from aiogram import Bot, Dispatcher, F, Router
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
)
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
ADMIN_CHAT_ID = int(os.getenv("ADMIN_CHAT_ID", "0"))
ADMIN_IDS = {
    int(x.strip())
    for x in os.getenv("ADMIN_IDS", "").split(",")
    if x.strip().lstrip("-").isdigit()
}

GOS_SPREADSHEET_ID = os.getenv("GOS_SPREADSHEET_ID", "").strip()
MVD_SPREADSHEET_ID = os.getenv("MVD_SPREADSHEET_ID", "").strip()
GOOGLE_CREDENTIALS_FILE = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json").strip()
DATA_DIR = Path(os.getenv("DATA_DIR", "/app/data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / os.getenv("DB_PATH", "uslugigoss.db")

if not BOT_TOKEN:
    raise RuntimeError("В .env не указан BOT_TOKEN")
if not ADMIN_CHAT_ID:
    raise RuntimeError("В .env не указан ADMIN_CHAT_ID")
if not GOS_SPREADSHEET_ID:
    raise RuntimeError("В .env не указан GOS_SPREADSHEET_ID")
if not MVD_SPREADSHEET_ID:
    raise RuntimeError("В .env не указан MVD_SPREADSHEET_ID")
if not Path(GOOGLE_CREDENTIALS_FILE).exists():
    raise RuntimeError(f"Не найден Google-ключ: {GOOGLE_CREDENTIALS_FILE}")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

router = Router()

# -------------------- Состояния --------------------

class Registration(StatesGroup):
    fio = State()
    age = State()
    birthdate = State()
    sex = State()
    citizenship_primary = State()
    citizenship_secondary = State()
    nationality = State()
    skin = State()
    hair = State()
    eyes = State()
    appearance = State()
    military = State()
    photo = State()


class Medical(StatesGroup):
    height = State()
    weight = State()
    blood = State()
    allergies = State()
    chronic = State()
    notes = State()


class LicenseFlow(StatesGroup):
    test = State()
    payment = State()


class AdminFlow(StatesGroup):
    reject_reason = State()
    search_query = State()
    edit_passport = State()
    edit_field = State()
    edit_value = State()
    fine_passport = State()
    fine_amount = State()
    fine_reason = State()
    wanted_passport = State()
    wanted_reason = State()
    status_passport = State()


# -------------------- Меню --------------------

MAIN_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="👤 Мой персонаж"), KeyboardButton(text="🆕 Регистрация")],
        [KeyboardButton(text="🩺 Медкарта"), KeyboardButton(text="📄 Документы")],
        [KeyboardButton(text="🚗 Лицензии"), KeyboardButton(text="💸 Штрафы")],
        [KeyboardButton(text="🚨 Розыск")],
    ],
    resize_keyboard=True,
    input_field_placeholder="Выберите услугу",
)

CANCEL_MENU = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="❌ Отмена")]],
    resize_keyboard=True,
)

SEX_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Мужчина"), KeyboardButton(text="Женщина")],
        [KeyboardButton(text="❌ Отмена")],
    ],
    resize_keyboard=True,
)

YES_NO_MENU = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Да"), KeyboardButton(text="Нет")],
        [KeyboardButton(text="❌ Отмена")],
    ],
    resize_keyboard=True,
)


# -------------------- Справочники --------------------

LICENSES = {
    "AUTO": {
        "title": "🚗 Вождение автомобиля",
        "fee": 3200,
        "questions": 15,
        "passing": 13,
        "bank": "road",
    },
    "TRUCK": {
        "title": "🚚 Вождение грузовика",
        "fee": 4200,
        "questions": 15,
        "passing": 13,
        "bank": "road",
    },
    "MOTO": {
        "title": "🏍 Вождение мотоцикла",
        "fee": 2800,
        "questions": 15,
        "passing": 13,
        "bank": "moto",
    },
    "WEAPON": {
        "title": "🔫 Оружие",
        "fee": 6500,
        "questions": 16,
        "passing": 14,
        "bank": "weapon",
    },
    "FISHING": {
        "title": "🎣 Рыбалка",
        "fee": 1200,
        "questions": 0,
        "passing": 0,
        "bank": None,
    },
    "HUNTING": {
        "title": "🦌 Охота",
        "fee": 2600,
        "questions": 0,
        "passing": 0,
        "bank": None,
        "requires": "WEAPON",
    },
}

QUESTION_BANKS = {
    "road": [
        ("Что означает красный сигнал светофора?", ["Движение запрещено", "Можно ехать быстрее", "Только поворот разрешён"], 0),
        ("Кто имеет преимущество на пешеходном переходе?", ["Пешеход", "Автомобиль", "Тот, кто громче сигналит"], 0),
        ("Можно ли садиться за руль в состоянии опьянения?", ["Нет", "Да, если ехать медленно", "Да, ночью"], 0),
        ("Что нужно сделать перед перестроением?", ["Включить поворотник и убедиться в безопасности", "Резко повернуть", "Посигналить"], 0),
        ("Что означает знак STOP?", ["Полная остановка", "Ускорение", "Парковка"], 0),
        ("Можно ли обгонять через сплошную линию?", ["Нет", "Да", "Только грузовику"], 0),
        ("Что делать при приближении спецмашины с маяками?", ["Уступить дорогу", "Гоняться за ней", "Остановиться посередине"], 0),
        ("Для чего нужен ремень безопасности?", ["Снизить риск травм", "Для красоты", "Чтобы не получить штраф только"], 0),
        ("Что делать при ДТП?", ["Остановиться и вызвать службы", "Уехать", "Скрыть машину"], 0),
        ("Допустимо ли превышать скорость ради опоздания?", ["Нет", "Да", "Только на 50 км/ч"], 0),
        ("Можно ли пользоваться телефоном за рулём без гарнитуры?", ["Нет", "Да всегда", "Только в городе"], 0),
        ("Что проверить перед поездкой?", ["Исправность транспорта", "Только цвет машины", "Ничего"], 0),
        ("Где запрещена парковка?", ["На пешеходном переходе", "На разрешённой стоянке", "Во дворе при разрешении"], 0),
        ("Что означает жёлтый сигнал светофора?", ["Предупреждает о смене сигнала", "Разрешает гонку", "Требует развернуться"], 0),
        ("Как вести себя в плохую погоду?", ["Снизить скорость и увеличить дистанцию", "Ускориться", "Выключить фары"], 0),
        ("Можно ли перевозить людей в закрытом грузовом кузове?", ["Нет", "Да без ограничений", "Только ночью"], 0),
        ("Кто отвечает за безопасность груза?", ["Водитель", "Случайный прохожий", "Никто"], 0),
        ("Что делать при отказе тормозов?", ["Снижать скорость безопасными способами и предупреждать других", "Прыгнуть из машины сразу", "Ускориться"], 0),
    ],
    "moto": [
        ("Обязателен ли шлем на мотоцикле?", ["Да", "Нет", "Только зимой"], 0),
        ("Можно ли ехать между машинами на высокой скорости?", ["Нет", "Да", "Только ночью"], 0),
        ("Что особенно важно на мотоцикле?", ["Защитная экипировка", "Громкая музыка", "Отсутствие зеркал"], 0),
        ("Нужно ли включать поворотник?", ["Да", "Нет", "Только за городом"], 0),
        ("Можно ли перевозить пассажира без места и подножек?", ["Нет", "Да", "Если пассажир держится"], 0),
        ("Как тормозить безопаснее?", ["Плавно использовать оба тормоза", "Только резко передним", "Ногами"], 0),
        ("Что делать на мокрой дороге?", ["Снизить скорость", "Ускориться", "Ехать без рук"], 0),
        ("Можно ли управлять мотоциклом в опьянении?", ["Нет", "Да", "Если недалеко"], 0),
        ("Для чего нужны зеркала?", ["Контролировать обстановку сзади", "Для украшения", "Чтобы закрыть номер"], 0),
        ("Что делать перед поворотом?", ["Снизить скорость заранее", "Тормозить резко в наклоне", "Закрыть глаза"], 0),
        ("Допустимы ли опасные трюки на дороге?", ["Нет", "Да", "Только перед полицией"], 0),
        ("Как держать дистанцию?", ["С запасом для торможения", "Вплотную", "Неважно"], 0),
        ("Что проверить перед поездкой?", ["Шины, тормоза, свет", "Только бензин", "Ничего"], 0),
        ("Можно ли ехать без света ночью?", ["Нет", "Да", "Если дорога пустая"], 0),
        ("Как вести себя рядом с грузовиком?", ["Не находиться долго в слепой зоне", "Ехать вплотную", "Обгонять по обочине"], 0),
        ("Кому уступать на переходе?", ["Пешеходу", "Никому", "Только велосипедисту"], 0),
        ("Что делать при аварии?", ["Остановиться и вызвать помощь", "Скрыться", "Удалить номер"], 0),
    ],
    "weapon": [
        ("Можно ли направлять оружие на человека без законной причины?", ["Нет", "Да", "Только ради шутки"], 0),
        ("Главное правило обращения с оружием?", ["Считать его заряженным", "Считать игрушкой", "Хранить без проверки"], 0),
        ("Куда направлять ствол при безопасном обращении?", ["В безопасную сторону", "На людей", "На себя"], 0),
        ("Когда палец кладут на спуск?", ["Только когда принято решение стрелять", "Всегда", "При переноске"], 0),
        ("Можно ли хранить оружие доступным детям?", ["Нет", "Да", "Если разряжено"], 0),
        ("Нужно ли проверять, что за целью?", ["Да", "Нет", "Только в тире"], 0),
        ("Допустима ли стрельба в воздух как предупреждение?", ["Нет", "Да всегда", "Только в городе"], 0),
        ("Можно ли носить оружие в состоянии опьянения?", ["Нет", "Да", "Если есть лицензия"], 0),
        ("Где хранить оружие?", ["В закрытом безопасном месте", "На столе", "В открытой машине"], 0),
        ("Можно ли передавать оружие человеку без допуска?", ["Нет", "Да", "Если знакомый"], 0),
        ("Что делать при осечке?", ["Сохранять направление и действовать безопасно", "Сразу смотреть в ствол", "Бросить оружие"], 0),
        ("Нужно ли знать правила конкретного тира?", ["Да", "Нет", "Только новичкам"], 0),
        ("Охотничье оружие можно использовать где угодно?", ["Нет", "Да", "Если лес рядом"], 0),
        ("Лицензия отменяет ответственность за применение?", ["Нет", "Да", "Иногда автоматически"], 0),
        ("Что делать при утрате оружия?", ["Немедленно сообщить компетентным органам", "Скрыть факт", "Купить новое"], 0),
        ("Можно ли изменять серийный номер?", ["Нет", "Да", "Если плохо читается"], 0),
        ("Нужно ли соблюдать условия транспортировки?", ["Да", "Нет", "Только самолётом"], 0),
        ("Кто отвечает за безопасное обращение?", ["Владелец/пользователь", "Магазин", "Никто"], 0),
    ],
}

GOS_HEADERS = [
    "Паспорт", "Код входа", "Telegram ID", "Username",
    "Фамилия", "Имя", "Отчество", "Возраст", "Дата рождения", "Пол",
    "Первое гражданство", "Второе гражданство", "Национальность",
    "Цвет кожи", "Цвет волос", "Цвет глаз", "Описание внешности",
    "Военный билет", "Фото file_id", "Статус", "Розыск", "Штрафы",
    "Лицензии", "Работа", "Примечания", "Дата регистрации",
]

REQUEST_HEADERS = [
    "ID", "Тип", "Telegram ID", "Username", "Паспорт", "ФИО",
    "Данные", "Статус", "Причина", "Создано", "Рассмотрено",
]

MED_HEADERS = [
    "Паспорт", "Telegram ID", "Рост", "Вес", "Группа крови",
    "Аллергии", "Хронические заболевания", "Примечания",
    "Статус", "Дата",
]

LICENSE_HEADERS = [
    "ID", "Паспорт", "Telegram ID", "Тип", "Название", "Баллы",
    "Максимум", "Пошлина", "Скрин file_id", "Статус",
    "Причина", "Дата",
]

LOG_HEADERS = ["Дата", "Администратор", "Действие", "Объект", "Подробности"]


# -------------------- SQLite --------------------

def init_db() -> None:
    with sqlite3.connect(DB_PATH) as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS test_sessions (
                user_id INTEGER PRIMARY KEY,
                license_code TEXT NOT NULL,
                questions TEXT NOT NULL,
                current_index INTEGER NOT NULL,
                score INTEGER NOT NULL,
                answers TEXT NOT NULL
            );
            """
        )
        conn.commit()


# -------------------- Google Sheets --------------------

def client():
    return gspread.service_account(filename=GOOGLE_CREDENTIALS_FILE)


def gos_book():
    return client().open_by_key(GOS_SPREADSHEET_ID)


def mvd_book():
    return client().open_by_key(MVD_SPREADSHEET_ID)


def get_or_create_ws(book, title: str, headers: list[str]):
    try:
        ws = book.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = book.add_worksheet(title=title, rows=1500, cols=max(len(headers), 20))
        ws.append_row(headers)
        return ws

    current = ws.row_values(1)
    if not current:
        ws.append_row(headers)
    elif current != headers:
        # Безопасно заполняем отсутствующие заголовки, не удаляя данные.
        for index, header in enumerate(headers, start=1):
            if index > len(current) or not current[index - 1]:
                ws.update_cell(1, index, header)
    return ws


def ensure_sheets():
    book = gos_book()
    get_or_create_ws(book, "Персонажи", GOS_HEADERS)
    get_or_create_ws(book, "Заявки", REQUEST_HEADERS)
    get_or_create_ws(book, "Медкарты", MED_HEADERS)
    get_or_create_ws(book, "Лицензии", LICENSE_HEADERS)
    get_or_create_ws(book, "Логи", LOG_HEADERS)


def ws_records(title: str, headers: list[str]) -> list[dict[str, Any]]:
    ws = get_or_create_ws(gos_book(), title, headers)
    values = ws.get_all_values()
    if len(values) < 2:
        return []
    header = values[0]
    out = []
    for row in values[1:]:
        padded = row + [""] * (len(header) - len(row))
        out.append(dict(zip(header, padded)))
    return out


def append_dict(ws, headers: list[str], data: dict[str, Any]) -> None:
    ws.append_row([data.get(h, "") for h in headers], value_input_option="USER_ENTERED")


def find_row(title: str, headers: list[str], key: str, value: Any):
    ws = get_or_create_ws(gos_book(), title, headers)
    values = ws.get_all_values()
    if not values:
        return ws, None, None
    header = values[0]
    if key not in header:
        return ws, None, None
    idx = header.index(key)
    for row_index, row in enumerate(values[1:], start=2):
        cell = row[idx] if idx < len(row) else ""
        if str(cell).strip() == str(value).strip():
            padded = row + [""] * (len(header) - len(row))
            return ws, row_index, dict(zip(header, padded))
    return ws, None, None


def update_field(title: str, headers: list[str], row_index: int, field: str, value: Any):
    ws = get_or_create_ws(gos_book(), title, headers)
    header = ws.row_values(1)
    if field not in header:
        ws.update_cell(1, len(header) + 1, field)
        header = ws.row_values(1)
    ws.update_cell(row_index, header.index(field) + 1, value)


def next_number(title: str, headers: list[str], field: str, default: int) -> int:
    rows = ws_records(title, headers)
    nums = []
    for row in rows:
        try:
            nums.append(int(str(row.get(field, "")).replace("№", "").strip()))
        except ValueError:
            pass
    return max(nums, default=default) + 1


def citizen_by_tg(user_id: int):
    for row in ws_records("Персонажи", GOS_HEADERS):
        if str(row.get("Telegram ID", "")).strip() == str(user_id):
            return row
    return None


def citizen_by_passport(passport: str):
    passport = str(passport).replace("№", "").strip()
    for row in ws_records("Персонажи", GOS_HEADERS):
        if str(row.get("Паспорт", "")).replace("№", "").strip() == passport:
            return row
    return None


def citizen_row_by_passport(passport: str):
    return find_row("Персонажи", GOS_HEADERS, "Паспорт", str(passport).replace("№", "").strip())


def has_license(citizen: dict[str, Any], code: str) -> bool:
    licenses = str(citizen.get("Лицензии", ""))
    return code in {x.strip() for x in licenses.split(",") if x.strip()}


def add_license_to_citizen(passport: str, code: str):
    ws, row_idx, citizen = citizen_row_by_passport(passport)
    if not citizen or not row_idx:
        return False
    current = [x.strip() for x in str(citizen.get("Лицензии", "")).split(",") if x.strip()]
    if code not in current:
        current.append(code)
    update_field("Персонажи", GOS_HEADERS, row_idx, "Лицензии", ", ".join(current) or "Нет")
    sync_mvd_field(passport, "Лицензии", ", ".join(current) or "Нет")
    return True


def sync_new_citizen_to_mvd(citizen: dict[str, Any]):
    book = mvd_book()
    ws = get_or_create_ws(
        book,
        "Граждане",
        ["Паспорт", "Фамилия", "Имя", "Отчество", "Возраст",
         "Дата рождения", "Пол", "Статус", "Лицензия", "Работа", "Примечания"],
    )
    headers = ws.row_values(1)
    mapping = {
        "Паспорт": citizen.get("Паспорт", ""),
        "Фамилия": citizen.get("Фамилия", ""),
        "Имя": citizen.get("Имя", ""),
        "Отчество": citizen.get("Отчество", ""),
        "Возраст": citizen.get("Возраст", ""),
        "Дата рождения": citizen.get("Дата рождения", ""),
        "Пол": "М" if citizen.get("Пол") == "Мужчина" else "Ж",
        "Статус": "Законопослушный",
        "Лицензия": citizen.get("Лицензии", "Нет"),
        "Работа": citizen.get("Работа", ""),
        "Примечания": citizen.get("Примечания", ""),
        "Username": citizen.get("Username", ""),
    }
    ws.append_row([mapping.get(h, "") for h in headers], value_input_option="USER_ENTERED")


def sync_mvd_field(passport: str, field: str, value: Any):
    try:
        ws = mvd_book().worksheet("Граждане")
    except gspread.WorksheetNotFound:
        return
    values = ws.get_all_values()
    if not values:
        return
    headers = values[0]
    passport_col = headers.index("Паспорт") if "Паспорт" in headers else 0
    field_alias = {"Лицензии": "Лицензия"}.get(field, field)
    if field_alias not in headers:
        return
    field_col = headers.index(field_alias)
    for idx, row in enumerate(values[1:], start=2):
        if passport_col < len(row) and str(row[passport_col]).strip() == str(passport).strip():
            ws.update_cell(idx, field_col + 1, value)
            return


def log_action(admin_id: int, action: str, obj: str, details: str = ""):
    ws = get_or_create_ws(gos_book(), "Логи", LOG_HEADERS)
    append_dict(ws, LOG_HEADERS, {
        "Дата": now(),
        "Администратор": admin_id,
        "Действие": action,
        "Объект": obj,
        "Подробности": details,
    })


# -------------------- Вспомогательные функции --------------------

def now() -> str:
    return datetime.now().strftime("%d.%m.%Y %H:%M:%S")


def split_fio(fio: str):
    parts = fio.strip().split()
    return (
        parts[0] if len(parts) > 0 else "",
        parts[1] if len(parts) > 1 else "",
        " ".join(parts[2:]) if len(parts) > 2 else "",
    )


def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS


def in_admin_chat(message_or_callback) -> bool:
    msg = message_or_callback.message if isinstance(message_or_callback, CallbackQuery) else message_or_callback
    return bool(msg.chat and msg.chat.id == ADMIN_CHAT_ID)


def request_buttons(req_id: int, req_type: str, user_id: int):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="✅ Одобрить",
                    callback_data=f"reqok:{req_type}:{req_id}:{user_id}",
                ),
                InlineKeyboardButton(
                    text="❌ Отклонить",
                    callback_data=f"reqno:{req_type}:{req_id}:{user_id}",
                ),
            ]
        ]
    )


def license_menu():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=LICENSES["AUTO"]["title"], callback_data="lic:AUTO")],
            [InlineKeyboardButton(text=LICENSES["TRUCK"]["title"], callback_data="lic:TRUCK")],
            [InlineKeyboardButton(text=LICENSES["MOTO"]["title"], callback_data="lic:MOTO")],
            [InlineKeyboardButton(text=LICENSES["WEAPON"]["title"], callback_data="lic:WEAPON")],
            [
                InlineKeyboardButton(text=LICENSES["FISHING"]["title"], callback_data="lic:FISHING"),
                InlineKeyboardButton(text=LICENSES["HUNTING"]["title"], callback_data="lic:HUNTING"),
            ],
        ]
    )


def admin_panel():
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="🔎 Найти персонажа", callback_data="adm:search"),
                InlineKeyboardButton(text="📋 Заявки", callback_data="adm:requests"),
            ],
            [
                InlineKeyboardButton(text="✏ Редактировать", callback_data="adm:edit"),
                InlineKeyboardButton(text="💸 Выдать штраф", callback_data="adm:fine"),
            ],
            [
                InlineKeyboardButton(text="🚨 Объявить в розыск", callback_data="adm:wanted"),
                InlineKeyboardButton(text="⚫ Жив/мёртв", callback_data="adm:status"),
            ],
        ]
    )


def character_admin_buttons(passport: str):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✏ Изменить поле", callback_data=f"char:edit:{passport}"),
                InlineKeyboardButton(text="⚫ Мёртв", callback_data=f"char:dead:{passport}"),
                InlineKeyboardButton(text="🟢 Жив", callback_data=f"char:alive:{passport}"),
            ],
            [
                InlineKeyboardButton(text="🚨 Розыск", callback_data=f"char:wanted:{passport}"),
                InlineKeyboardButton(text="✅ Снять розыск", callback_data=f"char:clearwanted:{passport}"),
            ],
        ]
    )


def format_citizen(c: dict[str, Any]) -> str:
    return (
        "━━━━━━━━━━━━━━━━━━━━\n"
        "<b>👤 КАРТОЧКА ПЕРСОНАЖА</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Паспорт:</b> №{escape(str(c.get('Паспорт', '—')))}\n"
        f"<b>ФИО:</b> {escape(c.get('Фамилия', ''))} {escape(c.get('Имя', ''))} {escape(c.get('Отчество', ''))}\n"
        f"<b>Возраст:</b> {escape(str(c.get('Возраст', '—')))}\n"
        f"<b>Дата рождения:</b> {escape(str(c.get('Дата рождения', '—')))}\n"
        f"<b>Статус:</b> {escape(str(c.get('Статус', 'Жив')))}\n"
        f"<b>Розыск:</b> {escape(str(c.get('Розыск', 'Нет')))}\n"
        f"<b>Штрафы:</b> {escape(str(c.get('Штрафы', 'Нет')))}\n"
        f"<b>Лицензии:</b> {escape(str(c.get('Лицензии', 'Нет')))}\n"
        f"<b>Работа:</b> {escape(str(c.get('Работа', '—')))}"
    )


async def send_admin_request(bot: Bot, req_id: int, req_type: str, message: Message, summary: str, photo: str | None = None):
    username = f"@{message.from_user.username}" if message.from_user.username else "не указан"
    caption = (
        "━━━━━━━━━━━━━━━━━━━━\n"
        f"<b>📨 ЗАЯВКА #{req_id}</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        f"<b>Тип:</b> {escape(req_type)}\n"
        f"<b>От:</b> {escape(message.from_user.full_name)}\n"
        f"<b>Username:</b> {escape(username)}\n"
        f"<b>Telegram ID:</b> <code>{message.from_user.id}</code>\n\n"
        f"{summary}"
    )
    if photo:
        await bot.send_photo(
            ADMIN_CHAT_ID,
            photo,
            caption=caption,
            reply_markup=request_buttons(req_id, req_type, message.from_user.id),
        )
    else:
        await bot.send_message(
            ADMIN_CHAT_ID,
            caption,
            reply_markup=request_buttons(req_id, req_type, message.from_user.id),
        )


# -------------------- Пользовательская часть --------------------

@router.message(CommandStart())
async def start(message: Message, state: FSMContext):
    await state.clear()
    c = await asyncio.to_thread(citizen_by_tg, message.from_user.id)
    if c:
        await message.answer(
            "<b>УслугиГосс | LimeWorld RP</b>\n\n"
            f"Вы вошли как <b>{escape(c.get('Фамилия', ''))} {escape(c.get('Имя', ''))}</b>.\n"
            f"Паспорт №{escape(str(c.get('Паспорт', '—')))}",
            reply_markup=MAIN_MENU,
        )
    else:
        await message.answer(
            "<b>УслугиГосс | LimeWorld RP</b>\n\n"
            "Персонаж на этом Telegram-аккаунте не найден.\n"
            "Создайте персонажа через регистрацию.",
            reply_markup=MAIN_MENU,
        )


@router.message(F.text == "❌ Отмена")
async def cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=MAIN_MENU)


@router.message(F.text == "🆕 Регистрация")
async def reg_start(message: Message, state: FSMContext):
    if await asyncio.to_thread(citizen_by_tg, message.from_user.id):
        await message.answer("На этом аккаунте уже зарегистрирован персонаж.")
        return
    await state.set_state(Registration.fio)
    await message.answer("Введите Фамилию Имя Отчество:", reply_markup=CANCEL_MENU)


@router.message(Registration.fio)
async def reg_fio(message: Message, state: FSMContext):
    if len((message.text or "").split()) < 2:
        await message.answer("Введите хотя бы фамилию и имя.")
        return
    await state.update_data(fio=message.text.strip())
    await state.set_state(Registration.age)
    await message.answer("Возраст персонажа от 14 до 200:")


@router.message(Registration.age)
async def reg_age(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.isdigit() or not 14 <= int(text) <= 200:
        await message.answer("Введите возраст от 14 до 200.")
        return
    await state.update_data(age=int(text))
    await state.set_state(Registration.birthdate)
    await message.answer("Дата рождения в формате ДД.ММ.ГГГГ:")


@router.message(Registration.birthdate)
async def reg_birth(message: Message, state: FSMContext):
    try:
        datetime.strptime((message.text or "").strip(), "%d.%m.%Y")
    except ValueError:
        await message.answer("Неверный формат. Пример: 27.06.2001")
        return
    await state.update_data(birthdate=message.text.strip())
    await state.set_state(Registration.sex)
    await message.answer("Выберите пол:", reply_markup=SEX_MENU)


@router.message(Registration.sex)
async def reg_sex(message: Message, state: FSMContext):
    if message.text not in {"Мужчина", "Женщина"}:
        await message.answer("Используйте кнопки.")
        return
    await state.update_data(sex=message.text)
    await state.set_state(Registration.citizenship_primary)
    await message.answer("Первое гражданство:", reply_markup=CANCEL_MENU)


@router.message(Registration.citizenship_primary)
async def reg_cp(message: Message, state: FSMContext):
    await state.update_data(citizenship_primary=(message.text or "").strip())
    await state.set_state(Registration.citizenship_secondary)
    await message.answer("Второе и последующие гражданства через запятую. Если нет, напишите «Нет»:")


@router.message(Registration.citizenship_secondary)
async def reg_cs(message: Message, state: FSMContext):
    await state.update_data(citizenship_secondary=(message.text or "").strip())
    await state.set_state(Registration.nationality)
    await message.answer("Национальность:")


@router.message(Registration.nationality)
async def reg_nat(message: Message, state: FSMContext):
    await state.update_data(nationality=(message.text or "").strip())
    await state.set_state(Registration.skin)
    await message.answer("Цвет кожи:")


@router.message(Registration.skin)
async def reg_skin(message: Message, state: FSMContext):
    await state.update_data(skin=(message.text or "").strip())
    await state.set_state(Registration.hair)
    await message.answer("Цвет волос:")


@router.message(Registration.hair)
async def reg_hair(message: Message, state: FSMContext):
    await state.update_data(hair=(message.text or "").strip())
    await state.set_state(Registration.eyes)
    await message.answer("Цвет глаз:")


@router.message(Registration.eyes)
async def reg_eyes(message: Message, state: FSMContext):
    await state.update_data(eyes=(message.text or "").strip())
    await state.set_state(Registration.appearance)
    await message.answer("Описание внешности:")


@router.message(Registration.appearance)
async def reg_appearance(message: Message, state: FSMContext):
    await state.update_data(appearance=(message.text or "").strip())
    data = await state.get_data()
    if int(data["age"]) < 18:
        await state.update_data(military="Нет по возрасту")
        await state.set_state(Registration.photo)
        await message.answer(
            "Отправьте фото персонажа для документов.\n"
            "Лицо прямо, без улыбки, маски и очков.",
            reply_markup=CANCEL_MENU,
        )
    else:
        await state.set_state(Registration.military)
        await message.answer("Есть военный билет?", reply_markup=YES_NO_MENU)


@router.message(Registration.military)
async def reg_military(message: Message, state: FSMContext):
    if message.text not in {"Да", "Нет"}:
        await message.answer("Используйте кнопки.")
        return
    await state.update_data(military=message.text)
    await state.set_state(Registration.photo)
    await message.answer(
        "Отправьте фото персонажа для документов.\n"
        "Лицо прямо, без улыбки, маски и очков.",
        reply_markup=CANCEL_MENU,
    )


@router.message(Registration.photo, F.photo)
async def reg_photo(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    req_id = await asyncio.to_thread(next_number, "Заявки", REQUEST_HEADERS, "ID", 0)
    fio = data["fio"]
    photo_id = message.photo[-1].file_id
    summary = (
        f"ФИО: {fio}\n"
        f"Возраст: {data['age']}\n"
        f"Дата рождения: {data['birthdate']}\n"
        f"Пол: {data['sex']}\n"
        f"Первое гражданство: {data['citizenship_primary']}\n"
        f"Второе гражданство: {data['citizenship_secondary']}\n"
        f"Национальность: {data['nationality']}\n"
        f"Цвет кожи: {data['skin']}\n"
        f"Цвет волос: {data['hair']}\n"
        f"Цвет глаз: {data['eyes']}\n"
        f"Описание внешности: {data['appearance']}\n"
        f"Военный билет: {data['military']}\n"
        f"Фото file_id: {photo_id}"
    )
    surname, name, patronymic = split_fio(fio)
    payload = {
        "surname": surname, "name": name, "patronymic": patronymic,
        **data, "photo": photo_id,
    }
    ws = get_or_create_ws(gos_book(), "Заявки", REQUEST_HEADERS)
    append_dict(ws, REQUEST_HEADERS, {
        "ID": req_id,
        "Тип": "Паспорт",
        "Telegram ID": message.from_user.id,
        "Username": message.from_user.username or "",
        "Паспорт": "",
        "ФИО": fio,
        "Данные": repr(payload),
        "Статус": "На рассмотрении",
        "Причина": "",
        "Создано": now(),
        "Рассмотрено": "",
    })
    await send_admin_request(bot, req_id, "PASSPORT", message, "<b>Заявка на паспорт</b>\n\n" + escape(summary), photo_id)
    await state.clear()
    await message.answer(f"✅ Заявка #{req_id} отправлена.", reply_markup=MAIN_MENU)


@router.message(Registration.photo)
async def reg_photo_wrong(message: Message):
    await message.answer("Нужно отправить именно фотографию.")


@router.message(F.text == "👤 Мой персонаж")
async def my_character(message: Message):
    c = await asyncio.to_thread(citizen_by_tg, message.from_user.id)
    if not c:
        await message.answer("Персонаж не найден.")
        return
    await message.answer(format_citizen(c))


@router.message(F.text == "📄 Документы")
async def documents(message: Message):
    c = await asyncio.to_thread(citizen_by_tg, message.from_user.id)
    if not c:
        await message.answer("Персонаж не найден.")
        return
    await message.answer(
        f"<b>Паспорт:</b> №{escape(str(c.get('Паспорт', '—')))}\n"
        f"<b>Военный билет:</b> {escape(str(c.get('Военный билет', 'Нет')))}\n"
        f"<b>Лицензии:</b> {escape(str(c.get('Лицензии', 'Нет')))}"
    )


@router.message(F.text == "🚨 Розыск")
async def wanted(message: Message):
    c = await asyncio.to_thread(citizen_by_tg, message.from_user.id)
    await message.answer(
        f"<b>Розыск:</b> {escape(str(c.get('Розыск', 'Нет')))}"
        if c else "Персонаж не найден."
    )


@router.message(F.text == "💸 Штрафы")
async def fines(message: Message):
    c = await asyncio.to_thread(citizen_by_tg, message.from_user.id)
    if not c:
        await message.answer("Персонаж не найден.")
        return
    await message.answer(
        f"<b>Штрафы:</b> {escape(str(c.get('Штрафы', 'Нет')))}\n\n"
        "Оплата через <code>/donate</code>.\n"
        "Поддельный скрин: штраф x2 и розыск."
    )


@router.message(F.text == "🩺 Медкарта")
async def med_start(message: Message, state: FSMContext):
    c = await asyncio.to_thread(citizen_by_tg, message.from_user.id)
    if not c:
        await message.answer("Сначала получите паспорт.")
        return
    await state.set_state(Medical.height)
    await message.answer("Рост в сантиметрах:", reply_markup=CANCEL_MENU)


@router.message(Medical.height)
async def med_height(message: Message, state: FSMContext):
    await state.update_data(height=(message.text or "").strip())
    await state.set_state(Medical.weight)
    await message.answer("Вес в килограммах:")


@router.message(Medical.weight)
async def med_weight(message: Message, state: FSMContext):
    await state.update_data(weight=(message.text or "").strip())
    await state.set_state(Medical.blood)
    await message.answer("Группа крови:")


@router.message(Medical.blood)
async def med_blood(message: Message, state: FSMContext):
    await state.update_data(blood=(message.text or "").strip())
    await state.set_state(Medical.allergies)
    await message.answer("Аллергии или «Нет»:")


@router.message(Medical.allergies)
async def med_allergies(message: Message, state: FSMContext):
    await state.update_data(allergies=(message.text or "").strip())
    await state.set_state(Medical.chronic)
    await message.answer("Хронические заболевания или «Нет»:")


@router.message(Medical.chronic)
async def med_chronic(message: Message, state: FSMContext):
    await state.update_data(chronic=(message.text or "").strip())
    await state.set_state(Medical.notes)
    await message.answer("Примечания или «Нет»:")


@router.message(Medical.notes)
async def med_finish(message: Message, state: FSMContext, bot: Bot):
    c = await asyncio.to_thread(citizen_by_tg, message.from_user.id)
    data = await state.get_data()
    req_id = await asyncio.to_thread(next_number, "Заявки", REQUEST_HEADERS, "ID", 0)
    payload = {**data, "notes": (message.text or "").strip(), "passport": c["Паспорт"]}
    summary = (
        f"<b>Паспорт:</b> №{escape(str(c['Паспорт']))}\n"
        f"<b>ФИО:</b> {escape(c['Фамилия'])} {escape(c['Имя'])} {escape(c['Отчество'])}\n"
        f"<b>Рост:</b> {escape(data['height'])}\n"
        f"<b>Вес:</b> {escape(data['weight'])}\n"
        f"<b>Группа крови:</b> {escape(data['blood'])}\n"
        f"<b>Аллергии:</b> {escape(data['allergies'])}\n"
        f"<b>Хронические:</b> {escape(data['chronic'])}\n"
        f"<b>Примечания:</b> {escape(payload['notes'])}"
    )
    ws = get_or_create_ws(gos_book(), "Заявки", REQUEST_HEADERS)
    append_dict(ws, REQUEST_HEADERS, {
        "ID": req_id, "Тип": "Медкарта", "Telegram ID": message.from_user.id,
        "Username": message.from_user.username or "", "Паспорт": c["Паспорт"],
        "ФИО": f"{c['Фамилия']} {c['Имя']} {c['Отчество']}",
        "Данные": repr(payload), "Статус": "На рассмотрении", "Причина": "",
        "Создано": now(), "Рассмотрено": "",
    })
    await send_admin_request(bot, req_id, "MEDICAL", message, summary)
    await state.clear()
    await message.answer(f"✅ Медкарта отправлена. Заявка #{req_id}.", reply_markup=MAIN_MENU)


# -------------------- Лицензии и тесты --------------------

@router.message(F.text == "🚗 Лицензии")
async def licenses(message: Message):
    c = await asyncio.to_thread(citizen_by_tg, message.from_user.id)
    if not c:
        await message.answer("Сначала получите паспорт.")
        return
    await message.answer(
        "<b>Получение лицензий</b>\n\n"
        "Авто, грузовик и мотоцикл: не менее 13/15.\n"
        "Оружие: не менее 14/16.\n"
        "Рыбалка: только госпошлина.\n"
        "Охота: сначала лицензия на оружие, затем госпошлина.",
        reply_markup=license_menu(),
    )


@router.callback_query(F.data.startswith("lic:"))
async def license_selected(callback: CallbackQuery, state: FSMContext):
    code = callback.data.split(":", 1)[1]
    cfg = LICENSES.get(code)
    if not cfg:
        await callback.answer("Неизвестная лицензия.", show_alert=True)
        return
    c = await asyncio.to_thread(citizen_by_tg, callback.from_user.id)
    if not c:
        await callback.answer("Сначала получите паспорт.", show_alert=True)
        return
    if has_license(c, code):
        await callback.answer("Эта лицензия уже есть.", show_alert=True)
        return
    required = cfg.get("requires")
    if required and not has_license(c, required):
        await callback.answer(
            "Для охоты сначала нужна лицензия на оружие.",
            show_alert=True,
        )
        return

    await state.update_data(license_code=code, passport=c["Паспорт"], score=0, qindex=0)

    if cfg["questions"] == 0:
        await state.set_state(LicenseFlow.payment)
        await callback.message.answer(
            f"<b>{cfg['title']}</b>\n\n"
            f"Госпошлина: <b>{cfg['fee']} ₽</b>\n"
            f"Оплатите через <code>/donate {cfg['fee']}</code> и отправьте скрин.",
            reply_markup=CANCEL_MENU,
        )
        await callback.answer()
        return

    bank = QUESTION_BANKS[cfg["bank"]]
    questions = random.sample(bank, cfg["questions"])
    await state.update_data(questions=questions)
    await state.set_state(LicenseFlow.test)
    await callback.message.answer(
        f"<b>{cfg['title']}</b>\n\n"
        f"Тест: {cfg['questions']} вопросов.\n"
        f"Проходной результат: {cfg['passing']}.\n\n"
        "Начинаем."
    )
    await send_test_question(callback.message, state)
    await callback.answer()


async def send_test_question(message: Message, state: FSMContext):
    data = await state.get_data()
    questions = data["questions"]
    idx = int(data.get("qindex", 0))
    if idx >= len(questions):
        await finish_test(message, state)
        return
    question, options, _ = questions[idx]
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=option, callback_data=f"ans:{idx}:{opt_idx}")]
            for opt_idx, option in enumerate(options)
        ]
    )
    await message.answer(
        f"<b>Вопрос {idx + 1}/{len(questions)}</b>\n\n{escape(question)}",
        reply_markup=keyboard,
    )


@router.callback_query(LicenseFlow.test, F.data.startswith("ans:"))
async def answer_test(callback: CallbackQuery, state: FSMContext):
    _, idx_raw, answer_raw = callback.data.split(":")
    data = await state.get_data()
    idx = int(idx_raw)
    if idx != int(data.get("qindex", 0)):
        await callback.answer("Этот вопрос уже отвечен.", show_alert=True)
        return
    questions = data["questions"]
    correct = int(questions[idx][2])
    score = int(data.get("score", 0))
    if int(answer_raw) == correct:
        score += 1
        await callback.answer("Верно")
    else:
        await callback.answer("Неверно")
    await callback.message.edit_reply_markup(reply_markup=None)
    await state.update_data(score=score, qindex=idx + 1)
    await send_test_question(callback.message, state)


async def finish_test(message: Message, state: FSMContext):
    data = await state.get_data()
    code = data["license_code"]
    cfg = LICENSES[code]
    score = int(data.get("score", 0))
    if score < cfg["passing"]:
        await state.clear()
        await message.answer(
            f"❌ Тест не сдан.\n"
            f"Результат: <b>{score}/{cfg['questions']}</b>\n"
            f"Нужно минимум: <b>{cfg['passing']}</b>.",
            reply_markup=MAIN_MENU,
        )
        return
    await state.update_data(test_score=score)
    await state.set_state(LicenseFlow.payment)
    await message.answer(
        f"✅ Тест сдан: <b>{score}/{cfg['questions']}</b>\n\n"
        f"Госпошлина: <b>{cfg['fee']} ₽</b>\n"
        f"Оплатите через <code>/donate {cfg['fee']}</code> и отправьте скрин.",
        reply_markup=CANCEL_MENU,
    )


@router.message(LicenseFlow.payment, F.photo)
async def license_payment(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    code = data["license_code"]
    cfg = LICENSES[code]
    c = await asyncio.to_thread(citizen_by_tg, message.from_user.id)
    req_id = await asyncio.to_thread(next_number, "Заявки", REQUEST_HEADERS, "ID", 0)
    lic_id = await asyncio.to_thread(next_number, "Лицензии", LICENSE_HEADERS, "ID", 0)
    score = data.get("test_score", "Без теста")
    photo_id = message.photo[-1].file_id
    payload = {
        "license_code": code,
        "score": score,
        "fee": cfg["fee"],
        "photo": photo_id,
        "passport": c["Паспорт"],
        "license_id": lic_id,
    }

    lic_ws = get_or_create_ws(gos_book(), "Лицензии", LICENSE_HEADERS)
    append_dict(lic_ws, LICENSE_HEADERS, {
        "ID": lic_id,
        "Паспорт": c["Паспорт"],
        "Telegram ID": message.from_user.id,
        "Тип": code,
        "Название": cfg["title"],
        "Баллы": score,
        "Максимум": cfg["questions"] or "—",
        "Пошлина": cfg["fee"],
        "Скрин file_id": photo_id,
        "Статус": "На рассмотрении",
        "Причина": "",
        "Дата": now(),
    })

    req_ws = get_or_create_ws(gos_book(), "Заявки", REQUEST_HEADERS)
    append_dict(req_ws, REQUEST_HEADERS, {
        "ID": req_id, "Тип": "Лицензия", "Telegram ID": message.from_user.id,
        "Username": message.from_user.username or "", "Паспорт": c["Паспорт"],
        "ФИО": f"{c['Фамилия']} {c['Имя']} {c['Отчество']}",
        "Данные": repr(payload), "Статус": "На рассмотрении", "Причина": "",
        "Создано": now(), "Рассмотрено": "",
    })
    summary = (
        f"<b>{escape(cfg['title'])}</b>\n"
        f"<b>Паспорт:</b> №{escape(str(c['Паспорт']))}\n"
        f"<b>ФИО:</b> {escape(c['Фамилия'])} {escape(c['Имя'])} {escape(c['Отчество'])}\n"
        f"<b>Тест:</b> {escape(str(score))}/{cfg['questions'] if cfg['questions'] else '—'}\n"
        f"<b>Пошлина:</b> {cfg['fee']} ₽"
    )
    await send_admin_request(bot, req_id, "LICENSE", message, summary, photo_id)
    await state.clear()
    await message.answer(
        f"✅ Заявка на лицензию отправлена. Номер #{req_id}.",
        reply_markup=MAIN_MENU,
    )


@router.message(LicenseFlow.payment)
async def license_payment_wrong(message: Message):
    await message.answer("Отправьте скрин оплаты фотографией.")


# -------------------- Административный чат --------------------

@router.message(Command("panel"))
async def panel(message: Message):
    if not is_admin(message.from_user.id) or message.chat.id != ADMIN_CHAT_ID:
        return
    await message.answer(
        "<b>Административная панель УслугиГосс</b>\n\n"
        "Работает только в этом staff-чате.",
        reply_markup=admin_panel(),
    )


@router.callback_query(F.data == "adm:search")
async def adm_search(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id) or not in_admin_chat(callback):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await state.set_state(AdminFlow.search_query)
    await callback.message.answer("Введите номер паспорта, Telegram ID, username или часть ФИО:")
    await callback.answer()


@router.message(AdminFlow.search_query)
async def adm_search_result(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id) or message.chat.id != ADMIN_CHAT_ID:
        await state.clear()
        return
    query = (message.text or "").strip().lstrip("@").casefold()
    found = []
    for c in await asyncio.to_thread(ws_records, "Персонажи", GOS_HEADERS):
        text = " ".join([
            str(c.get("Паспорт", "")), str(c.get("Telegram ID", "")),
            str(c.get("Username", "")), str(c.get("Фамилия", "")),
            str(c.get("Имя", "")), str(c.get("Отчество", "")),
        ]).casefold()
        if query in text:
            found.append(c)
    await state.clear()
    if not found:
        await message.answer("Ничего не найдено.")
        return
    for c in found[:10]:
        await message.answer(
            format_citizen(c),
            reply_markup=character_admin_buttons(str(c["Паспорт"])),
        )


@router.callback_query(F.data == "adm:requests")
async def adm_requests(callback: CallbackQuery):
    if not is_admin(callback.from_user.id) or not in_admin_chat(callback):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    rows = await asyncio.to_thread(ws_records, "Заявки", REQUEST_HEADERS)
    pending = [r for r in rows if r.get("Статус") == "На рассмотрении"]
    if not pending:
        await callback.message.answer("Заявок на рассмотрении нет.")
    else:
        text = ["<b>Заявки на рассмотрении</b>\n"]
        for r in pending[-20:]:
            text.append(
                f"#{escape(str(r.get('ID')))} | {escape(str(r.get('Тип')))} | "
                f"паспорт {escape(str(r.get('Паспорт') or 'ещё нет'))} | "
                f"{escape(str(r.get('ФИО')))}"
            )
        await callback.message.answer("\n".join(text))
    await callback.answer()


@router.callback_query(F.data == "adm:edit")
async def adm_edit(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id) or not in_admin_chat(callback):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await state.set_state(AdminFlow.edit_passport)
    await callback.message.answer("Введите номер паспорта персонажа:")
    await callback.answer()


@router.message(AdminFlow.edit_passport)
async def adm_edit_passport(message: Message, state: FSMContext):
    if not is_admin(message.from_user.id) or message.chat.id != ADMIN_CHAT_ID:
        await state.clear()
        return
    passport = (message.text or "").replace("№", "").strip()
    c = await asyncio.to_thread(citizen_by_passport, passport)
    if not c:
        await message.answer("Паспорт не найден.")
        return
    await state.update_data(edit_passport=passport)
    await state.set_state(AdminFlow.edit_field)
    await message.answer(
        "Введите точное название поля, которое хотите изменить.\n\n"
        "Например: Статус, Розыск, Штрафы, Лицензии, Работа, Примечания, Фамилия."
    )


@router.message(AdminFlow.edit_field)
async def adm_edit_field(message: Message, state: FSMContext):
    field = (message.text or "").strip()
    if field not in GOS_HEADERS:
        await message.answer("Такого поля нет. Введите название точно как в таблице.")
        return
    await state.update_data(edit_field=field)
    await state.set_state(AdminFlow.edit_value)
    await message.answer("Введите новое значение:")


@router.message(AdminFlow.edit_value)
async def adm_edit_value(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    ws, row_idx, c = await asyncio.to_thread(citizen_row_by_passport, data["edit_passport"])
    if not c or not row_idx:
        await state.clear()
        await message.answer("Персонаж не найден.")
        return
    value = (message.text or "").strip()
    await asyncio.to_thread(update_field, "Персонажи", GOS_HEADERS, row_idx, data["edit_field"], value)
    if data["edit_field"] in {"Статус", "Розыск", "Штрафы", "Лицензии", "Работа", "Примечания"}:
        await asyncio.to_thread(sync_mvd_field, data["edit_passport"], data["edit_field"], value)
    await asyncio.to_thread(log_action, message.from_user.id, "Редактирование", f"Паспорт {data['edit_passport']}", f"{data['edit_field']} = {value}")
    try:
        await bot.send_message(
            int(c["Telegram ID"]),
            f"ℹ️ Данные персонажа изменены.\n"
            f"<b>{escape(data['edit_field'])}:</b> {escape(value)}"
        )
    except Exception:
        pass
    await state.clear()
    await message.answer("✅ Поле изменено.", reply_markup=admin_panel())


@router.callback_query(F.data == "adm:fine")
async def adm_fine(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id) or not in_admin_chat(callback):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await state.set_state(AdminFlow.fine_passport)
    await callback.message.answer("Введите паспорт для выдачи штрафа:")
    await callback.answer()


@router.message(AdminFlow.fine_passport)
async def adm_fine_passport(message: Message, state: FSMContext):
    passport = (message.text or "").replace("№", "").strip()
    if not await asyncio.to_thread(citizen_by_passport, passport):
        await message.answer("Паспорт не найден.")
        return
    await state.update_data(fine_passport=passport)
    await state.set_state(AdminFlow.fine_amount)
    await message.answer("Введите сумму штрафа:")


@router.message(AdminFlow.fine_amount)
async def adm_fine_amount(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not text.isdigit() or int(text) <= 0:
        await message.answer("Введите положительную сумму числом.")
        return
    await state.update_data(fine_amount=int(text))
    await state.set_state(AdminFlow.fine_reason)
    await message.answer("Введите причину штрафа:")


@router.message(AdminFlow.fine_reason)
async def adm_fine_reason(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    ws, row_idx, c = await asyncio.to_thread(citizen_row_by_passport, data["fine_passport"])
    old = str(c.get("Штрафы", "")).strip()
    entry = f"{data['fine_amount']} ₽: {(message.text or '').strip()}"
    new = entry if not old or old == "Нет" else f"{old}; {entry}"
    await asyncio.to_thread(update_field, "Персонажи", GOS_HEADERS, row_idx, "Штрафы", new)
    await asyncio.to_thread(sync_mvd_field, data["fine_passport"], "Штрафы", new)
    await asyncio.to_thread(log_action, message.from_user.id, "Штраф", f"Паспорт {data['fine_passport']}", entry)
    await bot.send_message(
        int(c["Telegram ID"]),
        f"💸 <b>Вам выписан штраф</b>\n\n"
        f"<b>Сумма:</b> {data['fine_amount']} ₽\n"
        f"<b>Причина:</b> {escape((message.text or '').strip())}\n\n"
        f"Оплата: <code>/donate {data['fine_amount']}</code>\n"
        "Поддельный скрин: штраф x2 и розыск."
    )
    await state.clear()
    await message.answer("✅ Штраф выдан.", reply_markup=admin_panel())


@router.callback_query(F.data == "adm:wanted")
async def adm_wanted(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id) or not in_admin_chat(callback):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await state.set_state(AdminFlow.wanted_passport)
    await callback.message.answer("Введите паспорт:")
    await callback.answer()


@router.message(AdminFlow.wanted_passport)
async def adm_wanted_passport(message: Message, state: FSMContext):
    passport = (message.text or "").replace("№", "").strip()
    if not await asyncio.to_thread(citizen_by_passport, passport):
        await message.answer("Паспорт не найден.")
        return
    await state.update_data(wanted_passport=passport)
    await state.set_state(AdminFlow.wanted_reason)
    await message.answer("Введите причину розыска:")


@router.message(AdminFlow.wanted_reason)
async def adm_wanted_reason(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    ws, row_idx, c = await asyncio.to_thread(citizen_row_by_passport, data["wanted_passport"])
    reason = (message.text or "").strip()
    await asyncio.to_thread(update_field, "Персонажи", GOS_HEADERS, row_idx, "Розыск", reason)
    await asyncio.to_thread(sync_mvd_field, data["wanted_passport"], "Розыск", reason)
    await asyncio.to_thread(log_action, message.from_user.id, "Розыск", f"Паспорт {data['wanted_passport']}", reason)
    await bot.send_message(int(c["Telegram ID"]), f"🚨 Ваш персонаж объявлен в розыск.\n<b>Причина:</b> {escape(reason)}")
    await state.clear()
    await message.answer("✅ Розыск установлен.", reply_markup=admin_panel())


@router.callback_query(F.data == "adm:status")
async def adm_status(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id) or not in_admin_chat(callback):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await state.set_state(AdminFlow.status_passport)
    await callback.message.answer("Введите паспорт. После поиска используйте кнопки «Жив» или «Мёртв».")
    await callback.answer()


@router.message(AdminFlow.status_passport)
async def adm_status_passport(message: Message, state: FSMContext):
    passport = (message.text or "").replace("№", "").strip()
    c = await asyncio.to_thread(citizen_by_passport, passport)
    await state.clear()
    if not c:
        await message.answer("Паспорт не найден.")
        return
    await message.answer(format_citizen(c), reply_markup=character_admin_buttons(passport))


@router.callback_query(F.data.startswith("char:"))
async def character_action(callback: CallbackQuery, state: FSMContext, bot: Bot):
    if not is_admin(callback.from_user.id) or not in_admin_chat(callback):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    _, action, passport = callback.data.split(":", 2)
    ws, row_idx, c = await asyncio.to_thread(citizen_row_by_passport, passport)
    if not c or not row_idx:
        await callback.answer("Персонаж не найден.", show_alert=True)
        return

    if action == "edit":
        await state.update_data(edit_passport=passport)
        await state.set_state(AdminFlow.edit_field)
        await callback.message.answer("Введите название поля:")
    elif action == "dead":
        await asyncio.to_thread(update_field, "Персонажи", GOS_HEADERS, row_idx, "Статус", "Мёртв")
        await asyncio.to_thread(sync_mvd_field, passport, "Статус", "Мёртв")
        await bot.send_message(int(c["Telegram ID"]), "⚫ Ваш персонаж отмечен как мёртвый.")
        await callback.message.answer("⚫ Статус изменён на «Мёртв».")
    elif action == "alive":
        await asyncio.to_thread(update_field, "Персонажи", GOS_HEADERS, row_idx, "Статус", "Жив")
        await asyncio.to_thread(sync_mvd_field, passport, "Статус", "Жив")
        await bot.send_message(int(c["Telegram ID"]), "🟢 Ваш персонаж отмечен как живой.")
        await callback.message.answer("🟢 Статус изменён на «Жив».")
    elif action == "wanted":
        await state.update_data(wanted_passport=passport)
        await state.set_state(AdminFlow.wanted_reason)
        await callback.message.answer("Введите причину розыска:")
    elif action == "clearwanted":
        await asyncio.to_thread(update_field, "Персонажи", GOS_HEADERS, row_idx, "Розыск", "Нет")
        await asyncio.to_thread(sync_mvd_field, passport, "Розыск", "Нет")
        await bot.send_message(int(c["Telegram ID"]), "✅ Розыск с персонажа снят.")
        await callback.message.answer("✅ Розыск снят.")
    await callback.answer()


# -------------------- Одобрение заявок --------------------

def parse_payload(value: str) -> dict[str, Any]:
    # Данные создаются самим ботом. eval ограничен пустым builtins.
    try:
        result = eval(value, {"__builtins__": {}}, {})
        return result if isinstance(result, dict) else {}
    except Exception:
        return {}


@router.callback_query(F.data.startswith("reqok:"))
async def request_approve(callback: CallbackQuery, bot: Bot):
    if not is_admin(callback.from_user.id) or not in_admin_chat(callback):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    _, req_type, req_id_raw, user_id_raw = callback.data.split(":")
    req_id = int(req_id_raw)
    user_id = int(user_id_raw)
    ws, row_idx, req = await asyncio.to_thread(find_row, "Заявки", REQUEST_HEADERS, "ID", str(req_id))
    if not req or not row_idx:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return
    if req.get("Статус") != "На рассмотрении":
        await callback.answer("Заявка уже рассмотрена.", show_alert=True)
        return
    payload = parse_payload(req.get("Данные", ""))

    if req_type == "PASSPORT":
        passport = await asyncio.to_thread(next_number, "Персонажи", GOS_HEADERS, "Паспорт", 613)
        code = f"UG-{passport}-{secrets.token_hex(2).upper()}"
        citizen = {
            "Паспорт": passport,
            "Код входа": code,
            "Telegram ID": user_id,
            "Username": req.get("Username", ""),
            "Фамилия": payload.get("surname", ""),
            "Имя": payload.get("name", ""),
            "Отчество": payload.get("patronymic", ""),
            "Возраст": payload.get("age", ""),
            "Дата рождения": payload.get("birthdate", ""),
            "Пол": payload.get("sex", ""),
            "Первое гражданство": payload.get("citizenship_primary", ""),
            "Второе гражданство": payload.get("citizenship_secondary", ""),
            "Национальность": payload.get("nationality", ""),
            "Цвет кожи": payload.get("skin", ""),
            "Цвет волос": payload.get("hair", ""),
            "Цвет глаз": payload.get("eyes", ""),
            "Описание внешности": payload.get("appearance", ""),
            "Военный билет": payload.get("military", ""),
            "Фото file_id": payload.get("photo", ""),
            "Статус": "Жив",
            "Розыск": "Нет",
            "Штрафы": "Нет",
            "Лицензии": "Нет",
            "Работа": "",
            "Примечания": "",
            "Дата регистрации": now(),
        }
        char_ws = get_or_create_ws(gos_book(), "Персонажи", GOS_HEADERS)
        await asyncio.to_thread(append_dict, char_ws, GOS_HEADERS, citizen)
        await asyncio.to_thread(sync_new_citizen_to_mvd, citizen)
        await bot.send_message(
            user_id,
            "✅ <b>Паспорт одобрен</b>\n\n"
            f"<b>Номер:</b> №{passport}\n"
            f"<b>Код входа:</b> <code>{code}</code>\n\n"
            "Сохраните код."
        )

    elif req_type == "MEDICAL":
        med_ws = get_or_create_ws(gos_book(), "Медкарты", MED_HEADERS)
        await asyncio.to_thread(append_dict, med_ws, MED_HEADERS, {
            "Паспорт": payload.get("passport", ""),
            "Telegram ID": user_id,
            "Рост": payload.get("height", ""),
            "Вес": payload.get("weight", ""),
            "Группа крови": payload.get("blood", ""),
            "Аллергии": payload.get("allergies", ""),
            "Хронические заболевания": payload.get("chronic", ""),
            "Примечания": payload.get("notes", ""),
            "Статус": "Одобрено",
            "Дата": now(),
        })
        await bot.send_message(user_id, "✅ Медкарта одобрена.")

    elif req_type == "LICENSE":
        code = payload.get("license_code", "")
        passport = str(payload.get("passport", ""))
        await asyncio.to_thread(add_license_to_citizen, passport, code)
        lic_ws, lic_row, _ = await asyncio.to_thread(find_row, "Лицензии", LICENSE_HEADERS, "ID", str(payload.get("license_id")))
        if lic_row:
            await asyncio.to_thread(update_field, "Лицензии", LICENSE_HEADERS, lic_row, "Статус", "Одобрено")
        await bot.send_message(
            user_id,
            f"✅ Лицензия одобрена: <b>{escape(LICENSES.get(code, {}).get('title', code))}</b>"
        )

    await asyncio.to_thread(update_field, "Заявки", REQUEST_HEADERS, row_idx, "Статус", "Одобрено")
    await asyncio.to_thread(update_field, "Заявки", REQUEST_HEADERS, row_idx, "Рассмотрено", now())
    await asyncio.to_thread(log_action, callback.from_user.id, "Одобрение", f"Заявка #{req_id}", req_type)

    if callback.message.photo:
        await callback.message.edit_caption(
            caption=(callback.message.caption or "") + "\n\n✅ <b>ОДОБРЕНО</b>",
            reply_markup=None,
        )
    else:
        await callback.message.edit_reply_markup(reply_markup=None)
        await callback.message.reply("✅ Заявка одобрена.")
    await callback.answer("Одобрено")


@router.callback_query(F.data.startswith("reqno:"))
async def request_reject(callback: CallbackQuery, state: FSMContext):
    if not is_admin(callback.from_user.id) or not in_admin_chat(callback):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    _, req_type, req_id_raw, user_id_raw = callback.data.split(":")
    await state.update_data(reject_req_id=int(req_id_raw), reject_user_id=int(user_id_raw), reject_type=req_type)
    await state.set_state(AdminFlow.reject_reason)
    await callback.message.reply(f"Введите причину отказа по заявке #{req_id_raw}:")
    await callback.answer()


@router.message(AdminFlow.reject_reason)
async def request_reject_reason(message: Message, state: FSMContext, bot: Bot):
    if not is_admin(message.from_user.id) or message.chat.id != ADMIN_CHAT_ID:
        await state.clear()
        return
    data = await state.get_data()
    reason = (message.text or "").strip()
    ws, row_idx, req = await asyncio.to_thread(find_row, "Заявки", REQUEST_HEADERS, "ID", str(data["reject_req_id"]))
    if not req or not row_idx:
        await state.clear()
        await message.answer("Заявка не найдена.")
        return
    await asyncio.to_thread(update_field, "Заявки", REQUEST_HEADERS, row_idx, "Статус", "Отклонено")
    await asyncio.to_thread(update_field, "Заявки", REQUEST_HEADERS, row_idx, "Причина", reason)
    await asyncio.to_thread(update_field, "Заявки", REQUEST_HEADERS, row_idx, "Рассмотрено", now())
    await asyncio.to_thread(log_action, message.from_user.id, "Отклонение", f"Заявка #{data['reject_req_id']}", reason)
    await bot.send_message(
        data["reject_user_id"],
        f"❌ Заявка #{data['reject_req_id']} отклонена.\n\n"
        f"<b>Причина:</b> {escape(reason)}"
    )
    await state.clear()
    await message.answer("✅ Отказ отправлен пользователю.", reply_markup=admin_panel())


# -------------------- Запуск --------------------

async def main():
    init_db()
    await asyncio.to_thread(ensure_sheets)

    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)

    await bot.delete_webhook(drop_pending_updates=True)

    try:
        await bot.send_message(
            ADMIN_CHAT_ID,
            "🟢 <b>УслугиГосс v2 запущен</b>\n"
            f"<b>Время:</b> {now()}\n\n"
            "Административная панель: /panel"
        )
    except Exception:
        logging.exception("Не удалось отправить сообщение о запуске")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
