from aiogram.fsm.state import State, StatesGroup


class RegistrationStates(StatesGroup):
    last_name = State()
    first_name = State()
    patronymic = State()
    age = State()
    birthdate = State()
    gender = State()
    first_citizenship = State()
    second_citizenship = State()
    nationality = State()
    skin = State()
    hair = State()
    eyes = State()
    appearance = State()
    military = State()
    photo = State()


class LoginStates(StatesGroup):
    waiting_code = State()
