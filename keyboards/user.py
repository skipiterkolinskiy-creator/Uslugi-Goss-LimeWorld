from aiogram.types import KeyboardButton, ReplyKeyboardMarkup


main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Мой персонаж"), KeyboardButton(text="Медкарта")],
        [KeyboardButton(text="Документы"), KeyboardButton(text="🚗 Лицензии")],
        [KeyboardButton(text="Штрафы"), KeyboardButton(text="Розыск")],
        [KeyboardButton(text="История заявлений")],
    ],
    resize_keyboard=True,
)

start_menu = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Регистрация"), KeyboardButton(text="Войти по коду")]],
    resize_keyboard=True,
)

cancel_menu = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Отмена")]],
    resize_keyboard=True,
)

gender_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Мужчина"), KeyboardButton(text="Женщина")],
        [KeyboardButton(text="Отмена")],
    ],
    resize_keyboard=True,
)

yes_no_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Да"), KeyboardButton(text="Нет")],
        [KeyboardButton(text="Отмена")],
    ],
    resize_keyboard=True,
)
