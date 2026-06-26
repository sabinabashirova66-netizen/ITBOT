import asyncio
import logging
import os

from aiogram import Bot

logger = logging.getLogger(__name__)

MANAGER_CHAT_ID = os.getenv("MANAGER_CHAT_ID", "")


async def notify_manager(
    bot: Bot,
    name: str,
    phone: str | None,
    current_job: str,
    tech_experience: str,
    work_style: str,
    study_time: str,
    goal: str,
    selected_course: str,
    manager_note: str,
) -> None:
    if not MANAGER_CHAT_ID:
        logger.warning("MANAGER_CHAT_ID не задан — уведомление не отправлено")
        return

    contact = phone if phone else "не указан (попросить при звонке)"

    text = (
        "🔥 <b>Новый лид!</b>\n\n"
        f"👤 Имя: {name}\n"
        f"📱 Телефон: {contact}\n"
        f"✅ Выбранный курс: <b>{selected_course}</b>\n\n"
        f"📋 <b>Профиль:</b>\n"
        f"  • Деятельность: {current_job}\n"
        f"  • Опыт с технологиями: {tech_experience}\n"
        f"  • Стиль работы: {work_style}\n"
        f"  • Время на учёбу: {study_time}\n"
        f"  • Цель: {goal}\n\n"
        f"💬 <b>Заметка:</b> {manager_note}"
    )

    logger.info(
        "Отправка уведомления: MANAGER_CHAT_ID из .env=%s (тип %s), лид name=%s",
        MANAGER_CHAT_ID, type(MANAGER_CHAT_ID).__name__, name,
    )
    try:
        await bot.send_message(chat_id=int(MANAGER_CHAT_ID), text=text, parse_mode="HTML")
        logger.info("Уведомление отправлено → chat_id=%s (из .env, не от пользователя)", MANAGER_CHAT_ID)
    except Exception as e:
        logger.error("Ошибка отправки уведомления менеджеру: %s", e)
        await asyncio.sleep(5)
        try:
            await bot.send_message(chat_id=int(MANAGER_CHAT_ID), text=text, parse_mode="HTML")
        except Exception as e2:
            logger.error("Повторная попытка уведомления провалилась: %s", e2)
