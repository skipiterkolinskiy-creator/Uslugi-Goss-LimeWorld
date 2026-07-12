from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup


def licenses_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [("Автомобиль", "AUTO"), ("Грузовик", "TRUCK")],
        [("Мотоцикл", "MOTO"), ("Оружие", "WEAPON")],
        [("Рыбалка", "FISHING"), ("Охота", "HUNTING")],
    ]
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=text, callback_data=f"license:start:{code}") for text, code in row]
            for row in rows
        ]
    )


def answers_keyboard(question_id: str, answers: list[str]) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text=answer, callback_data=f"license:answer:{question_id}:{index}")]
            for index, answer in enumerate(answers)
        ]
    )
