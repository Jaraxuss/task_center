# Task Center Backend

本目录提供“本地轻量任务中心”的后端 MVP，技术栈为 **FastAPI + SQLite + SQLAlchemy**。

## 已实现范围
- 任务（Task）/ 提醒（Reminder）/ 事件日志（TaskEvent）三类核心模型
- REST API：
  - 健康检查
  - 任务 CRUD
  - 任务完成 / 延期 / 取消
  - 新增提醒
  - 今日 / 看板 / 历史查询
- 为后续 **22:00 晚间收口** 预留字段与接口占位：
  - `tasks.nightly_bucket`
  - `tasks.nightly_reviewed_at`
  - `task_events.event_type = nightly_reviewed`
  - `GET /api/nightly-review`

## 目录结构
```bash
backend/
├── README.md
├── db.py
├── main.py
├── models.py
├── requirements.txt
├── schemas.py
├── seed_demo.py
└── data/
    └── task_center.db   # 启动后自动生成
```

## 环境要求
- Python 3.11+

## 安装依赖
```bash
cd /home/velen/.openclaw/workspace/task_center/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 初始化数据库
SQLite 数据库默认位于：
- `backend/data/task_center.db`

首次启动应用时会自动建表；如果只想先初始化数据库，可直接执行：
```bash
source .venv/bin/activate
python -c "from main import init_db; init_db(); print('db initialized')"
```

## 启动开发服务
默认配置可直接这样启动：
```bash
source .venv/bin/activate
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

如果要把监听地址 / 允许跨域的前端地址做成可改配置，先导出环境变量（也可参考 `.env.example` 自己放进启动脚本）：
```bash
export TASK_CENTER_API_HOST=0.0.0.0
export TASK_CENTER_API_PORT=8000
export TASK_CENTER_CORS_ORIGINS=http://127.0.0.1:5173,http://localhost:5173
source .venv/bin/activate
uvicorn main:app --reload --host "$TASK_CENTER_API_HOST" --port "$TASK_CENTER_API_PORT"
```

如果前端改到 `192.168.31.169:5173`，把 CORS 一并改掉即可：
```bash
export TASK_CENTER_CORS_ORIGINS=http://192.168.31.169:5173,http://127.0.0.1:5173,http://localhost:5173
```

启动后可访问：
- API 文档：`http://127.0.0.1:8000/docs`
- 健康检查：`http://127.0.0.1:8000/api/health`

## Demo 数据（可选）
为了方便前端联调，可执行：
```bash
source .venv/bin/activate
python seed_demo.py
```

若数据库已有任务数据，脚本会跳过写入。

## API 概览

### 健康检查
- `GET /api/health`

### 任务
- `GET /api/tasks?date=today&status=&q=`
- `GET /api/tasks/{task_id}`
- `POST /api/tasks`
- `PATCH /api/tasks/{task_id}`
- `POST /api/tasks/{task_id}/complete`
- `POST /api/tasks/{task_id}/defer`
- `POST /api/tasks/{task_id}/cancel`
- `POST /api/tasks/{task_id}/reminders`

### 项目
- `GET /api/projects`
- `PATCH /api/projects/rename`

### 仪表盘 / 查询
- `GET /api/dashboard`
- `GET /api/dashboard/today`
- `GET /api/dashboard/board`
- `GET /api/dashboard/history?limit=50`
- `GET /api/history?date=YYYY-MM-DD&status=&q=`
- `GET /api/nightly-review`

## 核心模型说明

### Task
关键字段：
- `title`：任务标题
- `description`：详细描述
- `due_at`：任务时间
- `status`：`todo | doing | done | deferred | canceled`
- `project`：所属项目；当前直接存放在 `tasks.project` 中，项目改名也是批量更新该字段
- `tags`：标签（API 输出为数组，库内以 JSON 字符串存储）
- `source`：来源（如 `chat` / `web` / `system`）
- `completed_at` / `canceled_at` / `deferred_to`
- `nightly_bucket` / `nightly_reviewed_at`：为 22:00 晚间收口预留

### Reminder
- 一个任务可挂多个提醒
- 支持字段：`remind_at`、`channel`、`status`、`note`

### TaskEvent
- 记录任务创建、更新、状态变化、提醒新增、延期、完成、取消等历史动作
- `payload_json` 用于保留变更上下文，便于后续接聊天命令、定时任务、审计视图

## 示例请求

### 新建任务
```bash
curl -X POST http://127.0.0.1:8000/api/tasks \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "今晚整理日报",
    "description": "把销售日报发给团队",
    "due_at": "2026-03-19T13:30:00",
    "project": "销售",
    "tags": ["日报", "内部"],
    "source": "web",
    "reminders": [
      {
        "remind_at": "2026-03-19T12:50:00",
        "channel": "local",
        "note": "提前 40 分钟提醒"
      }
    ]
  }'
```

### 延期任务
```bash
curl -X POST http://127.0.0.1:8000/api/tasks/1/defer \
  -H 'Content-Type: application/json' \
  -d '{
    "deferred_to": "2026-03-20T09:30:00",
    "reason": "等待上游素材"
  }'
```

### 查看项目分组
```bash
curl http://127.0.0.1:8000/api/projects
```

### 项目改名
```bash
curl -X PATCH http://127.0.0.1:8000/api/projects/rename \
  -H 'Content-Type: application/json' \
  -d '{
    "old_name": "常熟伊斯格",
    "new_name": "常熟伊斯格-AI"
  }'
```

返回示例：
```json
{
  "old_name": "常熟伊斯格",
  "new_name": "常熟伊斯格-AI",
  "updated_task_count": 3,
  "project": {
    "name": "常熟伊斯格-AI",
    "task_count": 3,
    "open_task_count": 2,
    "done_task_count": 1
  }
}
```

## 后续建议
- 增加 Alembic 迁移，替代当前 MVP 的自动建表
- 接入定时器 / cron，驱动 reminder firing 与 nightly review
- 为前端增加更细的筛选项（项目、标签、是否逾期）
- 若进入多用户阶段，再引入 owner / permission 相关模型
