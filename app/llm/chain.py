"""LangChain-цепочки для работы с Groq LLM."""
import logging
import os
import re

from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from app.llm.prompts import (
    SYSTEM_PROMPT,
    TOP2_RECOMMENDATION_PROMPT,
    MANAGER_NOTE_PROMPT,
    SUMMARY_PROMPT,
)
from app.llm.memory import ConversationMemory
from app.rag.retriever import retriever

logger = logging.getLogger(__name__)

MODEL_NAME = "llama-3.3-70b-versatile"

_VALID_COURSES = frozenset({
    "Frontend-разработчик",
    "Python-разработчик",
    "UI/UX дизайнер",
    "QA-инженер",
})


def _build_llm() -> ChatGroq:
    return ChatGroq(
        model=MODEL_NAME,
        temperature=0.7,
        max_tokens=512,
        api_key=os.getenv("GROQ_API_KEY"),
    )


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type(Exception),
    reraise=True,
)
async def _invoke_llm(llm: ChatGroq, messages: list) -> str:
    response = await llm.ainvoke(messages)
    return response.content


def _parse_top2(raw: str) -> list[dict]:
    results = []
    seen = set()
    for i in ("1", "2"):
        course_match = re.search(rf"КУРС_{i}:\s*(.+)", raw)
        desc_match = re.search(rf"ОПИСАНИЕ_{i}:\s*(.+?)(?=\nКУРС_|\Z)", raw, re.DOTALL)
        if not (course_match and desc_match):
            continue
        course = course_match.group(1).strip()
        for valid in _VALID_COURSES:
            if valid.lower() in course.lower() or course.lower() in valid.lower():
                course = valid
                break
        if course in seen:
            continue
        seen.add(course)
        results.append({
            "course": course,
            "description": desc_match.group(1).strip(),
        })
    return results


async def generate_faq_answer(
    user_message: str,
    memory: ConversationMemory,
    fsm_state: str,
    user_name: str = "",
) -> str:
    llm = _build_llm()
    rag_context = retriever.format_context(user_message)

    system_text = SYSTEM_PROMPT.format(
        fsm_state=fsm_state,
        user_profile=f"Имя: {user_name}" if user_name else "Имя неизвестно",
        conversation_summary=memory.summary or "Начало диалога",
        rag_context=rag_context or "Контекст недоступен",
    )

    messages = [SystemMessage(content=system_text)]
    for msg in memory.recent_messages[-5:]:
        if msg["role"] == "user":
            messages.append(HumanMessage(content=msg["content"]))
        else:
            messages.append(AIMessage(content=msg["content"]))
    messages.append(HumanMessage(content=user_message))

    return await _invoke_llm(llm, messages)


async def generate_top2_recommendation(
    current_job: str,
    tech_experience: str,
    work_style: str,
    study_time: str,
    goal: str,
) -> list[dict]:
    llm = _build_llm()
    query = f"курсы: деятельность {current_job}, опыт {tech_experience}, стиль {work_style}, цель {goal}"
    rag_context = retriever.format_context(query)

    prompt = TOP2_RECOMMENDATION_PROMPT.format(
        current_job=current_job,
        tech_experience=tech_experience,
        work_style=work_style,
        study_time=study_time,
        goal=goal,
        rag_context=rag_context or "Смотри доступные курсы в базе.",
    )
    messages = [HumanMessage(content=prompt)]
    raw = await _invoke_llm(llm, messages)
    return _parse_top2(raw)


async def generate_manager_note(
    current_job: str,
    tech_experience: str,
    work_style: str,
    study_time: str,
    goal: str,
    course: str,
) -> str:
    llm = _build_llm()
    prompt = MANAGER_NOTE_PROMPT.format(
        current_job=current_job,
        tech_experience=tech_experience,
        work_style=work_style,
        study_time=study_time,
        goal=goal,
        course=course,
    )
    messages = [HumanMessage(content=prompt)]
    return await _invoke_llm(llm, messages)


async def summarize_memory(memory: ConversationMemory) -> str:
    if not memory.should_summarize():
        return memory.summary

    llm = _build_llm()
    history_text = memory.get_history_for_summary()
    if not history_text:
        return memory.summary

    prompt = SUMMARY_PROMPT.format(history=history_text)
    messages = [HumanMessage(content=prompt)]
    try:
        return await _invoke_llm(llm, messages)
    except Exception as e:
        logger.error("Ошибка сжатия памяти: %s", e)
        return memory.summary
