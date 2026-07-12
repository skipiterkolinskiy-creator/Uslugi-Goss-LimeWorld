from aiogram.fsm.state import State, StatesGroup


class LicenseStates(StatesGroup):
    answering_test = State()
    waiting_payment_photo = State()
    waiting_fine_payment_photo = State()
