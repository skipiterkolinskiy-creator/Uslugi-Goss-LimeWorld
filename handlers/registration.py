from datetime import datetime

from aiogram import F, Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from keyboards.admin import request_decision_keyboard
from keyboards.user import cancel_menu, gender_menu, main_menu, yes_no_menu
from services.notifications import send_admin_photo
from services.requests import requests_service
from states.registration import LoginStates, RegistrationStates

router = Router(name="registration")


def text(message: Message) -> str:
    return (message.text or "").strip()


@router.message(F.text == "Отмена")
async def cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer("Действие отменено.", reply_markup=main_menu)


@router.message(F.text == "Регистрация")
async def begin_registration(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(RegistrationStates.last_name)
    await message.answer("Введите фамилию персонажа:", reply_markup=cancel_menu)


@router.message(F.text == "Войти по коду")
async def begin_login(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(LoginStates.waiting_code)
    await message.answer("Введите код входа вида UG-616-A7F2:", reply_markup=cancel_menu)


@router.message(LoginStates.waiting_code)
async def process_login(message: Message, state: FSMContext) -> None:
    from services.citizens import citizens_service

    citizen = await citizens_service.find_by_code(text(message))
    if not citizen:
        await message.answer("Код не найден. Проверьте ввод или пройдите регистрацию.")
        return
    await citizens_service.add_login_binding(citizen, message.from_user.id, message.from_user.username or "")
    await state.clear()
    await message.answer(f"Вы вошли как {citizen.fio}. Паспорт №{citizen.passport}", reply_markup=main_menu)


@router.message(RegistrationStates.last_name)
async def reg_last_name(message: Message, state: FSMContext) -> None:
    await state.update_data(last_name=text(message))
    await state.set_state(RegistrationStates.first_name)
    await message.answer("Введите имя персонажа:")


@router.message(RegistrationStates.first_name)
async def reg_first_name(message: Message, state: FSMContext) -> None:
    await state.update_data(first_name=text(message))
    await state.set_state(RegistrationStates.patronymic)
    await message.answer("Введите отчество персонажа:")


@router.message(RegistrationStates.patronymic)
async def reg_patronymic(message: Message, state: FSMContext) -> None:
    await state.update_data(patronymic=text(message))
    await state.set_state(RegistrationStates.age)
    await message.answer("Введите возраст от 14 до 200:")


@router.message(RegistrationStates.age)
async def reg_age(message: Message, state: FSMContext) -> None:
    value = text(message)
    if not value.isdigit() or not 14 <= int(value) <= 200:
        await message.answer("Возраст должен быть числом от 14 до 200.")
        return
    await state.update_data(age=int(value))
    await state.set_state(RegistrationStates.birthdate)
    await message.answer("Введите дату рождения в формате ДД.ММ.ГГГГ:")


@router.message(RegistrationStates.birthdate)
async def reg_birthdate(message: Message, state: FSMContext) -> None:
    try:
        datetime.strptime(text(message), "%d.%m.%Y")
    except ValueError:
        await message.answer("Дата должна быть в формате ДД.ММ.ГГГГ.")
        return
    await state.update_data(birthdate=text(message))
    await state.set_state(RegistrationStates.gender)
    await message.answer("Выберите пол:", reply_markup=gender_menu)


@router.message(RegistrationStates.gender)
async def reg_gender(message: Message, state: FSMContext) -> None:
    if text(message).lower() not in {"мужчина", "женщина"}:
        await message.answer("Выберите: Мужчина или Женщина.", reply_markup=gender_menu)
        return
    await state.update_data(gender=text(message).capitalize())
    await state.set_state(RegistrationStates.first_citizenship)
    await message.answer("Введите первое гражданство:", reply_markup=cancel_menu)


@router.message(RegistrationStates.first_citizenship)
async def reg_first_citizenship(message: Message, state: FSMContext) -> None:
    await state.update_data(first_citizenship=text(message))
    await state.set_state(RegistrationStates.second_citizenship)
    await message.answer("Введите дополнительные гражданства через запятую или Нет:")


@router.message(RegistrationStates.second_citizenship)
async def reg_second_citizenship(message: Message, state: FSMContext) -> None:
    await state.update_data(second_citizenship=text(message))
    await state.set_state(RegistrationStates.nationality)
    await message.answer("Введите национальность:")


@router.message(RegistrationStates.nationality)
async def reg_nationality(message: Message, state: FSMContext) -> None:
    await state.update_data(nationality=text(message))
    await state.set_state(RegistrationStates.skin)
    await message.answer("Введите цвет кожи:")


@router.message(RegistrationStates.skin)
async def reg_skin(message: Message, state: FSMContext) -> None:
    await state.update_data(skin=text(message))
    await state.set_state(RegistrationStates.hair)
    await message.answer("Введите цвет волос:")


@router.message(RegistrationStates.hair)
async def reg_hair(message: Message, state: FSMContext) -> None:
    await state.update_data(hair=text(message))
    await state.set_state(RegistrationStates.eyes)
    await message.answer("Введите цвет глаз:")


@router.message(RegistrationStates.eyes)
async def reg_eyes(message: Message, state: FSMContext) -> None:
    await state.update_data(eyes=text(message))
    await state.set_state(RegistrationStates.appearance)
    await message.answer("Опишите внешность персонажа:")


@router.message(RegistrationStates.appearance)
async def reg_appearance(message: Message, state: FSMContext) -> None:
    await state.update_data(appearance=text(message))
    data = await state.get_data()
    if int(data["age"]) < 18:
        await state.update_data(military="Не предусмотрен по возрасту")
        await ask_photo(message, state)
        return
    await state.set_state(RegistrationStates.military)
    await message.answer("Есть ли военный билет?", reply_markup=yes_no_menu)


@router.message(RegistrationStates.military)
async def reg_military(message: Message, state: FSMContext) -> None:
    if text(message).lower() not in {"да", "нет"}:
        await message.answer("Выберите: Да или Нет.", reply_markup=yes_no_menu)
        return
    await state.update_data(military=text(message).capitalize())
    await ask_photo(message, state)


async def ask_photo(message: Message, state: FSMContext) -> None:
    await state.set_state(RegistrationStates.photo)
    await message.answer(
        "Отправьте фотографию персонажа для документов.\n\n"
        "Требования:\n"
        "• лицо должно быть видно полностью;\n"
        "• персонаж смотрит прямо в камеру;\n"
        "• без улыбки;\n"
        "• без маски;\n"
        "• без солнцезащитных очков;\n"
        "• волосы не закрывают лицо;\n"
        "• одежда обычная или деловая;\n"
        "• религиозные головные уборы разрешены.",
    )


@router.message(RegistrationStates.photo)
async def reg_photo(message: Message, state: FSMContext) -> None:
    if not message.photo:
        await message.answer("Принимается только фотография. Отправьте фото персонажа.")
        return
    data = await state.get_data()
    photo_id = message.photo[-1].file_id
    payload = {**data, "photo_file_id": photo_id, "username": message.from_user.username or ""}
    request_id = requests_service.create_local("passport", message.from_user.id, payload)
    fio = f"{data['last_name']} {data['first_name']} {data['patronymic']}"
    await requests_service.append_sheet(request_id, "Паспорт", message.from_user.id, message.from_user.username or "", "", fio, payload)
    caption = (
        f"ЗАЯВКА НА ПАСПОРТ #{request_id}\n\n"
        f"ФИО: {fio}\n"
        f"Возраст: {data['age']}\n"
        f"Дата рождения: {data['birthdate']}\n"
        f"Пол: {data['gender']}\n"
        f"Гражданства: {data['first_citizenship']}; {data['second_citizenship']}\n"
        f"Национальность: {data['nationality']}\n"
        f"Внешность: {data['skin']}, {data['hair']}, {data['eyes']}; {data['appearance']}\n"
        f"Военный билет: {data['military']}\n"
        f"Telegram ID: {message.from_user.id}\n"
        f"Username: @{message.from_user.username or '-'}"
    )
    ok = await send_admin_photo(message.bot, photo_id, caption, reply_markup=request_decision_keyboard("passport", request_id))
    await state.clear()
    if ok:
        await message.answer("Заявка на паспорт отправлена администрации.", reply_markup=main_menu)
    else:
        await message.answer("Не удалось передать заявку администрации. Попробуйте позднее.", reply_markup=main_menu)
