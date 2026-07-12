from aiogram.fsm.state import State, StatesGroup


class AdminSearchStates(StatesGroup):
    waiting_query = State()


class AdminEditStates(StatesGroup):
    waiting_value = State()


class AdminFineStates(StatesGroup):
    waiting_passport = State()
    waiting_amount = State()
    waiting_reason = State()


class AdminWantedStates(StatesGroup):
    waiting_passport = State()
    waiting_reason = State()


class AdminRejectStates(StatesGroup):
    waiting_reason = State()
