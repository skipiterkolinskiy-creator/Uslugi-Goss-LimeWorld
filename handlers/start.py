from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message

from keyboards.user import main_menu, start_menu
from services.citizens import citizens_service

router = Router(name="start")


@router.message(CommandStart())
async def start(message: Message) -> None:
    citizen = await citizens_service.find_by_telegram(message.from_user.id)
    if citizen:
        await message.answer(
            "УслугиГосс | LimeWorld RP\n\n"
            f"Вы вошли как {citizen.fio}.\n"
            f"Паспорт №{citizen.passport}",
            reply_markup=main_menu,
        )
        return
    await message.answer(
        "УслугиГосс | LimeWorld RP\n\n"
        "На этом Telegram-аккаунте персонаж не найден.",
        reply_markup=start_menu,
    )
