import logging
from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from database.models import CitizenData
from handlers.admin_panel import admin_allowed
from services.audit import log_action
from services.citizens import citizens_service
from services.license_tests import license_tests_service
from services.mvd_sync import mvd_sync_service
from services.records import append_fine, append_license, append_medical, append_wanted
from services.requests import requests_service
from states.admin import AdminRejectStates

router = Router(name="moderation")
logger = logging.getLogger(__name__)


@router.callback_query(F.data.startswith("mod:approve:"))
async def approve(callback: CallbackQuery) -> None:
    if not admin_allowed(callback.from_user.id, callback.message.chat.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    _, _, kind, raw_id = callback.data.split(":")
    request_id = int(raw_id)
    record = requests_service.get_local(request_id)
    if record is None:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return
    payload = record["payload"]
    if kind == "passport":
        next_passport = max(await citizens_service.max_passport(), await mvd_sync_service.max_passport()) + 1
        citizen = CitizenData(
            passport=next_passport,
            login_code=citizens_service.make_login_code(next_passport),
            telegram_id=int(record["user_id"]),
            username=payload.get("username", ""),
            last_name=payload["last_name"],
            first_name=payload["first_name"],
            patronymic=payload["patronymic"],
            age=int(payload["age"]),
            birthdate=payload["birthdate"],
            gender=payload["gender"],
            first_citizenship=payload["first_citizenship"],
            second_citizenship=payload["second_citizenship"],
            nationality=payload["nationality"],
            skin=payload["skin"],
            hair=payload["hair"],
            eyes=payload["eyes"],
            appearance=payload["appearance"],
            military=payload["military"],
            photo_file_id=payload["photo_file_id"],
            registered_at=datetime.now().strftime("%d.%m.%Y %H:%M"),
        )
        await citizens_service.append(citizen)
        await mvd_sync_service.create_mvd_citizen(citizen)
        try:
            await callback.bot.send_message(
                citizen.telegram_id,
                f"Паспорт одобрен.\n\nПаспорт №{citizen.passport}\nКод входа: {citizen.login_code}",
            )
        except Exception:
            logger.exception("Не удалось уведомить пользователя об одобрении паспорта")
        await log_action(callback.from_user.id, callback.from_user.username or "", "Одобрение паспорта", citizen.passport, citizen.fio)
    elif kind == "license":
        passport = int(payload["passport"])
        citizen = await citizens_service.find_by_passport(passport)
        current = citizen.licenses if citizen else ""
        code = payload["license_code"]
        licenses = ", ".join(sorted({x.strip() for x in current.split(",") if x.strip()} | {code}))
        await citizens_service.update_field(passport, "Лицензии", licenses)
        await mvd_sync_service.update_mvd_licenses(passport, licenses)
        await append_license(request_id, payload, callback.from_user.username or str(callback.from_user.id), "Одобрена")
        await callback.bot.send_message(record["user_id"], f"Лицензия «{payload['license_title']}» одобрена.")
        await log_action(callback.from_user.id, callback.from_user.username or "", "Одобрение лицензии", passport, payload["license_title"])
    elif kind == "medical":
        await append_medical(request_id, payload, callback.from_user.username or str(callback.from_user.id))
        await callback.bot.send_message(record["user_id"], "Медкарта одобрена.")
        await log_action(callback.from_user.id, callback.from_user.username or "", "Одобрение медкарты", payload.get("passport", ""), payload.get("fio", ""))
    requests_service.mark(request_id, "approved")
    await callback.message.answer("Заявка одобрена.")
    await callback.answer()


@router.callback_query(F.data.startswith("mod:reject:"))
async def reject_begin(callback: CallbackQuery, state: FSMContext) -> None:
    if not admin_allowed(callback.from_user.id, callback.message.chat.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    _, _, kind, raw_id = callback.data.split(":")
    await state.clear()
    await state.update_data(kind=kind, request_id=int(raw_id))
    await state.set_state(AdminRejectStates.waiting_reason)
    await callback.message.answer("Введите причину отказа:")
    await callback.answer()


@router.message(AdminRejectStates.waiting_reason)
async def reject_reason(message: Message, state: FSMContext) -> None:
    if not admin_allowed(message.from_user.id, message.chat.id):
        await state.clear()
        return
    data = await state.get_data()
    request_id = int(data["request_id"])
    record = requests_service.get_local(request_id)
    reason = (message.text or "").strip()
    if not reason:
        await message.answer("Причина отказа обязательна.")
        return
    requests_service.mark(request_id, "rejected")
    if record:
        await message.bot.send_message(record["user_id"], f"Заявка отклонена.\nПричина: {reason}")
    await log_action(message.from_user.id, message.from_user.username or "", "Отказ", request_id, reason)
    await state.clear()
    await message.answer("Отказ отправлен пользователю.")


@router.callback_query(F.data.startswith("mod:fake:license:"))
async def fake_payment(callback: CallbackQuery) -> None:
    if not admin_allowed(callback.from_user.id, callback.message.chat.id):
        await callback.answer("Нет доступа.", show_alert=True)
        return
    request_id = int(callback.data.split(":")[-1])
    record = requests_service.get_local(request_id)
    if record is None:
        await callback.answer("Заявка не найдена.", show_alert=True)
        return
    payload = record["payload"]
    passport = int(payload["passport"])
    amount = int(payload["fee"]) * 2
    citizen = await citizens_service.find_by_passport(passport)
    current = int((citizen.fines if citizen else "0") or "0")
    reason = "Предоставление поддельного подтверждения оплаты государственной пошлины"
    await citizens_service.update_field(passport, "Штрафы", str(current + amount))
    await citizens_service.update_field(passport, "Розыск", reason)
    await mvd_sync_service.update_mvd_fines(passport, str(current + amount))
    await mvd_sync_service.update_mvd_wanted(passport, reason)
    await append_fine(passport, str(record["user_id"]), amount, reason, callback.from_user.username or str(callback.from_user.id))
    await append_wanted(passport, reason, callback.from_user.username or str(callback.from_user.id))
    await callback.bot.send_message(record["user_id"], f"Скрин оплаты признан поддельным.\nШтраф: {amount} рублей.\nПерсонаж объявлен в розыск.")
    await log_action(callback.from_user.id, callback.from_user.username or "", "Поддельный скрин", passport, str(amount))
    requests_service.mark(request_id, "fake")
    await callback.message.answer("Создан двойной штраф и розыск.")
    await callback.answer()
