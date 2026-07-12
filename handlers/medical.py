from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from keyboards.admin import request_decision_keyboard
from keyboards.user import cancel_menu, main_menu
from services.citizens import citizens_service
from services.notifications import send_admin_message
from services.requests import requests_service
from states.medical import MedicalStates

router = Router(name="medical")


@router.message(F.text == "Медкарта")
async def begin_medical(message: Message, state: FSMContext) -> None:
    citizen = await citizens_service.find_by_telegram(message.from_user.id)
    if citizen is None:
        await message.answer("Сначала получите паспорт.")
        return
    await state.clear()
    await state.update_data(passport=citizen.passport, fio=citizen.fio, telegram_id=message.from_user.id)
    await state.set_state(MedicalStates.height)
    await message.answer("Введите рост персонажа:", reply_markup=cancel_menu)


@router.message(MedicalStates.height)
async def med_height(message: Message, state: FSMContext) -> None:
    await state.update_data(height=(message.text or "").strip())
    await state.set_state(MedicalStates.weight)
    await message.answer("Введите вес персонажа:")


@router.message(MedicalStates.weight)
async def med_weight(message: Message, state: FSMContext) -> None:
    await state.update_data(weight=(message.text or "").strip())
    await state.set_state(MedicalStates.blood)
    await message.answer("Введите группу крови:")


@router.message(MedicalStates.blood)
async def med_blood(message: Message, state: FSMContext) -> None:
    await state.update_data(blood=(message.text or "").strip())
    await state.set_state(MedicalStates.allergies)
    await message.answer("Введите аллергии или Нет:")


@router.message(MedicalStates.allergies)
async def med_allergies(message: Message, state: FSMContext) -> None:
    await state.update_data(allergies=(message.text or "").strip())
    await state.set_state(MedicalStates.chronic)
    await message.answer("Введите хронические заболевания или Нет:")


@router.message(MedicalStates.chronic)
async def med_chronic(message: Message, state: FSMContext) -> None:
    await state.update_data(chronic=(message.text or "").strip())
    await state.set_state(MedicalStates.notes)
    await message.answer("Введите примечания или Нет:")


@router.message(MedicalStates.notes)
async def med_notes(message: Message, state: FSMContext) -> None:
    await state.update_data(notes=(message.text or "").strip())
    data = await state.get_data()
    request_id = requests_service.create_local("medical", message.from_user.id, data)
    await requests_service.append_sheet(request_id, "Медкарта", message.from_user.id, message.from_user.username or "", str(data["passport"]), data["fio"], data)
    ok = await send_admin_message(
        message.bot,
        f"ЗАЯВКА НА МЕДКАРТУ #{request_id}\n\n"
        f"Паспорт: {data['passport']}\nФИО: {data['fio']}\n"
        f"Рост: {data['height']}\nВес: {data['weight']}\nГруппа крови: {data['blood']}\n"
        f"Аллергии: {data['allergies']}\nХронические заболевания: {data['chronic']}\nПримечания: {data['notes']}",
        reply_markup=request_decision_keyboard("medical", request_id),
    )
    await state.clear()
    if ok:
        await message.answer("Медкарта отправлена на проверку.", reply_markup=main_menu)
    else:
        await message.answer("Не удалось передать заявку администрации. Попробуйте позднее.", reply_markup=main_menu)
