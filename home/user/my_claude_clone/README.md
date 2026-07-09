# Claude.ai Clone — Python + Flask + SQLite

Полнофункциональный клон интерфейса Claude (Anthropic) с чатами, артефактами, проектами и Claude Code Jobs (MCP).

## Стек
- Flask 3, Flask-SQLAlchemy, Flask-Login
- SQLite
- Jinja2 + Tailwind CDN + Vanilla JS
- threading для Jobs

## Быстрый старт
```bash
cd my_claude_clone
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python app.py
```
Откройте http://localhost:5000

**Demo login:**  
`demo@claude.com` / `123456`

## Структура
```
my_claude_clone/
├── app.py
├── models.py
├── seed.py
├── config.py
├── requirements.txt
├── .env
├── routes/
│   ├── auth.py
│   ├── main.py
│   └── api.py
├── services/
│   ├── ai_client.py
│   ├── mcp_client.py
│   └── job_executor.py
├── static/
│   ├── css/style.css
│   └── js/chat.js, sidebar.js, projects.js, artifacts.js, jobs.js
└── templates/
    ├── base.html
    ├── dashboard.html
    ├── login.html
    ├── register.html
    ├── projects.html
    ├── artifacts.html
    ├── code.html
    └── settings.html
```

## AI провайдеры
В `.env`:
```
AI_PROVIDER=mock
# или anthropic / openrouter / groq
ANTHROPIC_API_KEY=sk-ant-...
OPENROUTER_API_KEY=...
GROQ_API_KEY=...
```
Mock-режим работает без ключей и автоматически генерирует артефакты кода.

## Функции
- ✅ Регистрация / вход / выход
- ✅ Чаты: создание, переименование, избранное, удаление, поиск
- ✅ Сообщения с AI, авто-извлечение ```code``` → Artifact
- ✅ Правая панель артефактов как в Claude
- ✅ Проекты: группировка чатов
- ✅ Artifacts: глобальный список
- ✅ Claude Code Jobs: queued → running → completed via MCP
- ✅ MCP-серверы: CRUD в /settings
- ✅ Responsive: сайдбар скрывается на мобилке
- ✅ Seed: 4 чата, 2 проекта, артефакты, 1 job

## API
- `GET/POST /api/conversations`
- `GET/POST /api/conversations/<id>/messages`
- `GET /api/artifacts`
- `CRUD /api/projects`
- `CRUD /api/jobs`
- `GET /api/mcp-servers`

Всё с `@login_required`, JSON-ошибки, логи в `app.log`.

Готово к деплою на Heroku / PythonAnywhere / Render.
