# Task Center API for Agents

给代理 / 脚本 / 自动化流程使用的 task_center 实操文档。

两件核心事：

> 1. 当用户提出提醒、待办、改时间、完成、取消等请求时，先把事实落进 task_center，再默认同步 OpenClaw cron。
> 2. 当用户提到客户跟进信息时，按 `task-center-customer-knowledge` Skill 写入客户事实、周期生成材料、审核后上传 NotebookLM。

---

## 1. 服务位置

- 后端代码：`/home/velen/.openclaw/workspace/task_center/backend/main.py`
- Schema 定义：`/home/velen/.openclaw/workspace/task_center/backend/schemas.py`
- 本地 API Base URL：`http://127.0.0.1:8000`
- 健康检查（仅调试 / 排障时使用）：`GET http://127.0.0.1:8000/api/health`

说明：
- 文档契约 `docs/API_CONTRACT.md` 可参考，但若与真实行为冲突，以 `backend/main.py` + `backend/schemas.py` 为准。
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
    "title": "交付妮茜雅 3 个增购账号",
    "description": "客户妮茜雅提出为避免五一断档，希望今天或明天把时间调整好并推进交付。本次需重点跟进 3 个增购账号交付。",
    "due_at": "2026-04-22T21:30:00",
    "project": "客户_无锡妮茜雅",
    "tags": ["客户", "交付", "增购账号", "妮茜雅"],
    "source": "chat",
    "reminders": [
      {
        "remind_at": "2026-04-22T21:30:00",
        "channel": "chat",
        "note": "提醒交付妮茜雅 3 个增购账号"
      }
    ]
  }'
```

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
    'project': '客户_无锡妮茜雅',
    'tags': ['客户', '交付', '增购账号', '妮茜雅'],
    'source': 'chat',
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

当南哥在待办 / 客户跟进语境中提到**跟进过程、跟进结果、客户反馈、聊天截图、会议结论、交付卡点**时，除了更新任务本身，还应把可沉淀内容写入客户材料。

当前规则：
- 客户材料的**唯一公开入口**是 `/api/customer-materials`。
- `/api/customer-materials-v2` 已在契约层面废弃；文档、agent、cron、skill 不应再引用该路径，短期兼容别名也必须在文档之外维护。
- 新模型字段（`customer_id`、`project_v2_id`、`review_batch_id`、`material_type`、`period_start`、`period_end`、`raw_facts_markdown`、`summary_markdown`、`insights_markdown`、`generation_meta`）为主字段。
- 旧字段（`project`、`source_type`、`candidate_markdown`、`review_note`、`task_id`、`archived_at`）保留兼容，但不再作为新流程主字段。
- 文档中所有示例都使用 `/api/customer-materials`；旧 `/api/customer-materials-v2` 仅保留在实现说明与迁移备注中，不作为调用示例。

> 迁移提示：旧 `project` 仍保留兼容，但新流程优先通过 `customer_id` / `project_v2_id` / `review_batch_id` 定位客户材料。

### 9.1 创建客户材料

#### 9.1.1 新模型（推荐）

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
    "summary_markdown": "简要纪要...",
    "insights_markdown": "洞察 / 风险 / 下一步建议（AI 推导层）...",
    "status": "pending"
  }'
```

#### 9.1.2 旧模型（兼容，非推荐）

```bash
curl -X POST http://127.0.0.1:8000/api/customer-materials \
  -H 'Content-Type: application/json' \
  -d '{
    "project": "客户_苏中药业",
    "title": "淘宝黄葵胶囊价格监控风控问题",
    "material_date": "2026-04-27T20:30:00",
    "source_type": "task_completion",
    "source": "chat",
    "source_refs": {"message_id": "om_xxx", "task_id": 105},
    "raw_source_markdown": "完整原始材料，尽量保留南哥原话、客户对话、截图 OCR/转写和不确定性标注。",
    "candidate_markdown": "轻度清洗后的 NotebookLM 候选入库 Markdown。",
    "value_types": ["客户需求", "系统限制", "风险/阻塞", "解决方案"],
    "task_id": 105
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
curl 'http://127.0.0.1:8000/api/customer-materials?project=客户_苏中药业'

# 按任务关联查询（兼容）
curl 'http://127.0.0.1:8000/api/tasks/105/customer-materials'
```

### 9.3 更新 / 审核 / 归档

```bash
# 审核通过
curl -X PATCH http://127.0.0.1:8000/api/customer-materials/1 \
  -H 'Content-Type: application/json' \
  -d '{"status": "approved"}'

# 更新新模型主字段
curl -X PATCH http://127.0.0.1:8000/api/customer-materials/1 \
  -H 'Content-Type: application/json' \
  -d '{
    "title": "佰世赛｜客户级｜2026-05-01 ~ 2026-05-07 客户事实与总结",
    "summary_markdown": "更新后的纪要",
    "insights_markdown": "更新后的洞察"
  }'

# 兼容旧字段修改（非新流程推荐）
curl -X PATCH http://127.0.0.1:8000/api/customer-materials/1 \
  -H 'Content-Type: application/json' \
  -d '{"status": "approved", "review_note": "已确认可入库"}'

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
- `raw_facts_markdown`：推荐，完整事实层；不要删减客户原话、截图转写、不确定性标注。
- `summary_markdown`：推荐，简要纪要层。
- `insights_markdown`：推荐，AI 推导层；上传 NotebookLM 时需显式标注为"洞察 / 风险 / 下一步建议"。
- `generation_meta`：可选，JSON 对象，记录生成参数与过程元信息。

#### 旧字段（兼容层）
- `project`：兼容，仍可查询，但不再作为新流程主定位字段。
- `material_date` / `source_type` / `source_refs` / `candidate_markdown` / `value_types` / `review_note` / `task_id` / `archived_at`：保留兼容，但不应作为新流程主字段。

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
- **不自动上传 NotebookLM**：必须等南哥审核确认后才上传。

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
    "aliases": ["客户_佰世赛", "BSS"],
    "area": "客户_佰世赛",
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

注意：新项目 API 路径为 `/api/projects-v2`，区别于旧的 `/api/projects`（旧接口保持不动）。

```bash
# 列表（支持 customer_id、area、status、q）
GET /api/projects-v2?customer_id=1&status=active

# 创建项目
POST /api/projects-v2
# 若有 customer_id 且未传 area，后端继承 customer.area。
curl -X POST http://127.0.0.1:8000/api/projects-v2 \
  -H 'Content-Type: application/json' \
  -d '{
    "customer_id": 1,
    "project_type": "customer",
    "name": "处理 3 个账号增购合同流程",
    "area": "客户_佰世赛",
    "tags": ["增购", "合同"]
  }'

# 详情
GET /api/projects-v2/{id}

# 更新
PATCH /api/projects-v2/{id}
curl -X PATCH http://127.0.0.1:8000/api/projects-v2/1 \
  -H 'Content-Type: application/json' \
  -d '{"status": "done"}'
```

### 10.5 Facts API

事实（facts）是 NotebookLM 的主要原始内容来源。写入规则：
- 用户明确说"记录一下" → status=`confirmed`
- 自动提取（任务完成、截图、会议纪要等） → status=`draft`
- 系统操作痕迹、提醒本身、无客户价值流水账 → **不写 fact**

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

# 删除（建议改 status=rejected，不硬删）
DELETE /api/facts/{id}
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
- `raw_facts_markdown`（推荐）
- `summary_markdown`（推荐）
- `insights_markdown`（推荐）
- `generation_meta`（可选 JSON 对象）
- `status`（可选）

**旧字段（兼容层，不作为新流程主字段）**
- `project`
- `material_date`
- `source_type`
- `source_refs`
- `raw_source_markdown`
- `candidate_markdown`
- `value_types`
- `review_note`
- `task_id`
- `archived_at`

#### 最小调用示例

```bash
# 列表（推荐新字段筛选）
GET /api/customer-materials?customer_id=1&review_batch_id=10&status=pending&material_type=period_summary

# 创建材料（新模型）
POST /api/customer-materials
curl -X POST http://127.0.0.1:8000/api/customer-materials \
  -H 'Content-Type: application/json' \
  -d '{
    "customer_id": 1,
    "project_v2_id": null,
    "review_batch_id": 1,
    "title": "佰世赛｜客户级｜2026-05-01 ~ 2026-05-07 客户事实与总结",
    "material_type": "period_summary",
    "period_start": "2026-05-01T00:00:00",
    "period_end": "2026-05-07T23:59:59",
    "raw_facts_markdown": "完整事实记录（不删减）...",
    "summary_markdown": "简要纪要...",
    "insights_markdown": "洞察 / 风险 / 下一步建议（AI 推导层）...",
    "status": "pending"
  }'

# 详情
GET /api/customer-materials/{id}

# 审核/更新（新模型主字段）
PATCH /api/customer-materials/{id}
curl -X PATCH http://127.0.0.1:8000/api/customer-materials/1 \
  -H 'Content-Type: application/json' \
  -d '{
    "status": "approved",
    "summary_markdown": "更新后的纪要",
    "insights_markdown": "更新后的洞察"
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

`tasks` 表新增以下字段（旧字段保留兼容）：

| 新字段 | 类型 | 说明 |
|---|---|---|
| `area` | string(128) nullable | 归属分类，替代旧 `project` 的真实语义 |
| `customer_id` | integer FK nullable | 关联客户 |
| `project_id` | integer FK nullable | 关联项目 |

旧 `project` 字段保留，兼容旧 API 和前端。创建/更新任务时：如果只传旧 `project`，后端兼容写入 `area`；返回时也保留旧 `project` 字段。

### 10.9 上传 NotebookLM 的拼接模板

审核通过后，上传到 NotebookLM 的 Markdown 按此模板拼接：

```markdown
# {customer.name}｜{project.name 或 "客户级"}｜{period_start} ~ {period_end} 客户事实与总结

## 一、完整事实记录

{raw_facts_markdown}

## 二、简要纪要

{summary_markdown}

## 三、洞察 / 风险 / 下一步建议

{insights_markdown}
```

规则：三层结构不能合并、不能删减；`insights_markdown` 必须明确标注为 AI 推导层。上传时使用 nblm 的 `upload-text` 命令，靠客户名匹配 Notebook。

---
