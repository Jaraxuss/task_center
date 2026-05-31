# Task 提醒投递模式与调度方案（2026-05-20）

创建时间：2026-05-20  
负责人：task owner / OpenCode

## 目标

把 TaskCenter 的「提醒」从 Task 详情本体中拆出来，作为独立调度与投递层来设计。第一版只支持三种提醒模式：

- 飞书卡片 V2：默认模式，由 TaskCenter 内部 worker 到点发送 Card JSON 2.0。
- 飞书卡片 V1：兼容模式，由 TaskCenter 内部 worker 到点发送 Card JSON 1.0。
- AI 提醒：高级模式，保存时立即创建 OpenClaw cron isolated agentTurn，到点由 OpenClaw Agent 处理并投递。

状态：后端 Phase 已完成（2026-05-20）；前端 / 移动端待实现。

---

## 0. 背景

### 0.1 已有能力

TaskCenter 后端已经具备飞书卡片 SDK 能力：

| 能力 | 位置 | 说明 |
|---|---|---|
| Feishu Card V2 SDK | `backend/scripts/sdk/feishu-card-v2` | 构建和发送 Card JSON 2.0 |
| Feishu Card V1 SDK | `backend/scripts/sdk/feishu-card-v1` | 构建和发送 Card JSON 1.0 |
| TaskCenter V2 服务入口 | `backend/services/feishu_card` | 后端内部使用的 V2 兼容导入层 |
| Task 卡片构建 | `backend/services/task_card_builder.py` | 把 Task 转成提醒卡片 Markdown / V2 card |
| Task 卡片投递 | `backend/services/notification_delivery.py` | `send_task_card_v2(...)` 已可发送 V2 卡片 |

Card SDK 的关键能力：

- 直连飞书 OpenAPI `im/v1/messages`，发送 `msg_type=interactive`。
- 支持 `open_id`、`user_id`、`union_id`、`email`、`chat_id`。
- 支持 `uuid` 幂等。
- 支持 tenant access token 获取与进程内缓存。
- 支持 30KB 卡片大小检查。
- V2 支持 `schema=2.0`、header title/subtitle、summary、Markdown block。
- V1 可作为 V2 不稳定时的手工 fallback。

### 0.2 OpenClaw 仍保留的能力

OpenClaw cron 仍适合做需要 Agent 能力的定时任务：

```bash
openclaw cron add \
  --at "2026-05-20T18:00:00+08:00" \
  --session isolated \
  --message "..." \
  --announce \
  --channel feishu \
  --to user:ou_xxx \
  --delete-after-run
```

本 Plan 不把 `cron main system-event` 纳入提醒方式。当前没有清晰产品场景，且它不保证飞书确定投递。

---

## 1. 核心决策

### 1.1 只保留三种提醒模式

| 模式 | 内部值 | 定时机制 | 投递机制 | 默认 |
|---|---|---|---|---|
| 飞书卡片 V2 | `feishu_card_v2` | TaskCenter worker | TaskCenter 直连飞书 OpenAPI 发 Card JSON 2.0 | 是 |
| 飞书卡片 V1 | `feishu_card_v1` | TaskCenter worker | TaskCenter 直连飞书 OpenAPI 发 Card JSON 1.0 | 否 |
| AI 提醒 | `openclaw_cron_agent` | OpenClaw cron | `isolated agentTurn + announce` | 否 |

不做：

- 不提供 `openclaw_cron_system_event` 选项。
- 不默认走 `openclaw message send`。
- 不在普通提醒中调用模型。
- 不在第一版自动迁移历史 OpenClaw cron。

### 1.2 老数据兼容

老数据的 `delivery_mode` 可以是 `null`。

读取时按兼容规则处理：

```text
delivery_mode is null => 视为 feishu_card_v2
```

但不强制迁移历史行。未来如果需要数据清理，可以单独写 migration / backfill。

### 1.3 历史 OpenClaw cron 不迁移

不扫描、不匹配、不批量 disable 老的 `task_center#XX` cron job。

原因：

- 从 OpenClaw cron 配置里反查历史 job 成本较高。
- 老提醒偶尔重复提醒可以接受。
- 等 TaskCenter 卡片投递链路稳定后，通过修改 Skill 断掉后续默认 cron 创建链路。
- 新设计仍保留 `external_cron_job_id` 字段，后续新建的 AI 提醒可以被追踪和清理。

### 1.4 AI 提醒保存时立即创建 cron

AI 提醒不是到点时由 TaskCenter 再去调用 OpenClaw，而是在保存提醒设置时立即创建 OpenClaw cron job。

```text
保存 AI 提醒
→ TaskCenter 立即 openclaw cron add
→ 保存 external_cron_job_id
→ 到点由 OpenClaw cron 执行 isolated agentTurn 并投递
```

这样可以避免到点时 TaskCenter 才调用 OpenClaw，因命令超时或 OpenClaw 临时不可用而错过提醒。

### 1.5 AI 提醒第一版使用静态 prompt

第一版不区分「静态 AI 提醒」和「动态 AI 提醒」。

规则：

- 前端提供一个默认 prompt 模板。
- 用户可以在前端编辑 prompt。
- 保存后，把用户最终确认的 prompt 写入 reminder，用于创建 OpenClaw cron。
- 不要求到点时 Agent 再读取 TaskCenter 最新 task 状态。

注意：默认模板来自前端，不作为数据库内置默认值。

---

## 2. 数据模型

### 2.1 扩展 `reminders`

现有 `reminders` 表保留，扩展为提醒调度主表。

建议字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `delivery_mode` | string nullable | `feishu_card_v2` / `feishu_card_v1` / `openclaw_cron_agent`；老数据允许 `null` |
| `receive_id` | string nullable | 飞书接收目标；为空时使用默认配置 |
| `receive_id_type` | string nullable | `open_id` / `chat_id` / `user_id` / `union_id` / `email`；为空时使用默认配置 |
| `external_cron_job_id` | string nullable | AI 提醒对应的 OpenClaw cron job id |
| `message_id` | string nullable | V1/V2 卡片发送成功后的飞书 message id |
| `request_uuid` | string nullable | 飞书发送幂等 UUID |
| `fired_at` | datetime nullable | 实际成功投递时间 |
| `last_error` | text nullable | 最近一次投递或 cron 操作失败原因 |
| `retry_count` | int | V1/V2 worker 投递重试次数 |
| `ai_prompt` | text nullable | AI 提醒使用的静态 prompt；仅 `openclaw_cron_agent` 使用 |

`external_cron_job_id` 对老数据可以为空。仅新建或编辑后的 AI 提醒需要写入。

### 2.2 状态枚举

第一版使用 5 个状态：

| 状态 | 含义 |
|---|---|
| `scheduled` | 等待触发 |
| `fired` | V1/V2 已成功发送；AI 提醒可暂不自动回写为 fired |
| `canceled` | 用户取消、task 完成/取消导致提醒取消 |
| `failed` | 投递或 cron 操作失败，超过可恢复范围 |
| `disabled` | 提醒被禁用或 AI cron 已被禁用/移除后的保守状态 |

说明：

- V1/V2 的状态由 TaskCenter worker 维护。
- AI 提醒第一版只要求记录 cron 创建/删除结果，不要求从 OpenClaw run history 回写实际送达状态。
- 后续如果需要闭环，可以增加 OpenClaw cron runs reconciler。

### 2.3 幂等 UUID

V1/V2 卡片发送建议使用 reminder 粒度 UUID：

```text
tc-reminder-{reminder_id}
```

不要继续只用 `task.updated_at` 生成 UUID，因为同一个 task 可能有多个 reminder，也可能发生重试。

---

## 3. 三种模式流程

### 3.1 飞书卡片 V2

创建 / 编辑：

```text
写 reminders
delivery_mode = feishu_card_v2
status = scheduled
external_cron_job_id = null
```

到点：

```text
TaskCenter worker 扫描 due reminder
→ build Task card v2
→ FeishuCardClient.send_card(...)
→ 成功写 message_id / fired_at / status=fired
→ 失败写 last_error / retry_count，超过阈值后 status=failed
```

### 3.2 飞书卡片 V1

创建 / 编辑：

```text
写 reminders
delivery_mode = feishu_card_v1
status = scheduled
external_cron_job_id = null
```

到点：

```text
TaskCenter worker 扫描 due reminder
→ build Task card v1
→ FeishuCardV1Client.send_card(...)
→ 成功写 message_id / fired_at / status=fired
→ 失败写 last_error / retry_count，超过阈值后 status=failed
```

V1 是手工 fallback，不作为默认模式。

### 3.3 AI 提醒

创建 / 编辑：

```text
写 reminders
delivery_mode = openclaw_cron_agent
status = scheduled
ai_prompt = 用户确认后的 prompt

立即调用 openclaw cron add
→ 保存 external_cron_job_id
```

建议命令形态：

```bash
openclaw cron add \
  --name "TaskCenter AI reminder #<reminder_id>" \
  --at "<remind_at ISO + timezone>" \
  --session isolated \
  --message "<ai_prompt>" \
  --announce \
  --channel feishu \
  --to "user:<receive_id>" \
  --delete-after-run
```

注意：

- `openclaw cron add` 输出 job id 的结构后续单独测试。
- 第一版可以先放 TODO，占位 `external_cron_job_id` 写入逻辑。
- 不为了 job id 解析去做复杂的 `cron list --json` 反查。

---

## 4. 模式切换与生命周期

### 4.1 从 AI 改成 V2 / V1

如果 reminder 存在 `external_cron_job_id`：

```bash
openclaw cron rm <external_cron_job_id>
```

然后更新 reminder：

```text
delivery_mode = feishu_card_v2 或 feishu_card_v1
external_cron_job_id = null
status = scheduled
last_error = null
```

如果 `cron rm` 失败：

- 不要静默吞掉。
- 记录 `last_error`。
- API 可以返回明确错误，避免用户误以为旧 AI cron 已清理。

### 4.2 从 V2 / V1 改成 AI

```text
更新 reminder 基本字段
写 ai_prompt
立即 openclaw cron add
保存 external_cron_job_id
```

如果 `cron add` 失败：

- reminder 不应进入「看似已安排」的状态。
- 可以把状态置为 `failed` 并记录 `last_error`。
- 前端提示用户 AI cron 创建失败。

### 4.3 AI 提醒改时间 / 改 prompt

第一版优先简单可靠：

```text
如果 external_cron_job_id 存在：openclaw cron rm <old-id>
openclaw cron add <new config>
保存新的 external_cron_job_id
```

不强依赖 `openclaw cron edit`。

### 4.4 取消 / 完成 Task

当 task 被取消或完成时，如果关联未触发 reminder 是 AI 模式：

```bash
openclaw cron rm <external_cron_job_id>
```

然后：

```text
reminder.status = canceled
```

V1/V2 提醒只需要把未触发 reminder 标为 `canceled`，不需要外部操作。

---

## 5. TaskCenter Worker

### 5.1 扫描范围

Worker 只处理 V1/V2，不处理 AI 提醒。

查询条件：

```text
status = scheduled
delivery_mode in (null, feishu_card_v2, feishu_card_v1)
remind_at <= now
```

其中 `delivery_mode = null` 按 `feishu_card_v2` 处理。

### 5.2 扫描间隔

默认扫描间隔：30 秒。

支持配置：

```text
TASK_CENTER_REMINDER_WORKER_INTERVAL_SECONDS=30
```

建议限制最小值，避免误配置导致高频扫描：

```text
min = 5 seconds
default = 30 seconds
```

### 5.3 处理流程

```text
每轮 tick:
  查询 due reminders
  对每条 reminder:
    加载 task
    如果 task 已 done/canceled:
      reminder.status = canceled
      continue

    根据 delivery_mode 构建 V1/V2 卡片
    调用对应 Feishu SDK 发送

    成功:
      reminder.status = fired
      reminder.fired_at = now
      reminder.message_id = response.data.message_id
      reminder.request_uuid = tc-reminder-{id}
      reminder.last_error = null

    失败:
      reminder.retry_count += 1
      reminder.last_error = error message
      未超过阈值: 保持 scheduled，等待下轮重试
      超过阈值: status = failed
```

重试策略第一版保持简单：

- 不做指数退避。
- 每 30 秒重试一次。
- 最大重试次数可配置，默认 3 次。

建议配置：

```text
TASK_CENTER_REMINDER_MAX_RETRIES=3
```

---

## 6. OpenClaw Cron Adapter

### 6.1 服务封装

新增服务层封装，避免 subprocess 逻辑散在 router 中：

```text
backend/services/openclaw_cron.py
```

建议函数：

```python
create_ai_reminder_job(reminder, task) -> str | None
remove_ai_reminder_job(job_id: str) -> None
```

第一版不强制实现复杂 job id 反查。

### 6.2 TODO：确认 `cron add` 输出结构

需要后续单独测试：

```bash
openclaw cron add ...
```

确认 stdout 是否稳定包含 job id，以及是否有 `--json` 输出。

本 Plan 不要求当前就解决该问题。实现时可以先留 TODO 或使用临时解析逻辑。

### 6.3 删除策略

只要 `openclaw cron rm <job-id>` 存在，就直接使用 `rm`。

适用场景：

- AI 改成 V1/V2。
- AI 提醒改时间 / 改 prompt。
- task 完成 / 取消导致 AI 提醒失效。
- 用户删除或取消 AI reminder。

---

## 7. 前端设计

### 7.1 Task 详情页保持干净

Task 详情页不展开提醒技术细节，只显示摘要：

```text
提醒：2026-05-20 18:00 · 飞书卡片 V2
```

点击进入提醒设置 sheet。

### 7.2 提醒设置 sheet

提醒方式只提供三项：

```text
提醒方式
- 飞书卡片 V2（默认，推荐）
- 飞书卡片 V1（兼容模式）
- AI 提醒（OpenClaw 定时处理）
```

说明文案：

```text
飞书卡片 V2：由 TaskCenter 到点直接发送，默认推荐。
飞书卡片 V1：V2 不稳定时手动切换。
AI 提醒：保存后立即创建 OpenClaw 定时 Agent 任务，到点由 Agent 处理并投递。
```

### 7.3 AI Prompt 编辑

选择 AI 提醒时，前端生成默认 prompt 并填入 textarea。

默认 prompt 由前端模板生成，不是数据库默认值。

示例：

```text
你是 TaskCenter 定时提醒助手。

请在到点后发送一条简洁中文提醒给task owner。不要扩写，不要引入额外事实。

任务信息：
- task_center #<id>
- 标题：<title>
- 计划时间：<due_at>
- 状态：<status>
- 项目：<project>
- 备注：<description>

请输出一条适合飞书发送的提醒。
```

用户可以直接编辑这个 prompt。保存后，最终文本写入 `reminders.ai_prompt`。

### 7.4 高级诊断

提醒设置底部可以折叠显示：

```text
飞书 message_id: xxx
OpenClaw cron job: xxx
最近错误: xxx
重试次数: 1/3
```

第一版可以不做复杂诊断页。

---

## 8. 实现范围

后端实现状态：已完成。

已落地内容：

- 扩展 `Reminder` 模型、schema 和 Alembic migration。
- 增加 `failed` / `disabled` 状态。
- 增加 V1 服务导入层与 V1 task card builder。
- 增加 V1/V2 统一提醒投递入口。
- 增加 TaskCenter reminder worker，默认处理 `null` / V2 / V1。
- 增加 OpenClaw cron adapter，AI 提醒保存时创建 cron，切换/取消/完成时 `cron rm`。
- 增加 reminder 更新端点，用于模式切换和 AI prompt / 时间调整。
- 接入 FastAPI lifespan 后台 worker loop，扫描间隔默认 30 秒且可配置。

保留 TODO：

- `openclaw cron add` stdout/job id 结构后续单独测试，目前只做 best-effort 解析。
- 前端提醒设置 sheet 尚未实现。

### 8.1 后端

| 文件 / 模块 | 改动 |
|---|---|
| `backend/models.py` | 扩展 `ReminderStatus` 和 `Reminder` 字段 |
| `backend/schemas/tasks.py` | 扩展 `ReminderCreate` / `ReminderRead` |
| `backend/alembic/versions/*` | 新增 reminder 字段 migration |
| `backend/config.py` | 增加 worker interval / max retries 配置 |
| `backend/services/notification_delivery.py` | 抽象 V1/V2 发送入口 |
| `backend/services/task_card_builder.py` | 如需补 V1 card builder，可在此扩展 |
| `backend/services/openclaw_cron.py` | 新增 OpenClaw cron adapter |
| `backend/services/reminder_worker.py` | 新增 due reminder 扫描与投递逻辑 |
| `backend/routers/tasks.py` | reminder 创建/编辑/取消时处理 delivery mode 与 AI cron 生命周期 |

### 8.2 前端 / 移动端

| 文件 / 模块 | 改动 |
|---|---|
| `mobile_frontend/src/types.ts` | 扩展 Reminder 类型 |
| `mobile_frontend/src/lib` | 扩展 reminder API payload |
| `mobile_frontend/src/sheets/TaskDetailSheet.tsx` | 只展示提醒摘要入口 |
| `mobile_frontend/src/sheets/*Reminder*` | 新增或扩展提醒设置 sheet |
| `mobile_frontend/src/styles.css` | 增加提醒设置 UI 样式 |

---

## 9. 验证

### 9.1 后端测试

建议新增测试：

| 测试 | 覆盖 |
|---|---|
| V2 reminder worker sends card | due reminder 触发 V2 SDK，写入 `message_id/fired_at/status` |
| V1 reminder worker sends card | due reminder 触发 V1 SDK |
| null delivery_mode fallback | 老数据 `delivery_mode=null` 按 V2 发送 |
| failed delivery retry | 失败写 `last_error/retry_count`，超过阈值 `failed` |
| AI create calls cron add | 创建 AI reminder 立即创建 OpenClaw cron |
| AI to V2 calls cron rm | 模式切换删除旧 cron |
| task complete cancels AI cron | task 完成时删除未触发 AI cron |
| task cancel cancels AI cron | task 取消时删除未触发 AI cron |

### 9.2 手测路径

1. 新建 V2 提醒，到点收到飞书 V2 卡片。
2. 切换为 V1，到点收到飞书 V1 卡片。
3. 新建 AI 提醒，保存后确认 OpenClaw cron job 创建。
4. AI 提醒改成 V2，确认旧 OpenClaw cron 被 `rm`。
5. AI 提醒改时间，确认旧 cron 被 `rm` 且新 cron 被创建。
6. task 完成 / 取消，确认未触发 AI cron 被 `rm`。
7. 老 reminder `delivery_mode=null` 可以被 worker 当 V2 正常发送。

### 9.3 命令验证

后续单独验证：

```bash
openclaw cron add ...
openclaw cron rm <job-id>
```

重点确认：

- `cron add` stdout 是否稳定返回 job id。
- 是否有 `--json` 输出。
- `cron rm` 对不存在 job id 的返回码与 stderr 行为。

---

## 10. 风险与取舍

| 风险 | 等级 | 处理 |
|---|---|---|
| V2 卡片线上兼容问题 | 中 | 提供 V1 手工 fallback |
| AI cron job id 获取不稳定 | 中 | 第一版可留 TODO，后续单独测试 CLI 输出结构 |
| TaskCenter worker 重复发送 | 中 | 使用 `tc-reminder-{id}` 作为飞书 uuid，并在 DB 状态上做 fired 标记 |
| 旧 OpenClaw cron 继续提醒 | 低 | 可接受，不做历史迁移 |
| AI 提醒静态 prompt 与 task 最新状态不一致 | 中 | 第一版接受；用户可编辑 prompt，后续再考虑动态读取 TaskCenter |
| cron rm 失败导致旧 AI 提醒残留 | 中 | API 明确报错并写 `last_error`，不假装切换成功 |

---

## 11. 后续不在本轮

- 历史 OpenClaw cron 自动迁移。
- OpenClaw cron runs 回写 TaskCenter。
- AI 动态提醒模板，即到点先读取 TaskCenter 最新 task 状态。
- 飞书卡片按钮与回调处理。
- 独立提醒中心 / 诊断中心。
- 复杂 recurrence 规则升级为 RRULE 或 nth weekday。

---

## 12. 最终结论

第一版提醒体系定为：

```text
默认普通提醒：TaskCenter worker + Feishu Card V2 SDK
兼容普通提醒：TaskCenter worker + Feishu Card V1 SDK
AI 提醒：保存时创建 OpenClaw cron isolated agentTurn，并保存 external_cron_job_id 以便后续 rm
```

TaskCenter 负责普通提醒的调度和卡片投递；OpenClaw 只负责用户显式选择的 AI 定时提醒。老数据不迁移，老 cron 不扫描，避免为历史兼容引入过重机制。
