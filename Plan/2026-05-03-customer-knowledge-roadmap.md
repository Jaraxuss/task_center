# TaskCenter 客户知识链路改造计划

创建时间：2026-05-03
负责人：阿龙 / OpenClaw main
目标：在不改桌面前端、不改 feishu-task Skill、不改第三方 nblm Skill 的前提下，把 TaskCenter 从“任务提醒账本”升级为“客户项目 + 事实库 + 周期材料审核 + NotebookLM 上传触发”的轻量系统。

---

## 0. 已确认的产品决策

### 0.1 不改的部分

- 暂不修改桌面前端。
- 暂不修改 `feishu-task` Skill：当前不使用飞书任务机制，提醒主要靠 OpenClaw cron。
- 不修改第三方 `nblm` Skill：它属于基础能力，只在新 Skill 中调用/遵循它的上传链路。
- 暂不修改晚间收口 cron：后续再设计。
- 不在 TaskCenter 中保存 NotebookLM 目标信息或外部上传引用。
- 不给 TaskCenter 配 LLM / NotebookLM API Key。审核完成后的上传由task owner告诉我触发，由 OpenClaw agent 使用 nblm 链路执行。

### 0.2 要改的部分

- TaskCenter 后端：新增/调整表、Schema、API、兼容逻辑、测试。
- 新建内部 Skill：定义客户事实采集、周期材料生成、审核后上传的规则；上传动作内部复用 nblm。
- Cron：把现有“每周总结”cron 替换为“每周客户材料生成”cron，时间为北京时间每周日 20:00。
- Agent 文档：更新 TaskCenter API 使用说明，让后续陌生 AI 能正确创建客户、项目、事实和审核材料。

---

## 1. 目标业务流程

### 1.1 日常事实产生

用户在聊天、任务完成、截图转写、转发消息、会议纪要中表达客户跟进事实时：

```text
聊天/任务完成/截图/会议纪要
  ↓
识别 customer / project / task 归属
  ↓
写入 facts
  ↓
周期 cron 聚合 facts
  ↓
生成 customer_materials pending
  ↓
审核页展示/修改/通过/跳过
  ↓
task owner告诉我上传
  ↓
我调用 nblm 链路上传到 NotebookLM
  ↓
TaskCenter 将 material 标记 uploaded
```

### 1.2 项目层级

```text
customers 客户
  ↓
projects 项目/事项包
  ↓
tasks 待办/提醒
  ↓
facts 事实
  ↓
customer_materials 周期材料
  ↓
NotebookLM
```

### 1.3 旧字段兼容

当前 `tasks.project` 实际是“归属分类/area”，不是新模型里的 project。

迁移策略：

- 数据库暂时保留 `tasks.project`，避免破坏旧 API 和旧前端。
- 新增 `tasks.area`，语义上承接旧 `project`。
- 新增 `tasks.customer_id`、`tasks.project_id`。
- 创建/更新任务时：如果只传旧 `project`，后端兼容写入 `area`；返回时也保留旧 `project` 字段。
- 新实现和新文档默认使用 `area/customer_id/project_id`。

---

## 2. 最终表结构

### 2.1 `customers`

客户表。表示真实客户、公司、组织或长期服务对象。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | integer PK | 客户唯一 ID。 |
| `name` | string(128) | 客户显示名称，例如 `佰世赛`。用于页面展示、搜索、NotebookLM 名称匹配。 |
| `key` | string(64), nullable/unique 建议 | 稳定标识，例如 `baishisai`。用于去重、程序引用、避免重名客户。若实现复杂，可先允许为空。 |
| `aliases_json` | text JSON array | 客户别名，如 `["客户_A", "BSS"]`。用于兼容旧 `tasks.project` 和口语叫法。 |
| `status` | string(32) | 客户状态：`active` / `paused` / `closed`。默认 `active`。 |
| `description` | text nullable | 客户补充说明。 |
| `area` | string(128) nullable | 默认归属分类，如 `客户_A`。用于任务看板和旧数据兼容。 |
| `tags_json` | text JSON array | 客户标签。 |
| `created_at` | datetime | 创建时间。 |
| `updated_at` | datetime | 更新时间。 |

不需要：`notebooklm_target`、`source_refs_json`、`archived_at`。

### 2.2 `projects`

项目表。真正表示客户项目、个人项目、内部项目。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | integer PK | 项目唯一 ID。 |
| `customer_id` | integer FK nullable | 所属客户。客户项目必填；个人/内部项目可为空。 |
| `project_type` | string(32) | `customer` / `personal` / `internal`。默认 `customer`。 |
| `name` | string(255) | 项目名称，例如 `处理 3 个账号增购合同流程`。 |
| `status` | string(32) | `active` / `waiting` / `done` / `canceled`。默认 `active`。 |
| `area` | string(128) nullable | 归属分类，通常继承客户 `area`。 |
| `tags_json` | text JSON array | 项目标签。 |
| `start_at` | datetime nullable | 项目开始时间。 |
| `target_end_at` | datetime nullable | 预计结束时间。 |
| `actual_end_at` | datetime nullable | 实际结束时间。 |
| `created_at` | datetime | 创建时间。 |
| `updated_at` | datetime | 更新时间。 |

不需要：`key`、`objective`、`scope_note`、`source_refs_json`、`archived_at`。

### 2.3 `facts`

事实表。NotebookLM 的主要原始内容来源。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | integer PK | 事实唯一 ID。 |
| `customer_id` | integer FK nullable | 所属客户。客户事实应尽量填写。 |
| `project_id` | integer FK nullable | 所属项目。能明确归属项目时填写。 |
| `task_id` | integer FK nullable | 来源任务。来自任务完成说明时填写。 |
| `fact_date` | datetime | 事实发生时间，不是写入时间。 |
| `title` | string(255) | 事实标题。 |
| `raw_markdown` | text | 原始事实内容。尽量保留用户原话、客户反馈、截图 OCR、会议结论和不确定性标注。 |
| `source_type` | string(32) | 来源类型：`chat` / `screenshot_ocr` / `task_completion` / `meeting_note` / `manual_input` / `forwarded_message` / `document`。 |
| `value_types_json` | text JSON array | 事实价值类型，如客户需求、业务流程、关键人信息、风险/阻塞、商机/增购/续费、交付结果等。 |
| `status` | string(32) | `draft` / `confirmed` / `rejected`。默认：自动提取为 `draft`，用户明确记录为 `confirmed`。 |
| `created_at` | datetime | 创建时间。 |
| `updated_at` | datetime | 更新时间。 |

不需要：`normalized_markdown`、`source`、`source_refs_json`、`confidence`、`archived_at`。

### 2.4 `customer_materials`

客户材料表。表示周期生成、待审核/待上传 NotebookLM 的材料包。旧表需要改造或兼容迁移。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | integer PK | 材料 ID。 |
| `customer_id` | integer FK | 所属客户。 |
| `project_id` | integer FK nullable | 所属项目。为空表示客户级材料。 |
| `review_batch_id` | integer FK nullable | 所属审核批次。 |
| `title` | string(255) | 材料标题。 |
| `material_type` | string(32) | `period_summary` / `fact_bundle` / `meeting_note` / `project_digest`。 |
| `period_start` | datetime nullable | 覆盖周期开始。 |
| `period_end` | datetime nullable | 覆盖周期结束。 |
| `raw_facts_markdown` | text | 完整事实内容。按时间/项目组织 facts，不删减事实。 |
| `summary_markdown` | text nullable | 简要纪要。 |
| `insights_markdown` | text nullable | 洞察、风险、下一步建议；明确是 AI 推导层。 |
| `status` | string(32) | `pending` / `approved` / `skipped` / `uploaded`。 |
| `generation_meta_json` | text JSON object nullable | 生成元信息，如 fact_count、model、周期等。 |
| `created_at` | datetime | 创建时间。 |
| `updated_at` | datetime | 更新时间。 |

不需要：`candidate_markdown`、`review_note`、`notebooklm_refs_json`、`archived_at`、旧 `source_refs_json`、旧 `raw_source_markdown`、旧 `value_types_json`、旧 `task_id`。

最终上传内容不存冗余字段，由 Skill 规则动态拼接：

```markdown
# {title}

## 一、完整事实记录
{raw_facts_markdown}

## 二、简要纪要
{summary_markdown}

## 三、洞察 / 风险 / 下一步建议
{insights_markdown}
```

### 2.5 `customer_material_facts`

材料-事实关联表。表示材料包含哪些 facts 以及排序。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | integer PK | 关联 ID。 |
| `material_id` | integer FK | `customer_materials.id`。 |
| `fact_id` | integer FK | `facts.id`。 |
| `sort_order` | integer | 事实在材料里的排序。 |
| `created_at` | datetime | 创建时间。 |

不需要：`include_mode`、`note`。

### 2.6 `review_batches`

审核批次表。一次 cron 生成多份材料时，用批次承接审核页分组。

| 字段 | 类型 | 说明 |
|---|---|---|
| `id` | integer PK | 批次 ID。 |
| `batch_type` | string(32) | `weekly_customer_summary` / `daily_customer_summary` / `manual_generation`。 |
| `title` | string(255) | 批次标题，例如 `2026-05-03 客户周期材料`。 |
| `period_start` | datetime nullable | 周期开始。 |
| `period_end` | datetime nullable | 周期结束。 |
| `status` | string(32) | `pending` / `partial` / `approved` / `uploaded`。 |
| `material_count` | integer | 本批次材料数量。 |
| `created_by` | string(32) | `cron` / `manual` / `agent`。 |
| `created_at` | datetime | 创建时间。 |
| `updated_at` | datetime | 更新时间。 |

不需要：`source_refs_json`、`approved_count`、`uploaded_count`。

### 2.7 `tasks` 新增字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `area` | string(128) nullable | 归属分类，替代旧 `project` 的真实语义。 |
| `customer_id` | integer FK nullable | 关联客户。 |
| `project_id` | integer FK nullable | 关联项目。 |

旧 `project` 字段保留，兼容旧 API 和前端。

---

## 3. 后端 API 计划

### 3.1 Customers API

- `GET /api/customers`
  - 支持 `q`、`status`。
- `POST /api/customers`
  - 创建客户。
  - 若未传 `area`，默认生成 `客户_{name}`。
  - 若未传 aliases，默认加入 `area`。
- `GET /api/customers/{id}`
- `PATCH /api/customers/{id}`

### 3.2 Projects API

- `GET /api/projects-v2`
  - 注意：现有 `/api/projects` 是旧 project summary，可避免冲突先用 `/api/projects-v2`。
  - 支持 `customer_id`、`area`、`status`、`q`。
- `POST /api/projects-v2`
  - 创建项目。
  - 若有 customer_id 且未传 area，继承 customer.area。
- `GET /api/projects-v2/{id}`
- `PATCH /api/projects-v2/{id}`

### 3.3 Facts API

- `GET /api/facts`
  - 支持 `customer_id`、`project_id`、`task_id`、`status`、`source_type`、`from`、`to`、`q`。
- `POST /api/facts`
  - 创建事实。
- `GET /api/facts/{id}`
- `PATCH /api/facts/{id}`
  - 支持修改 status、title、raw_markdown、归属等。
- `DELETE /api/facts/{id}`
  - 建议不硬删，第一版可改 status=`rejected`。

### 3.4 Customer Materials API 改造

保留现有路径 `/api/customer-materials`，但迁移到新字段。

- `GET /api/customer-materials`
  - 支持 `customer_id`、`project_id`、`review_batch_id`、`status`、`material_type`。
- `POST /api/customer-materials`
  - 创建材料。
- `GET /api/customer-materials/{id}`
- `PATCH /api/customer-materials/{id}`
  - 审核页保存修改、改状态。
- `POST /api/customer-materials/{id}/mark-uploaded`
  - 上传后由 agent 调用，标记 uploaded。

### 3.5 Review Batches API

- `GET /api/review-batches`
- `POST /api/review-batches`
- `GET /api/review-batches/{id}`
- `PATCH /api/review-batches/{id}`
- `GET /api/review-batches/{id}/customer-materials`

---

## 4. 新 Skill 计划

### 4.1 Skill 名称

建议：`task-center-customer-knowledge`

位置：

```text
/home/velen/.openclaw/workspace/skills/task-center-customer-knowledge/SKILL.md
```

### 4.2 Skill 负责什么

这个 Skill 不直接实现外部 API，而是定义 OpenClaw agent 如何使用 TaskCenter + nblm 完成客户知识闭环。

职责：

1. 识别客户事实触发点。
2. 创建/维护 customers、projects、facts。
3. 定义周期材料生成规则。
4. 定义审核后上传 NotebookLM 的拼接规则。
5. 说明不要修改 nblm Skill，只调用/遵循 nblm 上传能力。
6. 说明不要使用 feishu-task Skill 作为任务系统。

### 4.3 事实写入规则

触发条件：

- 用户说“记录一下 / 这个写入事实 / 这个客户反馈是……” → 写 fact，默认 `confirmed`。
- 任务完成且有关联 `customer_id/project_id`，且 completion_note 有实质客户跟进内容 → 自动提取 fact，默认 `draft`。
- 用户转发截图、消息、会议纪要 → 提取 fact，默认 `draft`。
- 事实明显是系统操作痕迹、提醒本身、无客户价值流水账 → 不写 fact。

### 4.4 周期材料拼接规则

上传/展示 Markdown：

```markdown
# {customer.name}｜{project.name 或 客户级}｜{period_start} ~ {period_end} 客户事实与总结

## 一、完整事实记录
{raw_facts_markdown}

## 二、简要纪要
{summary_markdown}

## 三、洞察 / 风险 / 下一步建议
{insights_markdown}
```

要求：

- `raw_facts_markdown` 不删减事实。
- `summary_markdown` 可以摘要。
- `insights_markdown` 必须明确是推导，不混入事实层。
- 上传 NotebookLM 时靠客户名称匹配 nblm 目标。

---

## 5. Cron 计划

### 5.1 周期客户材料生成 cron

替换现有每周总结 cron。

时间：北京时间每周日 20:00。

Cron 表达式建议：

```text
0 20 * * 0
TZ: Asia/Shanghai
```

payload：isolated `agentTurn`。

任务文本大意：

```text
这是每周客户材料生成任务。请使用 task-center-customer-knowledge Skill：
1. 读取 TaskCenter 本周 confirmed/draft facts；
2. 按 customer + project 分组；
3. 生成 review_batch；
4. 为每组 facts 生成 customer_materials，status=pending；
5. 建立 customer_material_facts 关联；
6. 只向task owner简短通知生成了多少份待审核材料，不输出全文。
```

### 5.2 审核后上传触发

不做自动 cron。

流程：

```text
task owner在审核页审核完成
  ↓
task owner告诉我“上传本周客户材料”或指定 material/batch
  ↓
我读取 approved customer_materials
  ↓
按 Skill 拼接 Markdown
  ↓
调用/遵循 nblm Skill 上传
  ↓
成功后 PATCH customer_materials status=uploaded
```

---

## 6. 实现拆分

### 子任务 A：TaskCenter 后端数据模型/API

范围：

- 修改 `task_center/backend/models.py`
- 修改 `schemas.py`
- 修改 `main.py`
- 修改兼容迁移 `ensure_schema_compatibility()`
- 新增 API
- 保证旧任务接口不炸
- 增加最小测试或脚本验证

### 子任务 B：TaskCenter 文档 + 新 Skill

范围：

- 新建 `skills/task-center-customer-knowledge/SKILL.md`
- 更新 `task_center/TASK_CENTER_API_FOR_AGENTS.md`
- 必要时新增简短 examples
- 明确 nblm 只是上传链路，不修改第三方 skill
- 明确 feishu-task 不参与

### 子任务 C：周期材料生成脚本/工具

范围：

- 在 TaskCenter 或 workspace scripts 中新增一个可由 cron/agent 调用的生成入口。
- 读取 facts，按 customer+project 分组。
- 创建 review_batch、customer_materials、customer_material_facts。
- 生成 raw_facts_markdown / summary_markdown / insights_markdown。
- 第一版可让 agentTurn 负责 LLM 生成，但脚本/API 需要支持写入结构化结果。

### 子任务 D：Cron 盘点与替换计划

范围：

- 找出现有“每周总结”cron。
- 不立即删除未知 cron；记录 jobId、schedule、payload。
- 待后端和 Skill 合并后，由主代理更新 cron 为每周日 20:00 北京时间。
- 如果可以安全更新，执行 cron update；否则输出具体操作建议给主代理。

---

## 7. 验收标准

### 7.1 后端验收

- 服务可启动。
- 旧 `/api/tasks` 创建/查询仍可用。
- 可创建 customer。
- 可创建 project。
- 可创建 fact。
- 可创建 review_batch。
- 可创建 customer_material，并关联 facts。
- 可查询 pending customer_materials。
- 可 PATCH material 到 approved/uploaded。

### 7.2 文档/Skill 验收

- 陌生 AI 能看懂什么时候写 fact。
- 陌生 AI 能看懂 weekly cron 怎么生成材料。
- 陌生 AI 能看懂审核后怎么上传 NotebookLM。
- 文档明确不要改 feishu-task / nblm。

### 7.3 Cron 验收

- 每周日 20:00 北京时间触发。
- 触发后只生成 pending 材料和简短通知。
- 不把全文推送到聊天。
- 不自动上传 NotebookLM。

---

## 8. 风险与处理

### 8.1 旧 customer_materials 字段冲突

现有表已有 `project/source_type/source_refs/raw_source_markdown/candidate_markdown/review_note/task_id/archived_at` 等字段。

处理：

- SQLite 迁移第一版可以只 `ALTER TABLE ADD COLUMN` 新字段，不物理删除旧字段。
- Schema/API 切到新字段。
- 旧字段保留但不再使用，降低破坏风险。

### 8.2 `/api/projects` 命名冲突

现有 `/api/projects` 是旧 task project summary。

处理：

- 第一版新项目 API 用 `/api/projects-v2`。
- 旧 `/api/projects` 保持不动。
- 后续桌面前端改造时再统一命名。

### 8.3 LLM 生成职责边界

TaskCenter 不配置 LLM key。

处理：

- 后端只提供数据结构/API。
- 周期 cron 由 OpenClaw agentTurn 执行 LLM 生成，再写入 API。

### 8.4 NotebookLM 依赖

不把 NotebookLM 目标固化在 TaskCenter。

处理：

- 上传时由 agent 使用客户名 + nblm Skill 进行匹配。
- 上传结果只把 material 标记 uploaded，不存外部细节。

---

## 9. 推荐执行顺序

1. 子任务 A：后端 schema/API/兼容。
2. 子任务 B：Skill + 文档。
3. 子任务 C：生成器脚本/agent 入口。
4. 主代理 review 合并结果。
5. 跑最小 API 验证。
6. 子任务 D 或主代理更新 cron。
7. 提交 git commit。

---

## 10. 给编码子代理的共用约束

- 模型：`glm/glm-5.1`
- thinking：high
- 不改桌面前端。
- 不改 feishu-task Skill。
- 不改第三方 nblm Skill。
- 不删除旧数据库字段，只追加和兼容。
- 如果文档和实现冲突，以 `task_center/backend/main.py`、`schemas.py`、`models.py` 为准。
- 修改完成后必须运行能跑的最小验证；不能跑要说明原因。
