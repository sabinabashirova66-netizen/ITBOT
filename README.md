# CodeStart — Telegram-бот ИИ-профориентатор

Telegram-бот для вымышленной онлайн IT-школы **CodeStart**. Отвечает на вопросы о курсах, проводит мини-тест, рекомендует курс через LLM + RAG и собирает контакт потенциального студента.

## Технологии

| Компонент | Технология |
|-----------|-----------|
| Бот | Python 3.11 + aiogram 3.x |
| LLM | Groq API (llama-3.3-70b-versatile) |
| Оркестрация LLM | LangChain |
| Векторный поиск | ChromaDB |
| Полнотекстовый поиск | BM25 (rank_bm25) |
| Состояния | Redis FSM |
| Хранение лидов | PostgreSQL 15 |
| Деплой | Docker Compose |

---

## Быстрый старт (5 шагов)

### 1. Клонировать репозиторий

```bash
git clone <repo-url>
cd tgbotITs
```

### 2. Заполнить .env

```bash
cp .env.example .env
# Открой .env и заполни все переменные (токен бота, Groq API key, MANAGER_CHAT_ID)
```

Минимально нужные переменные:
- `BOT_TOKEN` — токен бота от [@BotFather](https://t.me/BotFather)
- `GROQ_API_KEY` — ключ на [console.groq.com](https://console.groq.com)
- `MANAGER_CHAT_ID` — ID чата, куда слать уведомления о лидах (см. раздел ниже)

### 3. Запустить инфраструктуру

```bash
docker-compose up -d postgres redis chromadb
```

Подождать ~10 секунд, пока сервисы поднимутся.

### 4. Проиндексировать базу знаний

```bash
docker-compose run --rm bot python -m app.rag.indexer
```

Эта команда читает три файла из `app/rag/knowledge_base/`, разбивает на чанки и загружает в ChromaDB. Нужно выполнить один раз (и повторять при обновлении базы знаний).

### 5. Запустить бота

```bash
docker-compose up bot
```

Открой Telegram, найди своего бота и напиши `/start`.

---

## Как обновить базу знаний

1. Отредактируй (или замени) нужные файлы в `app/rag/knowledge_base/`:
   - `courses.txt` — информация о курсах
   - `faq.txt` — вопросы и ответы
   - `cases.txt` — истории выпускников

2. Перезапусти индексацию:

```bash
docker-compose run --rm bot python -m app.rag.indexer
```

ChromaDB пересоздаст коллекцию с новыми данными. Бот автоматически начнёт использовать обновлённую базу.

---

## Как найти MANAGER_CHAT_ID

Есть два способа:

**Способ 1 — через @userinfobot:**
1. Найди бота [@userinfobot](https://t.me/userinfobot) в Telegram
2. Напиши ему `/start`
3. Он пришлёт твой `id` — это и есть `MANAGER_CHAT_ID`

**Способ 2 — для группы или канала:**
1. Добавь своего бота в нужную группу/канал
2. Отправь любое сообщение в группу
3. Открой в браузере: `https://api.telegram.org/bot<BOT_TOKEN>/getUpdates`
4. Найди поле `"chat": {"id": -1001234567890}` — это `MANAGER_CHAT_ID`

Значение помести в `.env`:
```
MANAGER_CHAT_ID=-1001234567890
```

---

## Структура проекта

```
tgbotITs/
├── docker-compose.yml          # Оркестрация сервисов
├── Dockerfile                  # Образ для бота
├── .env.example                # Шаблон переменных окружения
├── requirements.txt            # Python-зависимости
├── README.md
└── app/
    ├── main.py                 # Точка входа, запуск polling
    ├── bot/
    │   ├── handlers.py         # Все обработчики сообщений и колбэков
    │   ├── fsm.py              # Состояния диалога (StatesGroup)
    │   └── keyboards.py        # Inline и Reply клавиатуры
    ├── rag/
    │   ├── indexer.py          # Индексация базы знаний в ChromaDB
    │   ├── retriever.py        # Гибридный поиск (Vector + BM25 + RRF)
    │   └── knowledge_base/
    │       ├── courses.txt     # Описание курсов
    │       ├── faq.txt         # Вопросы и ответы
    │       └── cases.txt       # Истории выпускников
    ├── llm/
    │   ├── chain.py            # LangChain-цепочки для Groq
    │   ├── prompts.py          # Системные промпты
    │   └── memory.py           # Summary Buffer Memory
    ├── db/
    │   ├── models.py           # SQLAlchemy модель Lead
    │   └── crud.py             # Асинхронное сохранение лидов
    └── notifications/
        └── telegram.py         # Уведомление менеджера
```

---

## Сценарий диалога (FSM)

```
/start → Приветствие (ввод имени)
       ↓
    FAQ-режим ← [Узнать про курсы] [Задать вопрос]
       ↓ (после 3 вопросов или "какой курс?")
    Тест Q1: Опыт в IT
       ↓
    Тест Q2: Время на учёбу
       ↓
    Тест Q3: Цель
       ↓
    Рекомендация курса (LLM + RAG)
       ↓ [Хочу записаться]
    Сбор телефона (до 3 попыток → fallback на email)
       ↓
    Лид сохранён → уведомление менеджеру
```

Команды, доступные в любой момент: `/start`, `/restart`, `/manager`

---

## Обработка ошибок

| Ситуация | Поведение |
|---|---|
| Groq API недоступен | Сообщение "Секунду..." + 3 повторные попытки |
| ChromaDB недоступна | Ответ через LLM без RAG-контекста |
| Неверный формат телефона | До 3 попыток → предложение оставить email |
| Ошибка уведомления менеджеру | Повторная попытка через 5 секунд |
