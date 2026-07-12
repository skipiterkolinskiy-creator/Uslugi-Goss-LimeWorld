from aiogram.fsm.state import State, StatesGroup


class MedicalStates(StatesGroup):
    height = State()
    weight = State()
    blood = State()
    allergies = State()
    chronic = State()
    notes = State()
