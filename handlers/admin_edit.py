from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from handlers.admin_panel import admin_allowed
from keyboards.admin import edit_fields_keyboard
from services.audit import log_action
from services.citizens import citizens_service
from services.mvd_sync import mvd_sync_service
from services.records import append_fine, append_wanted
from states.admin import AdminEditStates, AdminFineStates, AdminWantedStates

router = Router(name="admin_edit")

FIELD_MAP = {
    "age": "Возраст",
    "birthdate": "Дата рождения",
    "citizenship": "Первое гражданство",
    "nationality": "Национальность",
    "appearance": "Описание внешности",
    "military": "Военный билет",
    "status": "Статус",
    "wanted": "Розыск",
    "fines": "Штрафы",
    "licenses": "Лицензии",
    "job": "Работа",
    "notes": "Примечания",
}


@router.callback_query(F.data.startswith("admin:edit:"))
async def choose_edit_field(callback: CallbackQuery) -> None:
    if not admin_allowed(callback.from_user.id, callback.message.chat.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    passport = int(callback.data.split(":")[-1])
    await callback.message.answer("Выберите поле:", reply_markup=edit_fields_keyboard(passport))
    await callback.answer()


@router.callback_query(F.data.startswith("admin:editfield:"))
async def ask_edit_value(callback: CallbackQuery, state: FSMContext) -> None:
    if not admin_allowed(callback.from_user.id, callback.message.chat.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    _, _, passport, field = callback.data.split(":")
    await state.clear()
    await state.update_data(passport=int(passport), field=field)
    await state.set_state(AdminEditStates.waiting_value)
    await callback.message.answer("Введите новое значение:")
    await callback.answer()


@router.message(AdminEditStates.waiting_value)
async def save_edit_value(message: Message, state: FSMContext) -> None:
    if not admin_allowed(message.from_user.id, message.chat.id):
        await state.clear()
        return
    data = await state.get_data()
    passport = int(data["passport"])
    field = data["field"]
    value = (message.text or "").strip()
    if not value:
        await message.answer("Введите непустое значение.")
        return
    if field == "fio":
        parts = value.split()
        if len(parts) < 2:
            await message.answer("Введите минимум фамилию и имя.")
            return
        await citizens_service.update_field(passport, "Фамилия", parts[0])
        await citizens_service.update_field(passport, "Имя", parts[1])
        await citizens_service.update_field(passport, "Отчество", " ".join(parts[2:]))
        await mvd_sync_service.update_by_header(passport, "Фамилия", parts[0])
        await mvd_sync_service.update_by_header(passport, "Имя", parts[1])
        await mvd_sync_service.update_by_header(passport, "Отчество", " ".join(parts[2:]))
    else:
        header = FIELD_MAP[field]
        await citizens_service.update_field(passport, header, value)
        if field == "status":
            await mvd_sync_service.update_mvd_status(passport, value)
        elif field == "wanted":
            await mvd_sync_service.update_mvd_wanted(passport, value)
        elif field == "fines":
            await mvd_sync_service.update_mvd_fines(passport, value)
        elif field == "licenses":
            await mvd_sync_service.update_mvd_licenses(passport, value)
        else:
            await mvd_sync_service.update_by_header(passport, header, value)
    await log_action(message.from_user.id, message.from_user.username or "", "Редактирование", passport, f"{field}: {value}")
    await state.clear()
    await message.answer("Изменение сохранено.")


@router.callback_query(F.data.startswith("admin:status:"))
async def set_status(callback: CallbackQuery) -> None:
    if not admin_allowed(callback.from_user.id, callback.message.chat.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    _, _, passport, status = callback.data.split(":", 3)
    await citizens_service.update_field(int(passport), "Статус", status)
    await mvd_sync_service.update_mvd_status(int(passport), status)
    await log_action(callback.from_user.id, callback.from_user.username or "", "Статус", passport, status)
    await callback.message.answer(f"Статус паспорта №{passport}: {status}.")
    await callback.answer()


@router.callback_query(F.data.startswith("admin:fine:"))
async def fine_from_card(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data == "admin:fine:start":
        return
    if not admin_allowed(callback.from_user.id, callback.message.chat.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    passport = int(callback.data.split(":")[-1])
    await state.clear()
    await state.update_data(passport=passport)
    await state.set_state(AdminFineStates.waiting_amount)
    await callback.message.answer("Введите сумму штрафа:")
    await callback.answer()


@router.message(AdminFineStates.waiting_passport)
async def fine_passport(message: Message, state: FSMContext) -> None:
    if not admin_allowed(message.from_user.id, message.chat.id):
        await state.clear()
        return
    value = (message.text or "").strip()
    if not value.isdigit():
        await message.answer("Введите числовой паспорт.")
        return
    await state.update_data(passport=int(value))
    await state.set_state(AdminFineStates.waiting_amount)
    await message.answer("Введите сумму штрафа:")


@router.message(AdminFineStates.waiting_amount)
async def fine_amount(message: Message, state: FSMContext) -> None:
    if not admin_allowed(message.from_user.id, message.chat.id):
        await state.clear()
        return
    value = (message.text or "").strip()
    if not value.isdigit() or int(value) <= 0:
        await message.answer("Введите положительную сумму.")
        return
    await state.update_data(amount=int(value))
    await state.set_state(AdminFineStates.waiting_reason)
    await message.answer("Введите причину штрафа:")


@router.message(AdminFineStates.waiting_reason)
async def fine_reason(message: Message, state: FSMContext) -> None:
    if not admin_allowed(message.from_user.id, message.chat.id):
        await state.clear()
        return
    data = await state.get_data()
    passport = int(data["passport"])
    amount = int(data["amount"])
    reason = (message.text or "").strip()
    citizen = await citizens_service.find_by_passport(passport)
    current = int((citizen.fines if citizen else "0") or "0")
    await citizens_service.update_field(passport, "Штрафы", str(current + amount))
    await mvd_sync_service.update_mvd_fines(passport, str(current + amount))
    await append_fine(passport, citizen.telegram_id if citizen else "", amount, reason, message.from_user.username or str(message.from_user.id))
    await log_action(message.from_user.id, message.from_user.username or "", "Штраф", passport, f"{amount}: {reason}")
    await state.clear()
    await message.answer("Штраф выдан.")


@router.callback_query(F.data.startswith("admin:wanted:"))
async def wanted_from_card(callback: CallbackQuery, state: FSMContext) -> None:
    if callback.data == "admin:wanted:start":
        return
    if not admin_allowed(callback.from_user.id, callback.message.chat.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    passport = int(callback.data.split(":")[-1])
    await state.clear()
    await state.update_data(passport=passport)
    await state.set_state(AdminWantedStates.waiting_reason)
    await callback.message.answer("Введите причину розыска:")
    await callback.answer()


@router.message(AdminWantedStates.waiting_passport)
async def wanted_passport(message: Message, state: FSMContext) -> None:
    if not admin_allowed(message.from_user.id, message.chat.id):
        await state.clear()
        return
    value = (message.text or "").strip()
    if not value.isdigit():
        await message.answer("Введите числовой паспорт.")
        return
    await state.update_data(passport=int(value))
    await state.set_state(AdminWantedStates.waiting_reason)
    await message.answer("Введите причину розыска:")


@router.message(AdminWantedStates.waiting_reason)
async def wanted_reason(message: Message, state: FSMContext) -> None:
    if not admin_allowed(message.from_user.id, message.chat.id):
        await state.clear()
        return
    data = await state.get_data()
    passport = int(data["passport"])
    reason = (message.text or "").strip()
    await citizens_service.update_field(passport, "Розыск", reason)
    await mvd_sync_service.update_mvd_wanted(passport, reason)
    await append_wanted(passport, reason, message.from_user.username or str(message.from_user.id))
    await log_action(message.from_user.id, message.from_user.username or "", "Розыск", passport, reason)
    await state.clear()
    await message.answer("Персонаж объявлен в розыск.")


@router.callback_query(F.data.startswith("admin:unwanted:"))
async def remove_wanted(callback: CallbackQuery) -> None:
    if not admin_allowed(callback.from_user.id, callback.message.chat.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    passport = int(callback.data.split(":")[-1])
    await citizens_service.update_field(passport, "Розыск", "Нет")
    await mvd_sync_service.update_mvd_wanted(passport, "Нет")
    await log_action(callback.from_user.id, callback.from_user.username or "", "Снятие розыска", passport, "Нет")
    await callback.message.answer("Розыск снят.")
    await callback.answer()
