from aiogram import F, Router
from aiogram.types import Message

from services.citizens import citizens_service

router = Router(name="profile")


async def current(message: Message):
    citizen = await citizens_service.find_by_telegram(message.from_user.id)
    if citizen is None:
        await message.answer("Персонаж не найден. Используйте /start.")
    return citizen


@router.message(F.text == "Мой персонаж")
async def profile(message: Message) -> None:
    citizen = await current(message)
    if citizen:
        await message.answer(citizens_service.format_card(citizen))


@router.message(F.text == "Документы")
async def documents(message: Message) -> None:
    citizen = await current(message)
    if citizen:
        await message.answer(
            f"<b>Документы</b>\n"
            f"Паспорт: №{citizen.passport}\n"
            f"Военный билет: {citizen.raw.get('Военный билет', 'Нет')}\n"
            f"Лицензии: {citizen.licenses or 'Нет'}\n"
            f"Медкарта: смотрите раздел «Медкарта»"
        )


@router.message(F.text == "Штрафы")
async def fines(message: Message) -> None:
    citizen = await current(message)
    if citizen:
        await message.answer(f"Текущая неоплаченная сумма штрафов: {citizen.fines or '0'} рублей.")


@router.message(F.text == "Розыск")
async def wanted(message: Message) -> None:
    citizen = await current(message)
    if citizen:
        await message.answer(f"Статус розыска: {citizen.wanted or 'Нет'}.")


@router.message(F.text == "История заявлений")
async def history(message: Message) -> None:
    await message.answer("История заявлений хранится в таблице УслугиГосс и доступна администрации.")
