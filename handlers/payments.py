from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from keyboards.admin import request_decision_keyboard
from keyboards.user import main_menu
from services.license_tests import license_tests_service
from services.notifications import send_admin_photo
from services.requests import requests_service
from states.licenses import LicenseStates

router = Router(name="payments")


@router.message(LicenseStates.waiting_payment_photo)
async def process_license_payment(message: Message, state: FSMContext) -> None:
    if not message.photo:
        await message.answer("Подтверждение оплаты принимается только фотографией.")
        return
    data = await state.get_data()
    code = data["license_code"]
    cfg = license_tests_service.config(code)
    payload = {
        **data,
        "license_title": cfg.title,
        "fee": cfg.fee,
        "payment_photo_file_id": message.photo[-1].file_id,
    }
    request_id = requests_service.create_local("license", message.from_user.id, payload)
    await requests_service.append_sheet(request_id, "Лицензия", message.from_user.id, message.from_user.username or "", str(data["passport"]), data["fio"], payload)
    ok = await send_admin_photo(
        message.bot,
        message.photo[-1].file_id,
        f"ЗАЯВКА НА ЛИЦЕНЗИЮ #{request_id}\n\n"
        f"Паспорт: {data['passport']}\n"
        f"ФИО: {data['fio']}\n"
        f"Лицензия: {cfg.title}\n"
        f"Пошлина: {cfg.fee} рублей",
        reply_markup=request_decision_keyboard("license", request_id),
    )
    await state.clear()
    if ok:
        await message.answer("Заявка на лицензию отправлена администрации.", reply_markup=main_menu)
    else:
        await message.answer("Не удалось передать заявку администрации. Попробуйте позднее.", reply_markup=main_menu)


@router.message(LicenseStates.waiting_fine_payment_photo)
async def process_fine_payment(message: Message, state: FSMContext) -> None:
    if not message.photo:
        await message.answer("Подтверждение оплаты штрафа принимается только фотографией.")
        return
    await state.clear()
    await message.answer("Скрин оплаты штрафа принят и будет проверен администрацией.", reply_markup=main_menu)
