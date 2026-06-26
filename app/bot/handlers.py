"""Обработчики сообщений и колбэков aiogram 3.x."""
import logging
import re

from aiogram import Bot, Router, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message, CallbackQuery, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder

from app.bot.fsm import Dialog
from app.bot.keyboards import (
    main_menu_keyboard,
    quiz_q1_keyboard,
    quiz_q2_keyboard,
    quiz_q3_keyboard,
    quiz_q4_keyboard,
    quiz_q5_keyboard,
    share_phone_keyboard,
)
from app.db.crud import save_lead
from app.llm.chain import (
    generate_faq_answer,
    generate_top2_recommendation,
    generate_manager_note,
    summarize_memory,
)
from app.llm.memory import ConversationMemory
from app.notifications.telegram import notify_manager

logger = logging.getLogger(__name__)
router = Router()

PHONE_RE = re.compile(r"^\+[0-9]{7,15}$")
MAX_PHONE_ATTEMPTS = 3

CURRENT_JOB_HUMAN = {
    "job_not_it": "Не связан с IT",
    "job_partial": "Частично связан с IT",
    "job_in_it": "Уже в IT",
}
TECH_EXPERIENCE_HUMAN = {
    "tech_never": "Никогда не пробовал",
    "tech_little": "Немного пробовал",
    "tech_basics": "Есть базовые знания",
}
WORK_STYLE_HUMAN = {
    "style_code": "Писать код и логику",
    "style_design": "Создавать визуал и дизайн",
    "style_qa": "Тестировать и находить ошибки",
}
STUDY_TIME_HUMAN = {
    "time_under5": "До 5 часов",
    "time_5_10": "5–10 часов",
    "time_over10": "10+ часов",
}
GOAL_HUMAN = {
    "goal_job": "Сменить работу",
    "goal_freelance": "Фриланс",
    "goal_project": "Свой проект",
    "goal_self": "Для себя",
}


# ─────────────────────────────────────────────────────────────
# Вспомогательные функции
# ─────────────────────────────────────────────────────────────

def _get_memory(data: dict) -> ConversationMemory:
    raw = data.get("memory")
    if raw:
        return ConversationMemory.deserialize(raw)
    return ConversationMemory()


def _get_name(data: dict) -> str:
    return data.get("name", "")


async def _update_memory(state: FSMContext, role: str, content: str) -> None:
    data = await state.get_data()
    memory = _get_memory(data)
    memory.add_message(role, content)
    if memory.should_summarize():
        new_summary = await summarize_memory(memory)
        memory.apply_summary(new_summary)
    data["memory"] = memory.serialize()
    await state.set_data(data)


async def _safe_llm_answer(
    user_message: str,
    memory: ConversationMemory,
    fsm_state: str,
    user_name: str,
) -> str:
    try:
        return await generate_faq_answer(user_message, memory, fsm_state, user_name)
    except Exception as e:
        logger.error("Groq API ошибка: %s", e)
        return "Секунду, обрабатываю запрос... Попробуй повторить через момент."


# ─────────────────────────────────────────────────────────────
# /start и /restart
# ─────────────────────────────────────────────────────────────

@router.message(CommandStart())
@router.message(Command("restart"))
async def cmd_start(message: Message, state: FSMContext) -> None:
    await state.clear()
    await state.set_state(Dialog.greeting)
    await message.answer(
        "Привет! 👋 Я ИИ-помощник онлайн-школы CodeStart.\n"
        "Помогу выбрать подходящий курс и ответить на вопросы.\n\n"
        "Как тебя зовут?",
        reply_markup=ReplyKeyboardRemove(),
    )


# ─────────────────────────────────────────────────────────────
# /manager — немедленно передать менеджеру
# ─────────────────────────────────────────────────────────────

@router.message(Command("manager"))
async def cmd_manager(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    name = _get_name(data) or "Пользователь"
    await message.answer(
        f"Понял, {name}! Оставь свой телефон — менеджер свяжется с тобой в течение часа.",
        reply_markup=share_phone_keyboard(),
    )
    await state.update_data(from_manager_cmd=True)
    await state.set_state(Dialog.capture_phone)


# ─────────────────────────────────────────────────────────────
# STATE_1: Приветствие — получаем имя
# ─────────────────────────────────────────────────────────────

@router.message(Dialog.greeting)
async def handle_greeting(message: Message, state: FSMContext) -> None:
    name = message.text.strip().split()[0] if message.text else "друг"
    await state.update_data(name=name, faq_count=0, phone_attempts=0)
    await _update_memory(state, "user", message.text or "")

    reply = f"Рад познакомиться, {name}! 😊\nЧем могу помочь?"
    await message.answer(reply, reply_markup=main_menu_keyboard())
    await _update_memory(state, "assistant", reply)
    await state.set_state(Dialog.faq_mode)


# ─────────────────────────────────────────────────────────────
# STATE_2: FAQ-режим
# ─────────────────────────────────────────────────────────────

@router.callback_query(F.data == "action_courses")
async def action_courses(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    data = await state.get_data()
    memory = _get_memory(data)
    answer = await _safe_llm_answer("Расскажи про доступные курсы", memory, "faq_mode", _get_name(data))
    await callback.message.answer(answer)
    await _update_memory(state, "assistant", answer)
    await state.set_state(Dialog.faq_mode)


@router.callback_query(F.data == "action_faq")
async def action_faq(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await callback.message.answer("Задавай свой вопрос — отвечу на всё о курсах и школе.")
    await state.set_state(Dialog.faq_mode)


@router.callback_query(F.data == "action_quiz")
async def action_quiz(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await _start_quiz(callback.message, state)


async def _start_quiz(message: Message, state: FSMContext) -> None:
    await message.answer(
        "Отлично, пройдём небольшой тест — 5 вопросов, и я подберу тебе курс 🎯\n\n"
        "<b>Вопрос 1 из 5.</b> Чем занимаешься сейчас?",
        parse_mode="HTML",
        reply_markup=quiz_q1_keyboard(),
    )
    await state.set_state(Dialog.quiz_q1)


@router.message(Dialog.faq_mode)
async def handle_faq_message(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    faq_count: int = data.get("faq_count", 0) + 1
    await state.update_data(faq_count=faq_count)

    text_lower = (message.text or "").lower()
    if any(kw in text_lower for kw in ("какой курс", "что выбрать", "посоветуй курс", "подобрать курс")):
        await _start_quiz(message, state)
        return

    await _update_memory(state, "user", message.text or "")
    memory = _get_memory(await state.get_data())
    answer = await _safe_llm_answer(message.text or "", memory, "faq_mode", _get_name(data))
    await message.answer(answer)
    await _update_memory(state, "assistant", answer)

    if faq_count >= 3:
        kb = InlineKeyboardBuilder()
        kb.button(text="🎯 Подобрать курс", callback_data="action_quiz")
        await message.answer(
            "Кстати, могу подобрать курс лично под тебя — займёт 5 вопросов.",
            reply_markup=kb.as_markup(),
        )


# ─────────────────────────────────────────────────────────────
# STATE 3–7: Квиз (5 вопросов)
# ─────────────────────────────────────────────────────────────

@router.callback_query(Dialog.quiz_q1, F.data.in_({"job_not_it", "job_partial", "job_in_it"}))
async def quiz_answer_q1(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(current_job=callback.data)
    await callback.message.answer(
        "<b>Вопрос 2 из 5.</b> Был ли у тебя опыт работы с технологиями?",
        parse_mode="HTML",
        reply_markup=quiz_q2_keyboard(),
    )
    await state.set_state(Dialog.quiz_q2)


@router.callback_query(Dialog.quiz_q2, F.data.in_({"tech_never", "tech_little", "tech_basics"}))
async def quiz_answer_q2(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(tech_experience=callback.data)
    await callback.message.answer(
        "<b>Вопрос 3 из 5.</b> Что тебе ближе по характеру работы?",
        parse_mode="HTML",
        reply_markup=quiz_q3_keyboard(),
    )
    await state.set_state(Dialog.quiz_q3)


@router.callback_query(Dialog.quiz_q3, F.data.in_({"style_code", "style_design", "style_qa"}))
async def quiz_answer_q3(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(work_style=callback.data)
    await callback.message.answer(
        "<b>Вопрос 4 из 5.</b> Сколько часов в неделю готов учиться?",
        parse_mode="HTML",
        reply_markup=quiz_q4_keyboard(),
    )
    await state.set_state(Dialog.quiz_q4)


@router.callback_query(Dialog.quiz_q4, F.data.in_({"time_under5", "time_5_10", "time_over10"}))
async def quiz_answer_q4(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(study_time=callback.data)
    await callback.message.answer(
        "<b>Вопрос 5 из 5.</b> Какая главная цель?",
        parse_mode="HTML",
        reply_markup=quiz_q5_keyboard(),
    )
    await state.set_state(Dialog.quiz_q5)


@router.callback_query(Dialog.quiz_q5, F.data.in_({"goal_job", "goal_freelance", "goal_project", "goal_self"}))
async def quiz_answer_q5(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    await state.update_data(goal=callback.data)
    data = await state.get_data()

    await callback.message.answer("Анализирую твои ответы... ⏳")

    try:
        top2 = await generate_top2_recommendation(
            current_job=CURRENT_JOB_HUMAN.get(data["current_job"], data["current_job"]),
            tech_experience=TECH_EXPERIENCE_HUMAN.get(data["tech_experience"], data["tech_experience"]),
            work_style=WORK_STYLE_HUMAN.get(data["work_style"], data["work_style"]),
            study_time=STUDY_TIME_HUMAN.get(data["study_time"], data["study_time"]),
            goal=GOAL_HUMAN.get(data["goal"], data["goal"]),
        )
    except Exception as e:
        logger.error("Ошибка генерации рекомендации: %s", e)
        top2 = []

    if len(top2) < 2:
        await callback.message.answer(
            "Не смог подобрать рекомендации — попробуй пройти тест ещё раз.",
            reply_markup=main_menu_keyboard(),
        )
        await state.set_state(Dialog.faq_mode)
        return

    await state.update_data(top2=top2)

    text = "🎯 <b>Вот два курса, которые подойдут тебе лучше всего:</b>\n\n"
    text += f"1️⃣ <b>{top2[0]['course']}</b>\n{top2[0]['description']}\n\n"
    text += f"2️⃣ <b>{top2[1]['course']}</b>\n{top2[1]['description']}\n\n"
    text += "Какой из них тебе ближе?"

    kb = InlineKeyboardBuilder()
    kb.button(text=top2[0]["course"], callback_data=f"choose_{top2[0]['course']}")
    kb.button(text=top2[1]["course"], callback_data=f"choose_{top2[1]['course']}")
    kb.adjust(1)

    await callback.message.answer(text, parse_mode="HTML", reply_markup=kb.as_markup())
    await state.set_state(Dialog.top2_choice)


# ─────────────────────────────────────────────────────────────
# STATE_8: Выбор из ТОП-2
# ─────────────────────────────────────────────────────────────

@router.callback_query(Dialog.top2_choice, F.data.startswith("choose_"))
async def handle_top2_choice(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.answer()
    selected_course = callback.data[len("choose_"):]
    await state.update_data(selected_course=selected_course)

    await callback.message.answer(
        f"Отличный выбор! 🎉\n\n"
        f"Запишем тебя на <b>{selected_course}</b>.\n"
        "Укажи свой телефон — менеджер свяжется в течение часа. 📱",
        parse_mode="HTML",
        reply_markup=share_phone_keyboard(),
    )
    await state.set_state(Dialog.capture_phone)


# ─────────────────────────────────────────────────────────────
# STATE_9: Сбор телефона
# ─────────────────────────────────────────────────────────────

@router.message(Dialog.capture_phone, F.contact)
async def handle_contact(message: Message, state: FSMContext, bot: Bot) -> None:
    phone = message.contact.phone_number
    if not phone.startswith("+"):
        phone = "+" + phone
    await _finalize_lead(message, state, bot, phone=phone)


@router.message(Dialog.capture_phone)
async def handle_phone_text(message: Message, state: FSMContext, bot: Bot) -> None:
    data = await state.get_data()

    if data.get("waiting_email"):
        email = (message.text or "").strip()
        await _finalize_lead(message, state, bot, email=email)
        return

    text = (message.text or "").strip().replace(" ", "").replace("-", "")

    if PHONE_RE.match(text):
        await _finalize_lead(message, state, bot, phone=text)
        return

    attempts: int = data.get("phone_attempts", 0) + 1
    await state.update_data(phone_attempts=attempts)

    if attempts >= MAX_PHONE_ATTEMPTS:
        await message.answer(
            "Не получается с телефоном — напиши свой email, и менеджер свяжется по почте.",
            reply_markup=ReplyKeyboardRemove(),
        )
        await state.update_data(waiting_email=True)
        return

    await message.answer(
        f"Формат не подходит (нужен вид +XXXXXXXXXXX, от 7 до 15 цифр после +). "
        f"Попытка {attempts} из {MAX_PHONE_ATTEMPTS}."
    )


async def _finalize_lead(
    message: Message,
    state: FSMContext,
    bot: Bot,
    phone: str | None = None,
    email: str | None = None,
) -> None:
    data = await state.get_data()
    name = _get_name(data) or "Пользователь"
    current_job = data.get("current_job", "")
    tech_experience = data.get("tech_experience", "")
    work_style = data.get("work_style", "")
    study_time = data.get("study_time", "")
    goal = data.get("goal", "")
    selected_course = data.get("selected_course", "Не определён")

    experience_combined = " | ".join(filter(None, [
        CURRENT_JOB_HUMAN.get(current_job, current_job),
        TECH_EXPERIENCE_HUMAN.get(tech_experience, tech_experience),
        WORK_STYLE_HUMAN.get(work_style, work_style),
    ]))

    try:
        manager_note = await generate_manager_note(
            current_job=CURRENT_JOB_HUMAN.get(current_job, current_job),
            tech_experience=TECH_EXPERIENCE_HUMAN.get(tech_experience, tech_experience),
            work_style=WORK_STYLE_HUMAN.get(work_style, work_style),
            study_time=STUDY_TIME_HUMAN.get(study_time, study_time),
            goal=GOAL_HUMAN.get(goal, goal),
            course=selected_course,
        )
    except Exception:
        manager_note = "Заметка недоступна."

    try:
        await save_lead(
            telegram_id=message.from_user.id,
            name=name,
            phone=phone,
            email=email,
            experience=experience_combined or None,
            study_time=STUDY_TIME_HUMAN.get(study_time, study_time) or None,
            goal=GOAL_HUMAN.get(goal, goal) or None,
            recommended_course=selected_course,
            manager_note=manager_note,
        )
    except Exception as e:
        logger.error("Ошибка сохранения лида: %s", e)

    await notify_manager(
        bot=bot,
        name=name,
        phone=phone,
        current_job=CURRENT_JOB_HUMAN.get(current_job, current_job),
        tech_experience=TECH_EXPERIENCE_HUMAN.get(tech_experience, tech_experience),
        work_style=WORK_STYLE_HUMAN.get(work_style, work_style),
        study_time=STUDY_TIME_HUMAN.get(study_time, study_time),
        goal=GOAL_HUMAN.get(goal, goal),
        selected_course=selected_course,
        manager_note=manager_note,
    )

    await message.answer(
        "Готово! ✅ Менеджер свяжется с тобой в течение часа.\n"
        "Если появятся вопросы — пиши, я здесь.",
        reply_markup=ReplyKeyboardRemove(),
    )
    await state.set_state(Dialog.lead_saved)


# ─────────────────────────────────────────────────────────────
# STATE_10: Лид сохранён
# ─────────────────────────────────────────────────────────────

@router.message(Dialog.lead_saved)
async def handle_after_lead(message: Message, state: FSMContext) -> None:
    await message.answer(
        "Твоя заявка уже у менеджера. Хочешь начать заново — напиши /start."
    )


# ─────────────────────────────────────────────────────────────
# Напоминание при молчании
# ─────────────────────────────────────────────────────────────

async def send_inactivity_reminder(bot: Bot, chat_id: int) -> None:
    try:
        await bot.send_message(chat_id, "Могу продолжить, когда будешь готов 😊")
    except Exception as e:
        logger.error("Ошибка напоминания: %s", e)


# ─────────────────────────────────────────────────────────────
# Fallback для неизвестных колбэков
# ─────────────────────────────────────────────────────────────

@router.callback_query()
async def unknown_callback(callback: CallbackQuery) -> None:
    await callback.answer("Используй кнопки в меню.")
