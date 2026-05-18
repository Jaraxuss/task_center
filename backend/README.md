# Task Center Backend

本目录提供“本地轻量任务中心”的后端 MVP，技术栈为 **FastAPI + SQLite + SQLAlchemy**。

## 已实现范围
- 任务（Task）/ 提醒（Reminder）/ 事件日志（TaskEvent）三类核心模型
- 新增 **TaskRecurrence**：任务级周期规则（daily / weekly / monthly）
- REST API：
  - 健康检查
  - 任务 CRUD
  - 任务完成 / 延期 / 取消
  - 新增提醒
  - 今日 / 看板 / 历史查询
  - 通过 `POST /api/tasks` 与 `PATCH /api/tasks/{id}` 创建 / 更新周期配置
- 为后续 **22:00 晚间收口** 预留字段与接口占位：
  - `tasks.nightly_bucket`
  - `tasks.nightly_reviewed_at`
  - `task_events.event_type = nightly_reviewed`
  - `GET /api/nightly-review`
- 新增 **飞书卡片 SDK**：TaskCenter 可直接通过飞书开放平台发送 Card JSON 1.0 / 2.0 卡片与文本提醒，详见 `scripts/sdk/README.md`、`../docs/FEISHU_CARD_V1_SDK.md`、`../docs/FEISHU_CARD_V2_SDK.md`

## 目录结构
```bash
backend/
├── README.md
├── db.py
├── main.py
├── models.py
├── recurrence.py
├── requirements.txt
├── schemas/
├── services/
│   └── feishu_card/  # 飞书卡片 V2 兼容 import 层
├── scripts/
│   ├── send_feishu_card.py  # V2 smoke 兼容入口
│   └── sdk/
│       ├── feishu-card-v1/  # 飞书 Card JSON 1.0 SDK
│       └── feishu-card-v2/  # 飞书 Card JSON 2.0 SDK
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

如果要启用 TaskCenter 飞书卡片 SDK，配置：

```bash
export TASK_CENTER_FEISHU_APP_ID=cli_xxx
export TASK_CENTER_FEISHU_APP_SECRET=xxx
export TASK_CENTER_FEISHU_DEFAULT_RECEIVE_ID=ou_xxx
export TASK_CENTER_FEISHU_DEFAULT_RECEIVE_ID_TYPE=open_id
```

可用 smoke 脚本先做 dry-run：

```bash
source .venv/bin/activate
python scripts/sdk/feishu-card-v2/send_card_v2.py --text "提醒：测试" --dry-run
python scripts/sdk/feishu-card-v1/send_card_v1.py --text "提醒：测试" --dry-run
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

## 时区约定（重要）
- **数据库统一存 UTC aware 时间**，格式示例：`2026-04-08T01:30:00Z`
- **API 统一返回 ISO 8601 UTC** 时间字符串
- **前端展示与按日分组统一按 `Asia/Shanghai`**
- 详细设计说明见：`../docs/TIMEZONE_DESIGN.md`

## 核心模型说明

### Task
关键字段：
- `title`：任务标题
- `description`：详细描述
- `due_at`：当前这一次要执行的时间（对周期任务来说，表示“下一次发生时间”）
- `status`：`todo | doing | done | deferred | canceled`
- `project`：所属项目；当前直接存放在 `tasks.project` 中，项目改名也是批量更新该字段
- `tags`：标签（API 输出为数组，库内以 JSON 字符串存储）
- `source`：来源（如 `chat` / `web` / `system`）
- `completed_at` / `canceled_at` / `deferred_to`
- `nightly_bucket` / `nightly_reviewed_at`：为 22:00 晚间收口预留

### Reminder
- 一个任务可挂多个提醒
- 支持字段：`remind_at`、`channel`、`status`、`note`
- 当前仍是“一次性 reminder 记录”；周期规则本身由 `TaskRecurrence` 保存

### TaskRecurrence
最小可用的周期配置表，按 **1 个任务对应 0 或 1 条周期规则** 设计：
- `task_id`：唯一外键，指向 `tasks.id`
- `enabled`：是否启用
- `frequency`：`daily | weekly | monthly`
- `interval`：步长，例如每 2 周 / 每 3 月
- `timezone`：重复规则的业务时区；当前默认按 `Asia/Shanghai` 解释用户输入，并统一换算后以 UTC aware 时间存储
- `time_of_day`：规则执行时间，例如 `10:30:00`
- `days_of_week_json`：周规则使用，ISO weekday（1=周一 ... 7=周日）
- `day_of_month`：月规则使用，例如 25
- `start_at` / `end_at`：规则生效起止
- `next_run_at`：后端预计算出的下一次触发时间
- `last_run_at`：最近一次完成后推进的时间
- `reminder_offsets_json`：预留给后续调度器使用，例如 `[30, 1440]` 表示提前 30 分钟和 1 天提醒

#### “每月 25 号 10:30” 的表示方式
```json
{
  "recurrence": {
    "enabled": true,
    "frequency": "monthly",
    "interval": 1,
    "timezone": "Asia/Shanghai",
    "day_of_month": 25,
    "time_of_day": "10:30:00",
    "days_of_week": [],
    "start_at": "2026-03-25T02:30:00Z",
    "end_at": null,
    "reminder_offsets_minutes": [30]
  }
}
```

### TaskEvent
- 记录任务创建、更新、状态变化、提醒新增、延期、完成、取消、周期配置更新、周期推进等历史动作
- `payload_json` 用于保留变更上下文，便于后续接聊天命令、定时任务、审计视图

## 周期任务行为（当前实现）
- 创建任务时可直接附带 `recurrence`
- 查询任务详情 / 列表时会返回 `recurrence`
- 更新任务时可：
  - 直接传新的 `recurrence` 进行覆盖/upsert
  - 传 `"clear_recurrence": true` 删除周期规则
- 周期任务执行 `POST /api/tasks/{id}/complete` 时：
  - 会记录一次 `completed` 事件
  - 如果周期规则仍有效，则自动计算下一次 `next_run_at`
  - `task.due_at` 会推进到下一次发生时间
  - 任务状态会回到 `todo`，继续留在任务池中
  - 如果已经没有下一次发生时间（比如超过 `end_at`），则落为普通 `done`

## 示例请求

### 新建普通任务
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

### 新建“每月 25 号 10:30”周期任务
```bash
curl -X POST http://127.0.0.1:8000/api/tasks \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "提交月报",
    "project": "财务",
    "source": "web",
    "recurrence": {
      "enabled": true,
      "frequency": "monthly",
      "interval": 1,
      "timezone": "Asia/Shanghai",
      "day_of_month": 25,
      "time_of_day": "10:30",
      "start_at": "2026-03-25T02:30:00Z",
      "reminder_offsets_minutes": [30]
    }
  }'
```

### 更新周期规则
```bash
curl -X PATCH http://127.0.0.1:8000/api/tasks/1 \
  -H 'Content-Type: application/json' \
  -d '{
    "recurrence": {
      "enabled": true,
      "frequency": "weekly",
      "interval": 1,
      "timezone": "Asia/Shanghai",
      "days_of_week": [1, 3, 5],
      "time_of_day": "09:00",
      "start_at": "2026-03-27T01:00:00Z"
    }
  }'
```

### 删除周期规则
```bash
curl -X PATCH http://127.0.0.1:8000/api/tasks/1 \
  -H 'Content-Type: application/json' \
  -d '{
    "clear_recurrence": true
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

## 后续建议 / 还没做的部分
- 接入真正的 scheduler / cron，驱动 reminder firing 与周期任务自动提醒
- 现在的 `reminder_offsets_minutes` 还只是规则字段，尚未自动展开成下一批 Reminder 记录
- 若要保留每次周期实例的独立完成历史，后续可以再引入 occurrence / run 表
- 若进入多用户阶段，再引入 owner / permission 相关模型
- 若项目继续发展，建议补 Alembic 迁移，替代当前 MVP 的自动建表
