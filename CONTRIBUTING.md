# Contributing

Thanks for helping improve TaskCenter. This project is a context-aware task and reminder system, so contributions should protect user context, time semantics, and auditability.

## Development Setup

Backend:

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -r requirements-dev.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Mobile frontend:

```bash
cd mobile_frontend
cp .env.example .env.local
npm install
npm run dev
```

The mobile frontend runs on `http://localhost:5174` and proxies `/api` to the backend.

## Checks

Run the most relevant checks before opening a pull request:

```bash
cd backend
source .venv/bin/activate
ruff check .
pytest
```

```bash
cd mobile_frontend
npm run build
```

## Pull Requests

Keep pull requests focused and small enough to review. Explain behavior changes, data model changes, and migration steps clearly.

Do not mix unrelated changes. For example, documentation cleanup, backend behavior changes, and mobile UI work should usually be separate pull requests.

## Privacy Rules

Never commit real customer data, chat logs, production task records, Feishu/OpenAI credentials, real user IDs, `open_id` values, production databases, or local `.env` files.

Use synthetic examples such as `Acme Corp`, `Example Customer`, `客户_A`, and `ou_example_user`.

If a change touches reminders, external message delivery, customer context, or time calculations, call that out explicitly in the pull request.
