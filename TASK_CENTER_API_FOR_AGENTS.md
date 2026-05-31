# Task Center API for Agents

给代理 / 脚本 / 自动化流程使用的 task_center 实操文档。

两件核心事：

> 1. 当用户提出提醒、待办、改时间、完成、取消等请求时，先把事实落进 task_center，再默认同步 OpenClaw cron。
> 2. 当用户提到客户跟进信息时，按 `task-center-customer-knowledge` Skill 写入客户事实、周期生成材料、审核后上传 NotebookLM。

> **2026-05-04 修订要点（务必先读）：**
>
> - `tasks` 新增 `source_type` 标签字段，用于标记任务来源（`forwarded_message` / `screenshot` / `meeting_note` / `user_chat` / `manual_input`）。
> - **转发消息 / 截图 / 会议纪要场景必须两步走**：先 `POST /api/tasks`（带 `source_type`），再 `POST /api/facts`（`task_id` 关联，`raw_markdown` 为原文，禁止 LLM 加工）。详见第 11 节。
> - **后端不派生 fact**：`POST /api/tasks/{id}/complete` 不再自动生成 fact，需要 fact 的场景必须显式 `POST /api/facts`。
> - **周期客户材料由 `scripts/customer_materials_weekly.py` 确定性脚本生成**，不再走 LLM / agentTurn；新流程材料**只写 `raw_facts_markdown`**。
> - 上传 NotebookLM 的 markdown **不再拼三段标题**，只保留 `# {customer}｜{project 或 客户级}｜{period}` + `raw_facts_markdown`。
>
> **2026-05-04 Phase 2 修订（继上条）：**
>
> - `customer_materials` 的 5 个旧/兼容字段 —— `raw_source_markdown` / `candidate_markdown` / `summary_markdown` / `insights_markdown` / `review_note` —— **已从后端物理删除**。agent / 脚本 / 调用方**不应再传**这些字段（目前 Pydantic 默认 `extra='ignore'`，多传会被静默忽略，不会 422）。
> - `customer_materials` 的唯一正文字段 = `raw_facts_markdown`。
> - `/api/customer-materials-v2` 端点族**已从代码中删除**，调用会返回 404。所有客户材料操作统一走 `/api/customer-materials`。
>
> **2026-05-06 Phase 3 修订（继上条）：**
>
> - `DELETE /api/facts/{id}` 改为**物理删除**（旧实现是把 status 标 `rejected`）。关联表 `customer_material_facts.fact_id` 已 `ON DELETE CASCADE`，无需手动清理。
> - `PATCH /api/facts/{id}` 现在被前端正式用来**改 customer 归属**：传 `customer_id: <int>` 切换、传 `clear_customer: true` 清空。schema 早已支持，本次只是补全前端入口。
> - 移动端任务详情页新增"客户事实"区块（数据来源：`GET /api/facts?task_id={taskId}`，已存在端点，无新增）。
>
> **2026-05-07 修订（按客户聚合查询补齐）：**
>
> - `GET /api/tasks` 新增 `customer_id` / `project_id` 两个筛选参数（FK 精确匹配），与 `/api/facts`、`/api/projects`、`/api/customer-materials` 已有的同名参数行为一致。例：`/api/tasks?customer_id=1`。
> - 至此，**任意一个客户视图所需的四类列表**（任务 / 事实 / 项目 / 客户材料）都可以用统一的 `?customer_id=<id>` 检索，agent / 前端不再需要先拉全量再客户端过滤。

---

## 1. 服务位置

后端项目根：`/home/velen/.openclaw/workspace/task_center/backend/`

| 模块 | 路径 | 职责 |
|---|---|---|
| 入口 | `backend/main.py` | 仅 FastAPI app / lifespan / CORS / 注册 routers，约 100 行；不含业务逻辑 |
| HTTP 路由 | `backend/routers/` | 按领域拆分：`tasks.py` / `dashboard.py` / `facts.py` / `customer_materials.py` / `customers.py` / `projects.py`（统一项目 CRUD，`/api/projects`；旧 `/api/projects-v2` 保留为兼容别名）/ `review_batches.py` / `preferences.py` / `health.py` |
| 业务逻辑 | `backend/services/` | 同名服务模块（`tasks.py` / `dashboard.py` / `customer_materials.py` …），路由只编排、领域规则在这里 |
| Pydantic schema | `backend/schemas.py` | 请求 / 响应模型（仍是单文件，后续可能拆分） |
| ORM | `backend/models.py` | SQLAlchemy 模型 |
| Alembic 迁移 | `backend/alembic/` | DB schema 版本管理 |

- 本地 API Base URL：`http://127.0.0.1:8000`
- 健康检查（仅调试 / 排障时使用）：`GET http://127.0.0.1:8000/api/health`
- 看一个端点的实现 = 先去 `backend/routers/<domain>.py`，再跳 `backend/services/<domain>.py`。

说明：
- 文档契约 `docs/API_CONTRACT.md` 可参考，但若与真实行为冲突，以 `backend/routers/*` + `backend/services/*` + `backend/schemas.py` 的实际代码为准。
- 当前后端实际返回的是**裸对象 / 裸数组**，不是统一 `{data, meta}` 包装。
- 日常提醒落账流程里，默认不先做 health 探测，直接调用业务接口。
- 当前 `customer-materials` 已采用新模型为主、旧字段兼容模式。文档、agent、cron、skill **只公开调用 `/api/customer-materials`**，不再使用 `/api/customer-materials-v2`。
- 即使你记得早先文档写过 `/api/customer-materials-v2`，也不要把当前调用改写成 `v2` 路径。

---

## 2. 时间规则

- 后端默认业务时区：`Asia/Shanghai`
- 请求里若传无时区时间，例如 `2026-04-22T21:30:00`，后端会按北京时间解释，再转 UTC 存储。
- 对中文聊天场景，通常可直接传北京时间字符串，无需手动写 `Z`。

---

## 3. 任务 / 提醒操作的默认顺序

### 3.1 创建提醒 / 待办

默认顺序：
1. `POST /api/tasks` 创建任务
2. 优先在创建任务时直接带上 `reminders`
3. 默认同步创建 OpenClaw cron

不要反过来先建 cron 再假定 task_center 已有。
也不要把“是否补 cron”当成临场判断分支；当前默认就是要补，因为 task_center 还没有主动通知能力。

### 3.2 改时间 / 延期

默认顺序：
1. 先更新 task_center
2. 再同步对应 cron

对应接口：
- 轻量改标题/描述/时间：`PATCH /api/tasks/{id}`
- 明确延期：`POST /api/tasks/{id}/defer`

### 3.3 完成 / 取消

对应接口：
- 完成：`POST /api/tasks/{id}/complete`
- 取消：`POST /api/tasks/{id}/cancel`

### 3.4 补提醒

若任务已存在但还没有提醒：
- `POST /api/tasks/{id}/reminders`

---

## 4. 最小必会接口

### 4.1 创建任务（推荐直接带 reminders）

```bash
curl -X POST http://127.0.0.1:8000/api/tasks \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "交付妮西雅 3 个增购账号",
    "description": "客户妮西雅提出为避免五一断档，希望今天或明天把时间调整好并推进交付。本次需重点跟进 3 个增购账号交付。",
    "due_at": "2026-04-22T21:30:00",
    "area": "customer",
    "customer_id": 5,
    "project_id": null,
    "tags": ["客户", "交付", "增购账号", "妮西雅"],
    "source": "chat",
    "source_type": "user_chat",
    "reminders": [
      {
        "remind_at": "2026-04-22T21:30:00",
        "channel": "chat",
        "note": "提醒交付妮西雅 3 个增购账号"
      }
    ]
  }'
```

> `source_type` 是任务来源**标签**（不是必填）。普通待办填 `user_chat` 或省略；当来源是用户转发 / 截图 / 会议纪要时**必须**填 `forwarded_message` / `screenshot` / `meeting_note` 并配套写 fact，详见第 11 节。

### 4.3 给已有任务补提醒

```bash
curl -X POST http://127.0.0.1:8000/api/tasks/87/reminders \
  -H 'Content-Type: application/json' \
  -d '{
    "remind_at": "2026-04-22T21:30:00",
    "channel": "chat",
    "note": "提醒交付妮茜雅 3 个增购账号"
  }'
```

### 4.4 更新任务基础字段

```bash
curl -X PATCH http://127.0.0.1:8000/api/tasks/87 \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "交付妮茜雅 3 个增购账号",
    "due_at": "2026-04-22T21:30:00",
    "tags": ["客户", "交付", "增购账号", "妮茜雅"]
  }'
```

### 4.5 延期任务

```bash
curl -X POST http://127.0.0.1:8000/api/tasks/87/defer \
  -H 'Content-Type: application/json' \
  -d '{
    "deferred_to": "2026-04-23T09:30:00",
    "reason": "等待对方确认账号交付时间"
  }'
```

### 4.6 完成任务

```bash
curl -X POST http://127.0.0.1:8000/api/tasks/87/complete \
  -H 'Content-Type: application/json' \
  -d '{
    "note": "已完成 3 个增购账号交付"
  }'
```

### 4.7 取消任务

```bash
curl -X POST http://127.0.0.1:8000/api/tasks/87/cancel \
  -H 'Content-Type: application/json' \
  -d '{
    "reason": "需求失效"
  }'
```

---

## 5. 推荐 Python 调用模板

```python
import json
import urllib.request

BASE = 'http://127.0.0.1:8000'

payload = {
    'title': '交付妮茜雅 3 个增购账号',
    'description': '客户妮茜雅提出为避免五一断档，希望今天或明天把时间调整好并推进交付。',
    'due_at': '2026-04-22T21:30:00',
    'area': 'customer',
    'customer_id': 5,
    'project_id': None,
    'tags': ['客户', '交付', '增购账号', '妮茜雅'],
    'source': 'chat',
    'source_type': 'user_chat',
    'reminders': [
        {
            'remind_at': '2026-04-22T21:30:00',
            'channel': 'chat',
            'note': '提醒交付妮茜雅 3 个增购账号',
        }
    ],
}

req = urllib.request.Request(
    f'{BASE}/api/tasks',
    data=json.dumps(payload, ensure_ascii=False).encode('utf-8'),
    headers={'Content-Type': 'application/json'},
    method='POST',
)

with urllib.request.urlopen(req, timeout=10) as resp:
    task = json.loads(resp.read().decode('utf-8'))
    print(task['id'])
```

---

## 6. 给代理的硬规则

1. 只要是提醒 / 待办类请求，默认直接调用 task_center API，不先做 health 探测。
2. 默认优先 `POST /api/tasks` 一次性创建任务 + reminders。
3. 创建或更新 task_center 后，默认同步创建或更新 OpenClaw cron；不要把“是否补 cron”当成分支判断。
4. 只有 task_center 写成功后，才允许说“已落账 task_center”。
5. 如果只建了 cron，必须明确说“已建 cron，未落 task_center”。
6. 改时间 / 延期 / 完成 / 取消时，先改 task_center，再同步 cron。
7. 若接口行为和文档描述冲突，以 `backend/main.py` 与 `backend/schemas.py` 为准。

---

## 7. 建议的提醒创建话术判定

### 可以说“已落账 task_center”
- `POST /api/tasks` 成功
- 或 `PATCH/POST defer/complete/cancel/reminders` 成功且目标任务真实存在

### 不能说“已落账 task_center”
- 只创建了 OpenClaw cron
- 只口头整理了任务文案
- 只看了 skill 规则，但没真的写 API

---

## 8. 与 OpenClaw cron 的职责划分

- `task_center`：任务主账本，记录任务事实、状态、时间、提醒、事件
- `cron`：提醒触发层，用于把提醒重新带回 OpenClaw 会话或指定 session

默认原则：

> task_center 负责“有没有这件事”；cron 负责“什么时候再叫你一次”。

---

## 9. 客户材料（NotebookLM 客户画像素材）

当task owner在待办 / 客户跟进语境中提到**跟进过程、跟进结果、客户反馈、聊天截图、会议结论、交付卡点**时，除了更新任务本身，还应把可沉淀内容写入客户材料。

当前规则：
- 客户材料的**唯一公开入口**是 `/api/customer-materials`。`/api/customer-materials-v2` 已在 2026-05-04 Phase 2 从代码中删除，调用会 404。
- 新模型主字段：`customer_id`、`project_v2_id`、`review_batch_id`、`material_type`、`period_start`、`period_end`、**`raw_facts_markdown`（唯一正文字段）**、`generation_meta`。
- 兼容字段：`project`、`title`、`material_date`、`source_type`、`source`、`source_refs`、`value_types`、`task_id`、`archived_at`、`status`。
- **已物理删除**的字段（传了也不会报错，但不会落地）：`raw_source_markdown`、`candidate_markdown`、`summary_markdown`、`insights_markdown`、`review_note`。

> 迁移提示：旧 `project` 仍保留兼容，但新流程优先通过 `customer_id` / `project_v2_id` / `review_batch_id` 定位客户材料。

### 9.1 创建客户材料

> 现实中移动端 / agent 基本不会手工 POST 新 material —— 周期材料由 `scripts/customer_materials_weekly.py` 在每周日 20:00 统一创建。下面示例仅作 schema 参考。

```bash
curl -X POST http://127.0.0.1:8000/api/customer-materials \
  -H 'Content-Type: application/json' \
  -d '{
    "customer_id": 1,
    "project_v2_id": null,
    "review_batch_id": 10,
    "title": "佰世赛｜客户级｜2026-05-01 ~ 2026-05-07 客户事实与总结",
    "material_type": "period_summary",
    "period_start": "2026-05-01T00:00:00",
    "period_end": "2026-05-07T23:59:59",
    "raw_facts_markdown": "完整事实记录（不删减）...",
    "status": "pending"
  }'
```

### 9.2 查询客户材料

```bash
# 按客户查询（推荐）
curl 'http://127.0.0.1:8000/api/customer-materials?customer_id=1'

# 按审核批次查询（推荐）
curl 'http://127.0.0.1:8000/api/customer-materials?review_batch_id=10'

# 按状态查询
curl 'http://127.0.0.1:8000/api/customer-materials?status=pending'

# 按旧项目标签兼容查询
curl 'http://127.0.0.1:8000/api/customer-materials?project=客户_A'

# 按任务关联查询（兼容）
curl 'http://127.0.0.1:8000/api/tasks/105/customer-materials'
```

### 9.3 更新 / 审核 / 归档

```bash
# 审核通过
curl -X PATCH http://127.0.0.1:8000/api/customer-materials/1 \
  -H 'Content-Type: application/json' \
  -d '{"status": "approved"}'

# 修改正文（task owner审核时改错别字 / 补遗漏）
curl -X PATCH http://127.0.0.1:8000/api/customer-materials/1 \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "佰世赛｜客户级｜2026-05-01 ~ 2026-05-07 客户事实与总结",
    "raw_facts_markdown": "task owner审核后微调过的事实原文..."
  }'

# 软归档，默认列表不再返回；如需看归档材料，加 include_archived=true
curl -X DELETE http://127.0.0.1:8000/api/customer-materials/1
```

### 9.4 字段规则

#### 新模型字段（主字段）
- `customer_id`：推荐，关联客户主键。
- `project_v2_id`：可选，关联新项目主键。
- `review_batch_id`：可选，关联审核批次；用于周期材料归集。
- `material_type`：可选，默认 `period_summary`；建议值：`period_summary` / `fact_bundle` / `meeting_note` / `project_digest`。
- `period_start` / `period_end`：可选，周期区间。
- `raw_facts_markdown`：**唯一正文字段**，完整事实层；不要删减客户原话、截图转写、不确定性标注。
- `generation_meta`：可选，JSON 对象，记录生成参数与过程元信息（脚本会写 `fact_count` / `generated_by` / `generated_at`）。

#### 兼容字段
- `project`：兼容，仍可查询，但不再作为新流程主定位字段。
- `material_date` / `source_type` / `source` / `source_refs` / `value_types` / `task_id` / `archived_at`：保留兼容，但不应作为新流程主字段。

#### 已物理删除的字段（2026-05-04 Phase 2）
- `raw_source_markdown` / `candidate_markdown` / `summary_markdown` / `insights_markdown` / `review_note`：列已从 DB drop，schema 不再暴露；POST / PATCH 传入会被 Pydantic 静默忽略，不产生任何副作用。

#### 常用状态
- `pending`：待审核
- `approved`：已确认
- `skipped`：已跳过
- `uploaded`：已上传

如果二者冲突，以 task_center 最新任务时间为准，并立即修正 cron。

### 9.5 标记已上传 / 材料关联 Facts

后续 agent/cron/skill 只允许调用 `/api/customer-materials/{id}/...`，不应再使用 `/api/customer-materials-v2`。

```bash
# 标记已上传
POST /api/customer-materials/{id}/mark-uploaded

# 添加材料关联 facts
POST /api/customer-materials/{id}/facts

curl -X POST http://127.0.0.1:8000/api/customer-materials/1/facts \
  -H 'Content-Type: application/json' \
  -d '{
    "fact_id": 42,
    "sort_order": 1
  }'

# 查询材料关联 facts
GET /api/customer-materials/{id}/facts

curl http://127.0.0.1:8000/api/customer-materials/1/facts
```

如果二者冲突，以 task_center 最新任务时间为准，并立即修正 cron。

---

## 10. 客户知识模块（customers / projects / facts / materials / batches）

### 10.1 概述

TaskCenter 新增了客户知识模块，支持从日常跟进中采集客户事实（facts），周期生成客户材料（customer_materials），审核后上传 NotebookLM。

**完整规则详见 Skill：** `skills/task-center-customer-knowledge/SKILL.md`

本节只补充 API 接口速查。若本节与 Skill 冲突，以 Skill 为准；若二者与后端代码冲突，以 `main.py` + `schemas.py` + `models.py` 为准。

### 10.2 不改的部分（重要）

- **不使用 feishu-task Skill**：当前不使用飞书任务机制，提醒靠 OpenClaw cron。
- **不修改 nblm Skill**：nblm 是第三方基础能力，只在上传链路调用其 `upload-text` 等命令。
- **不自动上传 NotebookLM**：必须等task owner审核确认后才上传。

### 10.3 Customers API

```bash
# 列表（支持 q、status 筛选）
GET /api/customers?q=佰&status=active

# 创建客户
POST /api/customers
# 若未传 area，默认生成 "客户_{name}"。
# 若未传 aliases，默认加入 area。
curl -X POST http://127.0.0.1:8000/api/customers \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "佰世赛",
    "key": "baishisai",
    "aliases": ["客户_A", "BSS"],
    "area": "客户_A",
    "tags": ["客户"]
  }'

# 详情
GET /api/customers/{id}

# 更新
PATCH /api/customers/{id}
curl -X PATCH http://127.0.0.1:8000/api/customers/1 \
  -H 'Content-Type: application/json' \
  -d '{"status": "paused", "description": "暂停跟进"}'
```

### 10.4 Projects API

项目 API 统一路径为 `/api/projects`（Phase 4.C 已完成命名统一）。旧路径 `/api/projects-v2` 仍可用作兼容别名，但**新代码 / Skill / 脚本应统一使用 `/api/projects`**。

```bash
# 列表（支持 customer_id、area、status、q）
GET /api/projects?customer_id=1&status=active

# 创建项目
POST /api/projects
# 若有 customer_id 且未传 area，后端继承 customer.area。
curl -X POST http://127.0.0.1:8000/api/projects \
  -H 'Content-Type: application/json' \
  -d '{
    "customer_id": 1,
    "project_type": "customer",
    "name": "处理 3 个账号增购合同流程",
    "tags": ["增购", "合同"]
  }'

# 详情
GET /api/projects/{id}

# 更新
PATCH /api/projects/{id}
curl -X PATCH http://127.0.0.1:8000/api/projects/1 \
  -H 'Content-Type: application/json' \
  -d '{"status": "done"}'
```

### 10.5 Facts API

事实（facts）是 NotebookLM 的主要原始内容来源。

**2026-05-04 修订后的写入规则（硬约定，详见 SKILL.md）：**

| 场景 | 任务 `source_type` | 是否写 fact | fact `status` | `raw_markdown` 要求 |
|---|---|---|---|---|
| 用户转发消息 / 会话记录 | `forwarded_message` | **必须**（两步走） | `confirmed` | 原文搬运，保留发言人/时间/原句，**禁止 LLM 加工** |
| 用户发截图 | `screenshot` | **必须**（两步走） | `confirmed` | 转写为多人对话原文 + 图片元素 `[此处为xx图片]` 描述 |
| 用户给会议纪要 | `meeting_note` | **必须**（两步走） | `confirmed` | 纪要原文 |
| 普通"提醒我做 X" | `user_chat` 或不填 | **不写** | — | — |
| 任务完成 (`POST /api/tasks/{id}/complete`) | 任意 | **不派生**（后端不做副作用） | — | 如完成结果有价值，让用户主动转发，再走转发场景 |

**两步走 = `POST /api/tasks` → 拿到 `task.id` → `POST /api/facts` 带 `task_id`**，两步必须配对。系统操作痕迹、提醒本身、无客户价值流水账一律不写 fact。

```bash
# 列表（支持 customer_id、project_id、task_id、status、source_type、from、to、q）
GET /api/facts?customer_id=1&status=draft&from=2026-05-01&to=2026-05-07

# 创建事实
POST /api/facts
curl -X POST http://127.0.0.1:8000/api/facts \
  -H 'Content-Type: application/json' \
  -d '{
    "customer_id": 1,
    "project_id": null,
    "task_id": null,
    "fact_date": "2026-05-03T14:30:00",
    "title": "佰世赛提出增购 5 个账号",
    "raw_markdown": "客户反馈：由于业务扩张，需要在月底前增购 5 个账号。",
    "source_type": "chat",
    "value_types": ["客户需求", "商机/增购/续费"],
    "status": "confirmed"
  }'

# 详情
GET /api/facts/{id}

# 更新（改状态/内容/归属）
PATCH /api/facts/{id}
curl -X PATCH http://127.0.0.1:8000/api/facts/1 \
  -H 'Content-Type: application/json' \
  -d '{"status": "confirmed", "raw_markdown": "更新后内容"}'

# 删除（物理删除，不可恢复；移动端"删除"按钮直接走这里）
# 关联表 customer_material_facts.fact_id 已 ON DELETE CASCADE，无需手动清理
DELETE /api/facts/{id}
# → 204 No Content
```

**source_type 可选值：** `chat` / `screenshot_ocr` / `task_completion` / `meeting_note` / `manual_input` / `forwarded_message` / `document`

**value_types 建议值：** 客户需求、业务流程、系统限制、关键人信息、客户偏好、风险/阻塞、解决方案、商机/增购/续费、售后问题、交付结果、可复用方法论

### 10.6 Customer Materials API（唯一公开入口）

公开契约：只调用 `/api/customer-materials`；`/api/customer-materials-v2` 已从文档中移除，不应再出现在 agent/cron/skill 调用中。

#### 字段说明

**新模型字段（主字段）**
- `customer_id`（推荐）
- `project_v2_id`（可选）
- `review_batch_id`（可选）
- `title`（必填）
- `material_type`（可选，默认 `period_summary`）
- `period_start` / `period_end`（可选）
- `raw_facts_markdown`（**唯一正文字段**）
- `generation_meta`（可选 JSON 对象）
- `status`（可选）

**兼容字段（不作为新流程主字段）**
- `project`
- `material_date`
- `source_type`
- `source`
- `source_refs`
- `value_types`
- `task_id`
- `archived_at`

**已物理删除字段（2026-05-04 Phase 2，POST/PATCH 中传入会被静默忽略）**
- `raw_source_markdown` / `candidate_markdown` / `summary_markdown` / `insights_markdown` / `review_note`

#### 最小调用示例

```bash
# 列表（推荐新字段筛选）
GET /api/customer-materials?customer_id=1&review_batch_id=10&status=pending&material_type=period_summary

# 创建材料（通常由 scripts/customer_materials_weekly.py 自动写入，手工调用仅用于调试）
POST /api/customer-materials
curl -X POST http://127.0.0.1:8000/api/customer-materials \
  -H 'Content-Type: application/json' \
  -d '{
    "customer_id": 1,
    "project_v2_id": null,
    "review_batch_id": 1,
    "title": "佰世赛｜客户级",
    "material_type": "period_summary",
    "period_start": "2026-05-01T00:00:00",
    "period_end": "2026-05-07T23:59:59",
    "raw_facts_markdown": "完整事实记录（不删减）...",
    "status": "pending"
  }'

# 详情
GET /api/customer-materials/{id}

# 审核/更新（新流程只动 raw_facts_markdown / status / title）
PATCH /api/customer-materials/{id}
curl -X PATCH http://127.0.0.1:8000/api/customer-materials/1 \
  -H 'Content-Type: application/json' \
  -d '{
    "status": "approved",
    "raw_facts_markdown": "task owner审核后微调过的事实原文..."
  }'

# 标记已上传（上传 NotebookLM 成功后调用）
POST /api/customer-materials/{id}/mark-uploaded

# 添加材料关联 facts
POST /api/customer-materials/{id}/facts
curl -X POST http://127.0.0.1:8000/api/customer-materials/1/facts \
  -H 'Content-Type: application/json' \
  -d '{
    "fact_id": 42,
    "sort_order": 1
  }'

# 查询材料关联 facts
GET /api/customer-materials/{id}/facts
curl http://127.0.0.1:8000/api/customer-materials/1/facts
```

#### 状态与类型

- `material_type` 可选值：`period_summary` / `fact_bundle` / `meeting_note` / `project_digest`
- `status` 流转：`pending` → `approved` → `uploaded`（或 `skipped`）

#### 旧参数迁移提示

| 旧筛选参数 | 当前状态 | 推荐迁移 |
|---|---|---|
| `project` | 仍支持 | 优先 `customer_id` / `project_v2_id` / `review_batch_id` |
| `task_id` | 仍支持 | 新流程不再作为主字段 |
| `value_type` | 仍支持 | 仅用于旧材料筛选 |
| `q` / `status` / `include_archived` / `limit` | 仍支持 | 继续使用 |

> 当前 `POST /api/customer-materials/{id}/mark-uploaded`、`POST /api/customer-materials/{id}/facts`、`GET /api/customer-materials/{id}/facts` 已统一到 `/api/customer-materials/{id}/...` 路径。agent 不应再使用 `/api/customer-materials-v2`。

### 10.7 Review Batches API

```bash
# 列表
GET /api/review-batches
curl http://127.0.0.1:8000/api/review-batches

# 创建批次
POST /api/review-batches
curl -X POST http://127.0.0.1:8000/api/review-batches \
  -H 'Content-Type: application/json' \
  -d '{
    "batch_type": "weekly_customer_summary",
    "title": "2026-05-03 客户周期材料",
    "period_start": "2026-05-01T00:00:00",
    "period_end": "2026-05-07T23:59:59",
    "material_count": 3,
    "created_by": "cron"
  }'

# 详情
GET /api/review-batches/{id}
curl http://127.0.0.1:8000/api/review-batches/1

# 查看批次下的材料（统一返回 CustomerMaterial）
GET /api/review-batches/{id}/customer-materials
curl http://127.0.0.1:8000/api/review-batches/1/customer-materials

# 等价查询方式
GET /api/customer-materials?review_batch_id=1
curl 'http://127.0.0.1:8000/api/customer-materials?review_batch_id=1'

# 更新批次状态
PATCH /api/review-batches/{id}
curl -X PATCH http://127.0.0.1:8000/api/review-batches/1 \
  -H 'Content-Type: application/json' \
  -d '{"status": "approved"}'
```

**batch_type 可选值：** `weekly_customer_summary` / `daily_customer_summary` / `manual_generation`

> 当前 `/api/review-batches/{id}/customer-materials` 已统一返回 `CustomerMaterialRead` schema，避免 agent 需要同时理解两套返回结构。

### 10.8 Tasks 新增字段

`tasks` 表字段（Phase 4.A/4.C 已完成数据模型收尾）：

| 字段 | 类型 | 说明 |
|---|---|---|
| `area` | string(128) nullable | 任务大类轴：`customer` / `internal` / `personal` / 空 |
| `customer_id` | integer FK nullable | 关联客户 |
| `project_id` | integer FK nullable | 关联项目（`projects` 表） |
| `source_type` | string(32) nullable | **2026-05-04 新增**。任务来源标签，仅作分类，不存原文。推荐枚举：`forwarded_message` / `screenshot` / `meeting_note` / `user_chat` / `manual_input`。后端不做硬枚举校验，可扩展。 |

> **2026-05-11 Phase 4.A.5 修订**：`tasks.project` 字符串列已从数据库物理删除。创建/更新任务时不再传 `project` 字段，应传 `project_id`。后端返回的 `TaskRead.project` 是从 `project_id` JOIN 派生的 `Project.name`，仅供显示。

**`GET /api/tasks` 筛选参数：**

| 参数 | 类型 | 说明 | 引入 |
|---|---|---|---|
| `status` | string | 任务状态精确匹配（`todo` / `doing` / `deferred` / `done` / `canceled`） | 一直存在 |
| `q` | string | 标题 / 描述 / 项目名称 ILIKE 模糊 | 一直存在 |
| `date` | string | 仅支持 `today`，按本地日界裁剪 `due_at` | 一直存在 |
| `source_type` | string | 按来源标签精确匹配 | 2026-05-04 |
| `from` | datetime ISO8601 | `created_at >= from`（含），北京时间字符串可直传 | 2026-05-04 |
| `to` | datetime ISO8601 | `created_at < to`（不含） | 2026-05-04 |
| `customer_id` | int | 按客户 FK 精确匹配（`tasks.customer_id`） | 2026-05-07 |
| `project_id` | int | 按项目 FK 精确匹配（`tasks.project_id`，对应 `projects` 表） | 2026-05-07 |

```bash
# 列出本周转发类任务，做一致性检查
curl 'http://127.0.0.1:8000/api/tasks?source_type=forwarded_message&from=2026-05-01T00:00:00&to=2026-05-08T00:00:00&limit=500'

# 客户 1 的全部任务
curl 'http://127.0.0.1:8000/api/tasks?customer_id=1'

# 客户 1 + 状态 doing
curl 'http://127.0.0.1:8000/api/tasks?customer_id=1&status=doing'
```

### 10.9 上传 NotebookLM 的拼接模板（2026-05-04 修订）

审核通过后，上传到 NotebookLM 的 Markdown **只保留单段事实层**：

```markdown
# {customer.name}｜{project.name 或 "客户级"}｜{period_start} ~ {period_end}

{raw_facts_markdown}
```

规则：

- **不再拼三段标题**（"完整事实记录 / 简要纪要 / 洞察建议"）。摘要 / 洞察由 NotebookLM 自带能力在上传后生成，不在 cron 时点重复劳动。
- 上传时使用 nblm 的 `upload-text` 命令，靠客户名匹配已有 Notebook。
- 上传成功后必须 `POST /api/customer-materials/{id}/mark-uploaded`，把 status 推到 `uploaded`。

### 10.10 审核回复约定

task owner在飞书审核通过后，回复格式为：

- `审核完成 #A #B #C`：上传指定 id 的 material（仅 `status=approved` 的会被上传）。
- `审核完成 batch #N`：上传 batch #N 下所有 `status=approved` 的 material。

主代理处理流程：

1. 按 id / batch_id 读 material；
2. 过滤 `status='approved'`，非 approved 的跳过并简短报告跳过原因（`pending` / `skipped` / 已 `uploaded`）；
3. 按 10.9 模板拼 markdown；
4. 调 nblm Skill 按客户名匹配 Notebook 上传；
5. 上传成功后 `POST /api/customer-materials/{id}/mark-uploaded`；
6. 整批完成后回报每份 material 上传成败。

### 10.11 周期 cron 与脚本

- **新链路 cron**：每周日 20:00 北京时间触发，执行 `python3 /home/velen/.openclaw/workspace/scripts/customer_materials_weekly.py`（type=shell，**不走 agentTurn / LLM**）。cron 配置由 OpenClaw 侧维护，不在 TaskCenter 仓库中。
- **脚本职责**：拉本周 `confirmed` facts → 按 `customer_id + project_id` 分组 → 创建 `review_batch` → 为每组创建 `customer_material`（仅写 `raw_facts_markdown`）→ 建立 `customer_material_facts` 关联 → 一致性检查（扫本周 `source_type ∈ {forwarded_message, screenshot, meeting_note}` 但无关联 fact 的 task）→ stdout 输出 JSON。
- **脚本输出格式**：

```json
{
  "status": "ok",
  "batch_id": 123,
  "period": ["2026-04-27T00:00:00+08:00", "2026-05-04T00:00:00+08:00"],
  "materials": [
    {"id": 45, "customer": "佰世赛", "project": null, "fact_count": 3}
  ],
  "warnings": [
    {"task_id": 87, "title": "...", "source_type": "screenshot", "reason": "missing_fact"}
  ]
}
```

无 fact 时输出 `{"status":"ok","message":"no_facts_this_week","period":[...],"warnings":[...]}`，不创建 batch。

主代理消费此 JSON，转人类可读消息发到飞书，让task owner到 TaskCenter 移动端审核。**不发全文**，只发 batch_id + material id/客户/项目 + warning 列表。

---

## 11. 转发 / 截图 / 会议纪要场景：两步走（硬约定）

> 本节是 2026-05-04 修订的核心。主代理在以下三类场景中**必须**按 Step 1 → Step 2 配对调用，缺一不可。完整规则详见 `skills/task-center-customer-knowledge/SKILL.md`，本节只给可执行示例。

### 11.1 触发条件

| 场景 | 任务 `source_type` | fact `source_type` |
|---|---|---|
| 用户转发飞书消息 / 会话记录 | `forwarded_message` | `forwarded_message` |
| 用户发截图 | `screenshot` | `screenshot_ocr`（建议）或 `screenshot` |
| 用户给会议纪要 | `meeting_note` | `meeting_note` |

### 11.2 Step 1：创建任务（带 `source_type`）

```bash
curl -X POST http://127.0.0.1:8000/api/tasks \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "佰世赛反馈增购 5 个账号需求，月底前推进合同",
    "description": "客户在群里发来增购意向，需要本周内出合同方案。",
    "due_at": "2026-05-08T18:00:00",
    "customer_id": 1,
    "project_id": null,
    "tags": ["客户", "增购", "佰世赛"],
    "source": "chat",
    "source_type": "forwarded_message"
  }'
# 响应里拿到 task.id（例如 142）
```

### 11.3 Step 2：写入原文 fact（`task_id` 关联）

```bash
curl -X POST http://127.0.0.1:8000/api/facts \
  -H 'Content-Type: application/json' \
  -d '{
    "customer_id": 1,
    "project_id": null,
    "task_id": 142,
    "fact_date": "2026-05-04T10:30:00",
    "title": "佰世赛提出增购 5 个账号",
    "raw_markdown": "[原始转发内容，保留所有发言人/时间/原话，不删减、不加工]",
    "source_type": "forwarded_message",
    "value_types": ["客户需求", "商机/增购/续费"],
    "status": "confirmed"
  }'
```

### 11.4 自审清单（每次执行后输出）

主代理执行完两步后，在回复里附带一行自审：

```
已写入：task #142 (source_type=forwarded_message), fact #87 (status=confirmed, raw_markdown 长度 N 字符)
```

### 11.5 禁止事项

- **不允许**用 LLM 加工 / 总结 / 改写 `raw_markdown`，必须搬运用户原文。
- **不允许**只建 task 不建 fact（脚本一致性检查会在每周 warning 中暴露）。
- **不允许**把 fact 内容塞进 `task.description` 后省略 Step 2。
- **不允许**调用 `POST /api/tasks/{id}/complete` 派生 fact——后端不会派生，主代理也不应代写。
- **不允许**对普通 `user_chat` 提醒任务（如"晚上 9 点提醒我做 X"）写 fact。
