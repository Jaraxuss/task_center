# TaskCenter

[English](README.md)

TaskCenter 是一个面向 AI Agent 的上下文任务与提醒后端，用来把客户沟通、会议纪要和后续跟进意图转化为结构化、可审计、带上下文的任务。

它不是普通 todo list。TaskCenter 关注的是提醒真正到点时，人或 Agent 不只需要知道“现在要做什么”，还需要知道“为什么要做、之前发生了什么、下一步该怎么处理”。

## 为什么需要 TaskCenter

传统提醒擅长告诉你“现在做这件事”，但很难保留任务背后的上下文：会议纪要、客户承诺、历史决策、交付卡点、跟进负责人等。

TaskCenter 把任务、提醒、事件记录和客户上下文连接在一起，让 AI Agent 和人可以更安全地协作。它适合客户跟进、会议纪要转 action、晚间收口、周期提醒，以及 human-in-the-loop 的任务处理流程。

## 它能做什么

- 通过 Agent 友好的 REST API 创建、更新、完成、延期和取消任务
- 存储提醒、周期规则、任务事件和客户上下文
- 为任务状态变化和提醒操作保留可审计事件日志
- 支持带上下文的客户跟进工作流
- 提供轻量移动端前端，用于查看任务和快速处理
- 默认按 UTC 存储时间，并按 `Asia/Shanghai` 语义展示和按日分组
- 可选通过 Feishu 集成发送提醒卡片，公开仓库中只保留合成示例

## 架构

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

后端是任务状态、时间语义、周期规则、提醒和事件历史的事实来源。移动端前端是独立 Git submodule，专注于轻量查看和任务处理。

## 仓库结构

```text
backend/           FastAPI, SQLite, SQLAlchemy, reminders, recurrence, events
mobile_frontend/   React, TypeScript, Vite mobile UI (Git submodule)
docs/              Product notes, API contract, timezone design, SDK docs
archive/frontend/  Archived desktop frontend, kept for historical reference
```

## 快速开始

克隆仓库并拉取移动端子模块：

```bash
git clone --recurse-submodules https://github.com/Jaraxuss/task_center.git
cd task_center
```

如果已经克隆但没有初始化子模块：

```bash
git submodule update --init --recursive
```

启动后端：

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

启动移动端：

```bash
cd ../mobile_frontend
cp .env.example .env.local
npm install
npm run dev
```

访问：

```text
http://localhost:5174
```

后端 API 文档：

```text
http://127.0.0.1:8000/docs
```

## 开发

后端检查：

```bash
cd backend
source .venv/bin/activate
pip install -r requirements-dev.txt
ruff check .
pytest
```

移动端构建：

```bash
cd mobile_frontend
npm run build
```

## 文档导航

- `docs/PROJECT_OVERVIEW.md`：当前系统地图，推荐作为接手入口
- `docs/PRD.md`：产品目标、范围和工作流假设
- `docs/API_CONTRACT.md`：API 与字段约定
- `docs/TIMEZONE_DESIGN.md`：日期、提醒、周期任务和按日分组的时间语义
- `TASK_CENTER_API_FOR_AGENTS.md`：面向 Agent 的 API 使用指南
- `backend/README.md`：后端启动、API 概览和运行说明
- `mobile_frontend/README.md`：移动端启动方式和交互模型
- `backend/scripts/sdk/README.md`：Feishu 卡片辅助脚本
- `docs/FEISHU_CARD_V1_SDK.md`：Feishu Card JSON 1.0 说明
- `docs/FEISHU_CARD_V2_SDK.md`：Feishu Card JSON 2.0 说明

## 隐私与安全

TaskCenter 适用于可能包含敏感客户上下文的工作流。公开仓库中只包含合成示例。

请不要提交真实客户数据、聊天记录、Feishu/OpenAI 凭证、用户 ID、真实 `open_id`、生产数据库、日志、备份或本地 `.env` 文件。

请使用 `.env.example` 作为模板，并把本地运行数据保存在已忽略目录中，例如 `backend/data/` 和 `backend/logs/`。

## 数据模型亮点

TaskCenter 围绕几个稳定概念组织：

- `Task`：行动项、状态、面向负责人展示的文本、到期时间和项目/客户关联
- `Reminder`：计划提醒时间、投递元数据和可选外部消息目标
- `TaskEvent`：任务状态变化和提醒更新的可审计历史
- `TaskRecurrence`：周期任务规则和下一次运行时间计算
- Customer context：帮助 Agent 保留跟进记忆的事实和材料

项目使用 UTC-aware 时间存储，并通过 API 返回 ISO 8601 UTC 字符串。UI 分组和展示默认使用 `Asia/Shanghai` 语义。

## 路线图

- 保持后端 API 对 Agent 驱动的任务创建和更新稳定
- 改进提醒投递的可靠性和可观测性
- 扩展带上下文的客户跟进工作流
- 改进移动端任务编辑和审核交互
- 增加轻量 CI 和公开贡献流程
- 保持示例合成化，确保适合开源审阅

## License

MIT。详见 `LICENSE`。
