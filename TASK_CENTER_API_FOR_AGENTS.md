# Task Center API for Agents

给代理 / 脚本 / 自动化流程使用的 task_center 实操文档。

目标只有一个：

> 当用户提出提醒、待办、改时间、完成、取消等请求时，先把事实落进 task_center，再默认同步 OpenClaw cron。

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

### 9.1 创建客户材料

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
    "candidate_markdown": "轻度清洗后的 NotebookLM 候选入库 Markdown。去掉晚间收口/用户反馈已完成等系统痕迹，但不要过度总结客户事实。",
    "value_types": ["客户需求", "系统限制", "风险/阻塞", "解决方案"],
    "task_id": 105
  }'
```

### 9.2 查询客户材料

```bash
# 查询某客户未归档材料
curl 'http://127.0.0.1:8000/api/customer-materials?project=客户_苏中药业'

# 查询待审核材料
curl 'http://127.0.0.1:8000/api/customer-materials?status=pending'

# 查询某任务关联材料
curl 'http://127.0.0.1:8000/api/tasks/105/customer-materials'
```

### 9.3 更新 / 审核 / 归档

```bash
# 修改材料正文或状态
curl -X PATCH http://127.0.0.1:8000/api/customer-materials/1 \
  -H 'Content-Type: application/json' \
  -d '{"status":"approved", "review_note":"已确认可入库"}'

# 软归档，默认列表不再返回；如需看归档材料，加 include_archived=true
curl -X DELETE http://127.0.0.1:8000/api/customer-materials/1
```

### 9.4 字段规则

- `project`：沿用现有客户标签 / 项目名，例如 `客户_苏中药业`。
- `raw_source_markdown`：原始证据层，尽量完整保真；截图要转成多人对话文本，不能识别的图片标注“此处为图片”。
- `candidate_markdown`：NotebookLM 候选入库层，只做轻度格式化和去系统痕迹，不替代原始材料。
- `value_types`：可多选，建议值包括：客户需求、业务流程、系统限制、关键人信息、客户偏好、风险/阻塞、解决方案、商机/增购/续费、售后问题、可复用方法论。
- `status`：`pending`（待审核）、`approved`（已确认）、`skipped`（已跳过）、`uploaded`（已上传）。

如果二者冲突，以 task_center 最新任务时间为准，并立即修正 cron。
