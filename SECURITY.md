# Security Policy

TaskCenter may be used with sensitive customer context, reminders, external messaging integrations, and audit logs. Treat all production data as confidential.

## Reporting a Vulnerability

Please report security issues privately through GitHub Security Advisories if available, or by contacting the repository maintainer directly.

Do not open a public issue with exploit details, credentials, private customer context, real user IDs, or production logs.

## Sensitive Data

Do not commit:

- Real customer data, meeting notes, chat logs, or task exports
- Feishu, OpenAI, database, or webhook credentials
- Real Feishu `open_id` values or other user identifiers
- Production SQLite databases, logs, backups, or `.env` files

Use `.env.example` as a template and keep local runtime data under ignored directories.

## Current Scope

TaskCenter is currently a local-first project and does not claim complete multi-user permission isolation. If you deploy it for a team, place it behind appropriate authentication, authorization, network controls, backups, and monitoring.
