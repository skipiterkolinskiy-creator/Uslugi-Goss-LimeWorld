from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from config import settings
from keyboards.admin import admin_panel_keyboard
from states.admin import AdminFineStates, AdminWantedStates

router = Router(name="admin_panel")


def admin_allowed(user_id: int, chat_id: int) -> bool:
    return user_id in settings.admin_ids and chat_id == settings.admin_chat_id


@router.message(Command("panel"))
async def panel(message: Message) -> None:
    if not admin_allowed(message.from_user.id, message.chat.id):
        await message.answer("Панель доступна только в административном чате.")
        return
    await message.answer("Административная панель", reply_markup=admin_panel_keyboard())


@router.callback_query(F.data == "admin:fine:start")
async def fine_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not admin_allowed(callback.from_user.id, callback.message.chat.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await state.clear()
    await state.set_state(AdminFineStates.waiting_passport)
    await callback.message.answer("Введите паспорт персонажа для штрафа:")
    await callback.answer()


@router.callback_query(F.data == "admin:wanted:start")
async def wanted_start(callback: CallbackQuery, state: FSMContext) -> None:
    if not admin_allowed(callback.from_user.id, callback.message.chat.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await state.clear()
    await state.set_state(AdminWantedStates.waiting_passport)
    await callback.message.answer("Введите паспорт персонажа для объявления в розыск:")
    await callback.answer()


@router.callback_query(F.data.in_({"admin:requests", "admin:licenses", "admin:medcards", "admin:logs", "admin:status:start", "admin:edit:start", "admin:unwanted:start"}))
async def admin_hint(callback: CallbackQuery) -> None:
    if not admin_allowed(callback.from_user.id, callback.message.chat.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    await callback.message.answer("Используйте поиск персонажа или карточку персонажа для этого действия.")
    await callback.answer()
