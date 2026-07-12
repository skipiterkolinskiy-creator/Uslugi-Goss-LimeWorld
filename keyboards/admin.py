from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def admin_panel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Найти персонажа", callback_data="admin:search")],
            [InlineKeyboardButton(text="Заявки", callback_data="admin:requests")],
            [InlineKeyboardButton(text="Редактировать", callback_data="admin:edit:start")],
            [InlineKeyboardButton(text="Выдать штраф", callback_data="admin:fine:start")],
            [InlineKeyboardButton(text="Объявить в розыск", callback_data="admin:wanted:start")],
            [InlineKeyboardButton(text="Снять с розыска", callback_data="admin:unwanted:start")],
            [InlineKeyboardButton(text="Жив/мёртв", callback_data="admin:status:start")],
            [InlineKeyboardButton(text="Лицензии", callback_data="admin:licenses")],
            [InlineKeyboardButton(text="Медкарты", callback_data="admin:medcards")],
            [InlineKeyboardButton(text="Логи", callback_data="admin:logs")],
        ]
    )


def character_actions_keyboard(passport: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Редактировать", callback_data=f"admin:edit:{passport}")],
            [InlineKeyboardButton(text="Выдать штраф", callback_data=f"admin:fine:{passport}")],
            [InlineKeyboardButton(text="Объявить в розыск", callback_data=f"admin:wanted:{passport}")],
            [InlineKeyboardButton(text="Снять с розыска", callback_data=f"admin:unwanted:{passport}")],
            [
                InlineKeyboardButton(text="Сделать мёртвым", callback_data=f"admin:status:{passport}:Мёртв"),
                InlineKeyboardButton(text="Сделать живым", callback_data=f"admin:status:{passport}:Жив"),
            ],
            [
                InlineKeyboardButton(text="Выдать лицензию", callback_data=f"admin:license:add:{passport}"),
                InlineKeyboardButton(text="Изъять лицензию", callback_data=f"admin:license:remove:{passport}"),
            ],
        ]
    )


def edit_fields_keyboard(passport: int) -> InlineKeyboardMarkup:
    fields = [
        ("ФИО", "fio"),
        ("Возраст", "age"),
        ("Дата рождения", "birthdate"),
        ("Гражданство", "citizenship"),
        ("Национальность", "nationality"),
        ("Внешность", "appearance"),
        ("Военный билет", "military"),
        ("Статус", "status"),
        ("Розыск", "wanted"),
        ("Штрафы", "fines"),
        ("Лицензии", "licenses"),
        ("Работа", "job"),
        ("Примечания", "notes"),
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=title, callback_data=f"admin:editfield:{passport}:{code}")]
            for title, code in fields
        ]
    )


def request_decision_keyboard(kind: str, request_id: int) -> InlineKeyboardMarkup:
    rows = [
        [
            InlineKeyboardButton(text="Одобрить", callback_data=f"mod:approve:{kind}:{request_id}"),
            InlineKeyboardButton(text="Отклонить", callback_data=f"mod:reject:{kind}:{request_id}"),
        ]
    ]
    if kind == "license":
        rows.append([InlineKeyboardButton(text="Поддельный скрин", callback_data=f"mod:fake:{kind}:{request_id}")])
    return InlineKeyboardMarkup(inline_keyboard=rows)
