from aiogram.fsm.state import State, StatesGroup


class Dialog(StatesGroup):
    greeting = State()
    faq_mode = State()
    quiz_q1 = State()
    quiz_q2 = State()
    quiz_q3 = State()
    quiz_q4 = State()
    quiz_q5 = State()
    top2_choice = State()
    capture_phone = State()
    lead_saved = State()
