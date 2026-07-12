from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from handlers.admin_panel import admin_allowed
from keyboards.admin import character_actions_keyboard
from services.citizens import citizens_service
from states.admin import AdminSearchStates

router = Router(name="admin_search")


@router.callback_query(F.data == "admin:search")
async def begin_search(callback: CallbackQuery, state: FSMContext) -> None:
    if not admin_allowed(callback.from_user.id, callback.message.chat.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await state.clear()
    await state.set_state(AdminSearchStates.waiting_query)
    await callback.message.answer("Введите номер паспорта, Telegram ID, username или часть ФИО:")
    await callback.answer()


@router.message(AdminSearchStates.waiting_query)
async def process_search(message: Message, state: FSMContext) -> None:
    if not admin_allowed(message.from_user.id, message.chat.id):
        await state.clear()
        return
    query = (message.text or "").strip()
    if not query:
        await message.answer("Введите непустой поисковый запрос.")
        return
    try:
        citizens = await citizens_service.search(query)
    except Exception:
        await state.clear()
        await message.answer("Не удалось выполнить поиск. Ошибка записана в логи.")
        raise
    await state.clear()
    if not citizens:
        await message.answer("Персонажи не найдены.")
        return
    for citizen in citizens[:10]:
        await message.answer(citizens_service.format_card(citizen), reply_markup=character_actions_keyboard(citizen.passport))
