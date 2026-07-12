from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from keyboards.licenses import answers_keyboard, licenses_keyboard
from keyboards.user import main_menu
from services.citizens import citizens_service
from services.license_tests import license_tests_service
from states.licenses import LicenseStates

router = Router(name="licenses")


@router.message(F.text == "🚗 Лицензии")
async def show_licenses(message: Message) -> None:
    await message.answer("Выберите тип лицензии:", reply_markup=licenses_keyboard())


@router.callback_query(F.data.startswith("license:start:"))
async def start_license(callback: CallbackQuery, state: FSMContext) -> None:
    citizen = await citizens_service.find_by_telegram(callback.from_user.id)
    if citizen is None:
        await callback.message.answer("Сначала получите паспорт.")
        await callback.answer()
        return
    code = callback.data.split(":")[-1]
    cfg = license_tests_service.config(code)
    if cfg.requires_license and not license_tests_service.can_apply_hunting(citizen.licenses):
        await callback.message.answer("Для оформления охотничьей лицензии сначала получите лицензию на оружие.")
        await callback.answer()
        return
    await state.clear()
    await state.update_data(license_code=code, passport=citizen.passport, fio=citizen.fio, telegram_id=callback.from_user.id)
    if cfg.questions_count == 0:
        await state.set_state(LicenseStates.waiting_payment_photo)
        await callback.message.answer(
            f"Оплатите государственную пошлину:\n\n/donate {cfg.fee}\n\nПосле оплаты отправьте фотографию подтверждения."
        )
        await callback.answer()
        return
    license_tests_service.start_test(callback.from_user.id, code)
    await state.set_state(LicenseStates.answering_test)
    await send_current_question(callback.message, callback.from_user.id, code)
    await callback.answer()


async def send_current_question(message: Message, user_id: int, code: str) -> None:
    cfg = license_tests_service.config(code)
    current = license_tests_service.get_current_question(user_id, code)
    if current is None:
        return
    index, _score, question, answers, question_id = current
    await message.answer(
        f"Вопрос {index + 1} из {cfg.questions_count}\n\n{question}",
        reply_markup=answers_keyboard(question_id, answers),
    )


@router.callback_query(F.data.startswith("license:answer:"))
async def answer_license(callback: CallbackQuery, state: FSMContext) -> None:
    data = await state.get_data()
    code = data.get("license_code")
    if not code:
        await callback.answer("Тест не найден.", show_alert=True)
        return
    _, _, question_id, answer_index = callback.data.split(":")
    accepted, score, total, finished = license_tests_service.answer(callback.from_user.id, code, question_id, int(answer_index))
    if not accepted:
        await callback.answer("Ответ уже принят или тест завершён.", show_alert=True)
        return
    try:
        await callback.message.edit_reply_markup(reply_markup=None)
    except Exception:
        await callback.message.answer("Ответ принят.")
    cfg = license_tests_service.config(code)
    if finished:
        license_tests_service.clear(callback.from_user.id, code)
        if score >= cfg.passing_score:
            await state.set_state(LicenseStates.waiting_payment_photo)
            await state.update_data(score=score, max_score=total)
            await callback.message.answer(
                f"Тест сдан: {score} из {total}.\n\n"
                f"Оплатите государственную пошлину:\n\n/donate {cfg.fee}\n\n"
                "После оплаты отправьте фотографию подтверждения."
            )
        else:
            await state.clear()
            await callback.message.answer(
                f"Тест не сдан: {score} из {total}.\nНеобходимо минимум {cfg.passing_score}.",
                reply_markup=main_menu,
            )
        await callback.answer()
        return
    await send_current_question(callback.message, callback.from_user.id, code)
    await callback.answer()
