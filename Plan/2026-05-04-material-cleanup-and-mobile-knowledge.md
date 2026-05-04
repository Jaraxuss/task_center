# CustomerMaterial 字段收口 + 移动端「知识」Tab（2026-05-04 Phase 2）

创建时间：2026-05-04
负责人：南哥 / OpenClaw main / Cascade
父 Plan：`Plan/2026-05-04-customer-knowledge-revision.md`

目标：

1. 把 `CustomerMaterial` 的正文字段收口到**唯一一个** `raw_facts_markdown`，物理删掉 `raw_source_markdown` / `candidate_markdown` / `summary_markdown` / `insights_markdown` / `review_note` 五个旧/兼容字段，前后端同步清理。
2. 改造移动端 `mobile_frontend`：底部 Tab「材料」→「知识」，内嵌「事实 / 材料」子 Tab（复用看板 segmented 样式），补齐 fact 的查看 / 编辑 / 状态切换能力，按 `review_batch_id` 分组展示 material，关联 facts 可跳转。
3. 彻底贯彻"卡片行内无操作按钮、全部动作收进详情页"的移动端交互原则。

---

## 0. 与父 Plan 的关系

### 0.1 仍然有效

- 父 Plan §1（核心决策）、§2（`tasks.source_type`）、§3（后端 API 变更）、§4（cron + 脚本）、§5（SKILL 文档）整体保留。
- 父 Plan §9 里"旧字段物理保留"的硬约束**被本 Plan 替换**——本轮决定物理删除。
- 2026-05-03 roadmap 的 5 表结构保留。

### 0.2 本 Plan 替换 / 细化的条目

- 替换 父 Plan §1.4 / §9：`summary_markdown` / `insights_markdown` 不再"保留兼容"，**物理删除**。
- 替换 父 Plan §6（移动端审核页更新）：本 Plan 是 §6 的**完整展开**，不仅覆盖材料审核，还新增 facts Tab。
- 细化 父 Plan §10（风险）：加上"后端字段删除对已有数据 / 桌面端 / 其它客户端的影响"评估。

---

## 1. 核心决策汇总

### 1.1 字段收口（CustomerMaterial）

**保留（写入字段）**：

- `raw_facts_markdown`（**唯一正文字段**，脚本 / agent / 移动端编辑都走这一个）

**保留（元数据字段）**：

- `id` / `title` / `status` / `created_at` / `updated_at` / `archived_at`
- `customer_id` / `project_v2_id` / `review_batch_id` / `material_type`
- `period_start` / `period_end` / `generation_meta`
- `project`（兼容桌面端 + legacy）/ `task_id`（兼容）/ `source` / `source_type` / `source_refs` / `value_types` / `material_date`

**物理删除（列 + schema + 所有引用）**：

- `raw_source_markdown`（旧：一次性原始材料原文）
- `candidate_markdown`（旧：NotebookLM 候选清洗文）
- `summary_markdown`（新 v2 兼容：简要纪要，由 NotebookLM 承担）
- `insights_markdown`（新 v2 兼容：洞察建议，由 NotebookLM 承担）
- `review_note`（旧：审核备注，新流程直接切 status 不写备注）

### 1.2 字段删除的原则

- **先搬后删**：对任何存量 row，如果 `raw_facts_markdown` 为空、而被删字段非空，先做一次"旧文本 → raw_facts_markdown"的搬迁，保证内容不丢。
- **不做反向兼容**：schema / API / 序列化 / 搜索 / 前端全部同步移除，不保留"接受但忽略"这种软层。
- **桌面前端**：已 grep `task_center/frontend/src/` **零引用**这五个字段，可安全删除。

### 1.3 移动端主决策

- 底部 Tab rename：`材料` → `知识`
- `知识` Tab 内嵌 segmented control：`事实 | 材料`（默认停在 `材料`，审核优先），复用 `board-segmented` 样式
- **行内卡片不放任何操作按钮**，所有动作（通过 / 跳过 / 归档 / 状态切换 / 删除）收进**详情 sheet**
- **不做"新增材料"入口**，不做"新增事实"入口（全部由 agent 写入）
- material 详情里展示关联 facts，可点击跳转 fact 详情
- fact 详情里展示关联 task，可点击跳转 task 详情
- 没有"已传"按钮 —— 上传唯一路径：用户飞书回复 `审核完成 #N` → 主代理调 nblm + `POST /mark-uploaded`

### 1.4 硬约束

- 不动桌面端代码
- 不动 feishu-task SKILL
- 不动 nblm SKILL
- 不动 cron 配置（由 OpenClaw 自行管理）
- 不在 TaskCenter 后端引入 LLM 调用
- 不引入 React Router / React Query 等新依赖（移动端保持现有轻量结构）

---

## 2. 后端字段清理（`task_center/backend`）

### 2.1 `models.py`

- `CustomerMaterial` 模型移除 5 个 `Mapped[str | None]` 列：
  - `raw_source_markdown`
  - `candidate_markdown`
  - `summary_markdown`
  - `insights_markdown`
  - `review_note`

### 2.2 `schemas.py`

- `CustomerMaterialCreate` / `CustomerMaterialUpdate` / `CustomerMaterialRead`：移除 5 个字段定义。

### 2.3 `main.py`

- `serialize_customer_material`：移除 5 个字段的赋值。
- `create_customer_material`：移除 5 个字段的构造参数。
- `update_customer_material`：移除 5 个字段的 patch 分支。
- 搜索 `q` 参数：移除对 `raw_source_markdown.like(...)` 和 `candidate_markdown.like(...)` 的 OR 分支，只保留 `raw_facts_markdown.like(...)` / `title.like(...)`。
- `ensure_schema_compatibility`：**新增一段数据搬迁 + 列删除**（见 §2.4）。

### 2.4 数据搬迁 + DROP COLUMN 迁移

SQLite 3.45.1 支持 `ALTER TABLE ... DROP COLUMN`。在 `ensure_schema_compatibility` 中按顺序执行（一次性，幂等）：

```python
# 1) 搬迁：raw_facts_markdown 为空时，按优先级回填
#    优先级：candidate_markdown > raw_source_markdown > summary_markdown > insights_markdown
cur.execute("""
    UPDATE customer_materials
    SET raw_facts_markdown = COALESCE(
        raw_facts_markdown,
        candidate_markdown,
        raw_source_markdown,
        summary_markdown,
        insights_markdown
    )
    WHERE raw_facts_markdown IS NULL OR raw_facts_markdown = ''
""")

# 2) DROP COLUMN（逐列执行，每条 try/except，列不存在时忽略）
for col in [
    "raw_source_markdown",
    "candidate_markdown",
    "summary_markdown",
    "insights_markdown",
    "review_note",
]:
    try:
        cur.execute(f"ALTER TABLE customer_materials DROP COLUMN {col}")
    except sqlite3.OperationalError:
        pass  # 列已不存在
```

**幂等保证**：基于 `ALTER TABLE DROP COLUMN` 对不存在列抛错后 catch，迁移重复执行无副作用。

### 2.5 预期 API 行为变化

- `POST /api/customer-materials` 带这 5 个字段时：FastAPI/Pydantic 默认 `extra="ignore"` → **静默忽略**；带严格模式则 422（目前项目用默认 ignore，影响为零）。
- `GET /api/customer-materials` / `GET /api/customer-materials/{id}` 响应 **不再包含**这 5 个字段键。
- 搜索 `?q=xxx` 不再匹配这 5 个字段的文本内容。

---

## 3. 脚本 / 文档 / SKILL 同步

### 3.1 `scripts/customer_materials_weekly.py`

- 创建 material 的 payload 里移除 `summary_markdown: None` 和 `insights_markdown: None` 两行（见 `customer_materials_weekly.py:220-221`），让 payload 里只保留 `raw_facts_markdown` 这一正文字段。
- 不需要重跑一次脚本验证数据；当前 DB 是空仓库或测试数据，迁移 SQL 兜底即可。

### 3.2 `task_center/TASK_CENTER_API_FOR_AGENTS.md`

- 所有 `summary_markdown` / `insights_markdown` / `candidate_markdown` / `raw_source_markdown` / `review_note` 字段描述、示例 curl、字段表、PATCH 样例**全部删除**。
- `10.6 字段说明` 表：`新模型字段（主字段）` 区只留 `raw_facts_markdown`；`旧字段（兼容层）` 区移除 5 个，保留 `project` / `material_date` / `source_type` / `source_refs` / `task_id` / `archived_at`。
- `10.9 上传 NotebookLM 的拼接模板`：已是单段式，无变化。
- 顶部 "修订要点" 摘要追加一条："2026-05-04 Phase 2：`summary/insights/candidate/raw_source/review_note` 五字段物理删除，唯一正文字段 = `raw_facts_markdown`"。

### 3.3 `skills/task-center-customer-knowledge/SKILL.md`

- 全文搜索并**删除**对上述 5 个字段的任何提及。
- §5.4（`raw_facts_markdown` 拼接规则）保留。
- §6（移动端审核页）章节重写，反映新 "知识" Tab + 事实 / 材料子 Tab 结构。
- 顶部"核心原则"第 5 条"TaskCenter 不调 LLM"保留；第 7 条"后端不派生 fact"保留。

---

## 4. 移动端「知识」Tab（`task_center/mobile_frontend`）

### 4.1 `types.ts`

#### 4.1.1 `Task` 补字段

```ts
export interface Task {
  // 原有字段保留
  source_type?: string | null;      // 新增
  customer_id?: number | null;      // 新增
  project_id?: number | null;       // 新增
  area?: string | null;             // 新增
}
```

#### 4.1.2 `CustomerMaterial` 重写

删除旧字段 + 加新字段：

```ts
export interface CustomerMaterial {
  id: number;
  title: string;
  status: CustomerMaterialStatus;
  created_at: string;
  updated_at: string;
  archived_at?: string | null;

  // v2 主字段
  raw_facts_markdown?: string | null;
  customer_id?: number | null;
  project_v2_id?: number | null;
  review_batch_id?: number | null;
  material_type?: string | null;        // 'period_summary' 等
  period_start?: string | null;
  period_end?: string | null;
  generation_meta?: Record<string, unknown> | null;

  // 兼容字段
  project?: string | null;
  material_date?: string | null;
  source_type?: string;
  source?: string;
  source_refs?: Record<string, unknown>;
  value_types?: string[];
  task_id?: number | null;
}

// 移除：raw_source_markdown, candidate_markdown, summary_markdown, insights_markdown, review_note
```

#### 4.1.3 新增 `ReviewBatch`

```ts
export interface ReviewBatch {
  id: number;
  batch_type: string;                   // 'weekly_customer_summary'
  title: string;
  period_start?: string | null;
  period_end?: string | null;
  status: 'pending' | 'partial' | 'approved' | 'uploaded' | string;
  material_count: number;
  created_by?: string | null;
  created_at: string;
  updated_at: string;
}
```

#### 4.1.4 新增 `Fact`

```ts
export type FactStatus = 'draft' | 'confirmed' | 'rejected';

export interface Fact {
  id: number;
  title: string;
  raw_markdown: string;
  fact_date?: string | null;
  status: FactStatus;
  source_type: string;
  value_types: string[];
  customer_id?: number | null;
  project_id?: number | null;
  task_id?: number | null;
  created_at: string;
  updated_at: string;
}

export interface FactFilters {
  customer_id?: number;
  project_id?: number;
  task_id?: number;
  status?: FactStatus | '';
  source_type?: string;
  q?: string;
  from?: string;
  to?: string;
  limit?: number;
}

export interface UpdateFactPayload {
  title?: string;
  raw_markdown?: string;
  fact_date?: string | null;
  status?: FactStatus;
  value_types?: string[];
}
```

#### 4.1.5 `CustomerMaterialPayload` / `UpdateCustomerMaterialPayload`

- 移除 5 个旧字段
- 保留 `raw_facts_markdown` 作为主编辑字段
- 移除 `createCustomerMaterial` 的入口（下见 §4.2）

### 4.2 `api.ts`

- `normalizeCustomerMaterial` 按新 schema 改写，读取新字段。
- `normalizeTask` 补 `source_type` / `customer_id` / `project_id` / `area`。
- **新增**：
  - `getReviewBatches(filters?)` → `GET /api/review-batches`
  - `getReviewBatch(id)` → `GET /api/review-batches/:id`
  - `getReviewBatchMaterials(id)` → `GET /api/review-batches/:id/customer-materials`
  - `getMaterialFacts(materialId)` → `GET /api/customer-materials/:id/facts`
  - `markMaterialUploaded(id)` → `POST /api/customer-materials/:id/mark-uploaded`（移动端本轮不调用，保留 API 给未来/主代理共用）
  - `getFacts(filters?)` → `GET /api/facts`
  - `getFact(id)` → `GET /api/facts/:id`
  - `updateFact(id, payload)` → `PATCH /api/facts/:id`
  - `deleteFact(id)` → `DELETE /api/facts/:id`
- **删除**：`createCustomerMaterial`（移动端不再支持手动新建 material）
- **保留**：`archiveCustomerMaterial` / `updateCustomerMaterial`（只用于 patch status / raw_facts_markdown）

### 4.3 `App.tsx` 结构改造

#### 4.3.1 底部导航

- `TabKey` type：`'today' | 'plan' | 'board' | 'knowledge' | 'history'`（`materials` → `knowledge`）
- 导航项标签：`'材料'` → `'知识'`，icon 保持 `◇` 或换成更贴"事实 + 材料"的符号（可选）
- URL hash 兼容：旧的 `#tab=materials` → 重定向到 `#tab=knowledge`（`parseHash` 里加一个 fallback）

#### 4.3.2 知识 Tab 顶部 segmented

- 新增 state：`knowledgeMode: 'materials' | 'facts'`，默认 `'materials'`，存到 URL hash（镜像 `boardMode`）
- UI 复用看板的分段样式，className 改为 `knowledge-segmented` / `knowledge-segment`
- CSS：在 `styles.css` 追加对应 class，或直接复用 `board-segmented`

#### 4.3.3 材料子 Tab

- 数据源：`getReviewBatches()` + 每个 batch 的 `getReviewBatchMaterials(id)`（可一次性 `getCustomerMaterials({limit:300})` 后前端按 `review_batch_id` 分组，避免 N+1；**推荐后者**以减少请求）
- 未归 batch 的 material（旧数据 / `review_batch_id=null`）：归入"未归批次"分组，按 `project` 或 `customer` 二次分组
- batch header：title + period（`YYYY-MM-DD ~ YYYY-MM-DD`）+ status pill + `N 份材料`
- material 卡片：
  - 行内**只展示**：title、customer/project、period 或 material_date、status pill、`raw_facts_markdown` 前 120 字预览
  - **无任何按钮**，整卡可点击进详情 sheet
- 顶部筛选：保留 status 筛选（全部 / pending / approved / skipped / uploaded）

#### 4.3.4 材料详情 Sheet（重写旧 `MaterialEditorSheet`）

- 主体：
  - 大 `<textarea>` 绑定 `raw_facts_markdown`（12 行起，随内容自适应）
  - 顶部只读信息条：客户（`customer_id` → customer name）/ 项目 / `period_start ~ period_end` / 创建时间 / 更新时间 / 状态 pill
  - 小字提示条：`"本批材料只展示原始事实，简要纪要 / 洞察由 NotebookLM 在上传后生成"`（父 Plan §6.3 要求）
- 关联 Facts 面板（在正文下方）：
  - 调 `getMaterialFacts(id)` 拿列表
  - 每条只读展示：title / fact_date / 前 80 字 preview / status pill
  - 点击 → 跳 fact 详情 sheet（第 4.3.6 节），**从 fact 详情关闭时回到 material 详情**（stack 导航）
- 动作按钮区（底部 sticky）：
  - `保存`（PATCH `raw_facts_markdown`）
  - `通过`（PATCH status=approved）
  - `跳过`（PATCH status=skipped）
  - `归档`（DELETE）
  - **不放"已传"按钮**（按用户点 5 要求）
- 关闭按钮保留

#### 4.3.5 事实子 Tab

- 数据源：`getFacts({ limit: 300 })`
- 顶部筛选：status（全部 / draft / confirmed / rejected）+ 客户筛选（可选，如果 customers 数量多）
- 分组：按 customer_id 分组，组标题 = customer name（或"未归类"）；组内按 `fact_date desc` 排序
- fact 卡片（行内）：
  - title + customer/project + `fact_date` + `source_type` badge + status pill + `raw_markdown` 前 100 字预览
  - 若 `value_types` 非空，显示 chip 行
  - **无任何按钮**，整卡可点击进 fact 详情 sheet

#### 4.3.6 事实详情 Sheet（新建）

- 主体：
  - 大 `<textarea>` 绑定 `raw_markdown`（10 行起）
  - 小字段行：`title` 输入框 + `fact_date` datetime-local + `value_types` chip 多选（复用 material editor 的 `materialValueTypeOptions`）
  - 只读信息：客户 / 项目 / `source_type` badge / 关联 task（点击 → 跳 task 详情 sheet）
- 动作按钮区（底部 sticky）：
  - `保存`（PATCH raw_markdown / title / fact_date / value_types）
  - `标为 Draft` / `标为 Confirmed` / `标为 Rejected`（PATCH status；当前 status 按钮置灰）
  - `删除`（DELETE，带 `window.confirm` 二次确认）
- 关闭按钮保留

#### 4.3.7 任务详情 Sheet 微调

- 在 `DetailItem` 列里新增一项："来源"→ 展示 `task.source_type`（若非空）
- 不新增编辑能力，只读展示

#### 4.3.8 其它清理

- 删除 `MaterialEditorSheet` 里对 `candidate_markdown` / `raw_source_markdown` / `review_note` / `material_date` 输入框的所有 JSX 和 state
- 删除 `MaterialFormState` 里相应字段
- 删除 `materialValueTypeOptions` 的用法除非 fact 详情 sheet 还要用（这里仍在 fact 里复用）
- 删除 `源类型` 下拉里的 `task_completion` 选项（新流程不再使用）
- 保留 `materialStatusLabelMap` / `MaterialStatusPill`（仍在卡片里展示）

### 4.4 `styles.css`

- 追加 `.knowledge-segmented` / `.knowledge-segment` / `.knowledge-segment-active` 等（或直接复用 board 的 class）
- material 详情 sheet 的关联 facts 面板需要新样式（`.material-facts-panel` / `.material-fact-row`）
- fact 详情 sheet 需要 `.fact-detail-sheet` / `.fact-meta-row` 等
- 可以在现有 `.material-editor-sheet` 基础上派生，保持视觉一致

### 4.5 URL Hash 路由兼容

- `parseHash` 扩展：
  - `tab=materials` → 自动重定向到 `tab=knowledge&mode=materials`
  - `tab=knowledge&mode=facts` 支持直接进事实子 Tab
- `buildHash` 逻辑同步

---

## 5. OpenClaw SKILL 细节确认（不改文件，只验证）

按用户点 5："移动端不做已传按钮 → 上传唯一路径 = 飞书回复 → 主代理处理"。

需要验证 `skills/task-center-customer-knowledge/SKILL.md` 已覆盖：

- §3（两步走写 fact）
- §5（周期材料生成脚本）
- §"审核回复约定"或同义段：`审核完成 #N` / `审核完成 batch #N` 两种指令格式
- 主代理处理流程：读 approved → 拼 markdown（单段模板）→ nblm upload → `POST /mark-uploaded`

若缺失，本 Plan §3.3 顺手补齐。**不改 feishu-task SKILL、不改 nblm SKILL**。

---

## 6. 实施任务拆分

### 6.1 单代理执行（推荐）

本 Plan 可由单个 Cascade session 完整执行，无需拆子代理——工作量中等（约 800 行代码变更，集中在 `App.tsx` + 后端几个点），推荐顺序见 §9。

### 6.2 可选：双代理拆分

- **R1：后端 + 脚本 + 文档**（§2 / §3）
- **R2：移动端**（§4）
- R1 和 R2 之间只有一个依赖点：R2 的 `normalizeCustomerMaterial` 需要 R1 的字段删除先生效，否则 API 响应里会多带 5 个字段（不影响功能，但 TypeScript 类型会严格化）。实际可以并行，R2 先用 optional 字段占位。

---

## 7. 验收清单

### 7.1 后端

- [ ] `models.py` / `schemas.py` / `main.py` 5 个字段全部移除，无残留引用
- [ ] `ensure_schema_compatibility` 迁移代码跑一次，DB 里 `customer_materials` 表不再有这 5 列（`.schema customer_materials` 验证）
- [ ] 搬迁逻辑对测试数据正确：凑一行老 material（raw_facts 为空、candidate 非空），跑迁移后 raw_facts 被填上
- [ ] `python3 -m py_compile` 通过
- [ ] 后端起服务 `uvicorn` 不报错
- [ ] `curl -X POST /api/customer-materials` 带 `raw_facts_markdown` 正常
- [ ] `curl -X POST /api/customer-materials` 带旧字段（如 `summary_markdown`）→ 静默忽略，不报 422
- [ ] `curl GET /api/customer-materials/1` 响应**不包含** 5 个字段的 key
- [ ] `curl GET /api/customer-materials?q=xxx` 搜索仍然可用

### 7.2 脚本

- [ ] `customer_materials_weekly.py` 移除 `summary_markdown: None` / `insights_markdown: None` 两行
- [ ] `python3 -m py_compile` 通过
- [ ] 手动跑一次，输出 JSON 合法；若无 fact 输出 `no_facts_this_week`
- [ ] 若有 fact：检查创建的 material 只含 `raw_facts_markdown` 非空

### 7.3 文档 / SKILL

- [ ] `TASK_CENTER_API_FOR_AGENTS.md` 里 grep 不到被删 5 字段
- [ ] `skills/task-center-customer-knowledge/SKILL.md` 里 grep 不到被删 5 字段
- [ ] 两份文档顶部修订要点更新

### 7.4 移动端

- [ ] `npm run build` 无 TS 错误
- [ ] `npm run dev` 启动 5174 端口
- [ ] 底部 Tab 显示"知识"而非"材料"
- [ ] 知识 Tab 顶部分段控件可切换"事实 / 材料"
- [ ] 材料子 Tab：看到 batch 分组，点卡片进详情 sheet
- [ ] 材料详情 sheet：大 textarea 可编辑 raw_facts_markdown，保存后列表刷新
- [ ] 材料详情 sheet：通过 / 跳过 / 归档按钮可用；**无"已传"按钮**
- [ ] 材料详情 sheet：关联 facts 面板列出 fact，点击跳 fact 详情
- [ ] 事实子 Tab：按客户分组，卡片点击进 fact 详情
- [ ] 事实详情 sheet：可编辑 raw_markdown / title / fact_date / value_types
- [ ] 事实详情 sheet：状态切换三按钮、删除按钮可用
- [ ] 任务详情 sheet：展示 `source_type`（若非空）
- [ ] **卡片行内没有任何操作按钮**（material / fact 一致）
- [ ] URL `#tab=materials` 自动跳到 `#tab=knowledge&mode=materials`

### 7.5 端到端（需要真实数据）

- [ ] 手建一条 fact（`confirmed`，本周）
- [ ] 跑 `customer_materials_weekly.py`，产生 1 batch + 1 material
- [ ] 移动端打开知识 Tab，看到 batch → material
- [ ] 详情页改正 raw_facts_markdown 一个错别字 → 保存
- [ ] 点"通过" → status 变 approved
- [ ] 飞书回复"审核完成 #N" → 主代理读到 approved → nblm upload → `POST /mark-uploaded`（此步由主代理执行）
- [ ] 移动端看到 status 变 uploaded

---

## 8. 风险和已知问题

### 8.1 数据丢失风险

- 搬迁逻辑的优先级是 `candidate_markdown > raw_source_markdown > summary_markdown > insights_markdown`。如果一条 material **同时**有 `candidate_markdown` 和 `summary_markdown` 非空，`summary_markdown` 的内容会丢。
- 缓解：跑迁移前做一次 `sqlite3 backup`。
- 实际影响评估：测试数据为主，生产数据极少；可接受。

### 8.2 其它客户端耦合

- 已 grep 桌面前端 `task_center/frontend/src/` → **零引用** 5 字段，无回归风险。
- 未检查 `task_center/chat/` / `task_center/docs/` —— 实施前需要再 grep 一次兜底。

### 8.3 Agent 写入行为

- agent 通过 API 写 material 时若仍带这 5 字段 → Pydantic `extra='ignore'` 默认静默忽略，不会 422。SKILL 文档修订后 agent 应停止发送。

### 8.4 SQLite DROP COLUMN 版本

- 项目本机 SQLite 3.45.1，支持 3.35+ 的 DROP COLUMN。若将来部署到 3.35 以下环境需重写为"新建表 + copy + drop"模式。

### 8.5 移动端 state 复杂度

- 本轮 App.tsx 会增加 ~300 行（knowledgeMode + fact state + fact editor sheet）。不拆组件会继续膨胀（已 2482 行）。本 Plan **不强制拆组件**，但建议执行时把 `FactEditorSheet` / `FactRow` / `MaterialFactsPanel` 抽成独立函数组件（仍在同文件），减轻视觉负担。

### 8.6 迁移幂等

- DROP COLUMN 重复执行会抛 `OperationalError: no such column`，必须 try/except 吞掉。已在 §2.4 代码中注明。

---

## 9. 推荐执行顺序

1. **Snapshot DB**：`cp backend/data/task_center.db backend/data/task_center.db.bak.2026-05-04-phase2`（防御性）
2. **后端字段清理**（§2）：改 models / schemas / main，写迁移，起服务确认健康
3. **脚本清理**（§3.1）：改 2 行，py_compile
4. **跑一次后端迁移**：起 uvicorn 自动触发 `ensure_schema_compatibility`，用 `sqlite3` 确认列已删
5. **API 文档 + SKILL 清理**（§3.2 / §3.3 / §5）
6. **移动端 types/api**（§4.1 / §4.2）：先改类型和 api，TS 编译
7. **移动端 App.tsx：Tab rename + segmented**（§4.3.1 / §4.3.2）
8. **移动端：材料子 Tab 列表 + 详情 sheet 重写**（§4.3.3 / §4.3.4）
9. **移动端：事实子 Tab 列表 + fact 详情 sheet 新建**（§4.3.5 / §4.3.6）
10. **移动端：任务详情 source_type 展示**（§4.3.7）
11. **样式补齐**（§4.4）
12. **URL hash 兼容**（§4.5）
13. **完整验证**（§7）
14. **Commit**：分 3 个 commit —— 后端清理、脚本 / 文档、移动端（后两个可在对应 git 仓库分别提交）

---

## 10. 一个待你二次确认的点

本 Plan §1.1 把 `review_note` 也列入物理删除，但你的原话只明确砍了 `summary_markdown` / `insights_markdown` / `candidate_markdown` 三个。推理依据：

- 用户点 3 已同意前端删 `review_note`
- 新流程审核动作只推 status，不写备注
- 保留物理列但前端不用 = 无价值死列

若你保留 `review_note`（将来想记 skip 原因），本 Plan §1.1 / §2 / §7 删字段清单改为 4 个，其它不变。

**请在 Plan 执行前拍板此点**。
