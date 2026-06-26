from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton


def main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="📚 Узнать про курсы", callback_data="action_courses"),
            InlineKeyboardButton(text="❓ Задать вопрос", callback_data="action_faq"),
        ],
        [
            InlineKeyboardButton(text="🎯 Пройти тест", callback_data="action_quiz"),
        ],
    ])


def quiz_q1_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🏠 Не связан с IT", callback_data="job_not_it")],
        [InlineKeyboardButton(text="🔗 Частично связан", callback_data="job_partial")],
        [InlineKeyboardButton(text="💻 Уже в IT", callback_data="job_in_it")],
    ])


def quiz_q2_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="❌ Никогда не пробовал", callback_data="tech_never")],
        [InlineKeyboardButton(text="🔍 Немного пробовал", callback_data="tech_little")],
        [InlineKeyboardButton(text="📚 Есть базовые знания", callback_data="tech_basics")],
    ])


def quiz_q3_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⌨️ Писать код и логику", callback_data="style_code")],
        [InlineKeyboardButton(text="🎨 Создавать визуал и дизайн", callback_data="style_design")],
        [InlineKeyboardButton(text="🔎 Тестировать и находить ошибки", callback_data="style_qa")],
    ])


def quiz_q4_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⏱ До 5 часов", callback_data="time_under5")],
        [InlineKeyboardButton(text="⏰ 5–10 часов", callback_data="time_5_10")],
        [InlineKeyboardButton(text="🚀 10+ часов", callback_data="time_over10")],
    ])


def quiz_q5_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔄 Сменить работу", callback_data="goal_job")],
        [InlineKeyboardButton(text="💻 Фриланс", callback_data="goal_freelance")],
        [InlineKeyboardButton(text="🚀 Свой проект", callback_data="goal_project")],
        [InlineKeyboardButton(text="📚 Для себя", callback_data="goal_self")],
    ])


def share_phone_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="📱 Поделиться номером", request_contact=True)],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def manager_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👨‍💼 Связаться с менеджером", callback_data="action_manager")],
    ])
