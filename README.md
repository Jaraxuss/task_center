# TaskCenter

[中文版本](README.zh-CN.md)

TaskCenter is a context-aware task and reminder backend for AI agents, designed to turn customer conversations, meeting notes, and follow-up intentions into structured, auditable tasks with the right context attached.

It is not just another todo list. TaskCenter is built for the moment when a reminder fires and the human or agent needs to know what the task is, why it matters, what happened before, and what should happen next.

## Why TaskCenter Exists

Traditional reminders are good at saying "do this now." They are less good at preserving the surrounding context: the meeting note, customer commitment, previous decision, delivery blocker, or follow-up owner.

TaskCenter keeps tasks, reminders, events, and customer context connected so AI agents and humans can collaborate safely. The core use cases are customer follow-up, meeting notes to actions, evening reviews, recurring reminders, and human-in-the-loop task handling.

## What It Does

- Create, update, complete, defer, and cancel tasks through an agent-friendly REST API
- Store reminders, recurrence rules, task events, and customer context
- Preserve an audit trail for task state changes and reminder operations
- Support context-aware customer follow-up workflows
- Provide a lightweight mobile frontend for review and quick task actions
- Store timestamps in UTC while using `Asia/Shanghai` semantics for display and daily grouping by default
- Optionally send reminder cards through Feishu integrations using synthetic public examples

## Architecture

```text
Chat / Agent
    |
    v
TaskCenter API (FastAPI)
    |
    v
SQLite + SQLAlchemy
    |
    +--> Mobile UI (React + Vite)
    +--> Reminder delivery / Feishu card helpers
    +--> Audit events and customer context
```

The backend is the source of truth for task state, time semantics, recurrence, reminders, and event history. The mobile frontend is a separate Git submodule focused on lightweight review and task handling.

## Repository Layout

```text
backend/           FastAPI, SQLite, SQLAlchemy, reminders, recurrence, events
mobile_frontend/   React, TypeScript, Vite mobile UI (Git submodule)
docs/              Product notes, API contract, timezone design, SDK docs
archive/frontend/  Archived desktop frontend, kept for historical reference
```

## Quickstart

Clone with the mobile frontend submodule:

```bash
git clone --recurse-submodules https://github.com/Jaraxuss/task_center.git
cd task_center
```

If you already cloned without submodules:

```bash
git submodule update --init --recursive
```

Start the backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Start the mobile frontend:

```bash
cd ../mobile_frontend
cp .env.example .env.local
npm install
npm run dev
```

Open:

```text
http://localhost:5174
```

Backend API docs are available at:

```text
http://127.0.0.1:8000/docs
```

## Development

Backend checks:

```bash
cd backend
source .venv/bin/activate
pip install -r requirements-dev.txt
ruff check .
pytest
```

Mobile build:

```bash
cd mobile_frontend
npm run build
```

## Documentation

- `docs/PROJECT_OVERVIEW.md`: current system map and recommended onboarding entry point
- `docs/PRD.md`: product goals, scope, and workflow assumptions
- `docs/API_CONTRACT.md`: API and field expectations
- `docs/TIMEZONE_DESIGN.md`: timezone model for dates, reminders, recurrence, and daily grouping
- `TASK_CENTER_API_FOR_AGENTS.md`: agent-facing API usage guide
- `backend/README.md`: backend setup, API overview, and runtime notes
- `mobile_frontend/README.md`: mobile frontend setup and interaction model
- `backend/scripts/sdk/README.md`: Feishu card helper scripts
- `docs/FEISHU_CARD_V1_SDK.md`: Feishu Card JSON 1.0 notes
- `docs/FEISHU_CARD_V2_SDK.md`: Feishu Card JSON 2.0 notes

## Privacy And Safety

TaskCenter is designed for workflows that may involve sensitive customer context. The public repository only includes synthetic examples.

Do not commit real customer data, chat logs, Feishu/OpenAI credentials, user IDs, real `open_id` values, production databases, logs, backups, or local `.env` files.

Use `.env.example` as a template and keep local runtime data under ignored directories such as `backend/data/` and `backend/logs/`.

## Data Model Highlights

TaskCenter centers on a few durable concepts:

- `Task`: the action item, status, owner-facing text, due time, and project/customer linkage
- `Reminder`: scheduled delivery metadata and optional external message target
- `TaskEvent`: auditable history for state changes and reminder updates
- `TaskRecurrence`: recurring task rules and next-run calculation
- Customer context: facts and materials that help agents retain follow-up memory

The project stores UTC-aware timestamps and returns ISO 8601 UTC strings through the API. UI grouping and display use `Asia/Shanghai` semantics unless configured otherwise.

## Roadmap

- Keep the backend API stable for agent-driven task creation and updates
- Improve reminder delivery reliability and observability
- Expand context-aware customer follow-up workflows
- Improve mobile task editing and review interactions
- Add lightweight CI and public contribution workflows
- Keep examples synthetic and safe for open source review

## License

MIT. See `LICENSE`.
