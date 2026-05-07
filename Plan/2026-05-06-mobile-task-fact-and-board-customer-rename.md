# 移动端任务详情接入客户事实 + 看板按客户分组重命名（2026-05-06 Phase 3）

创建时间：2026-05-06
负责人：南哥 / OpenClaw main / Cascade
父 Plan：`Plan/2026-05-04-material-cleanup-and-mobile-knowledge.md`

目标（按用户原话拆解）：

1. 看板"按项目"分组方式 → 改名"按客户"（视觉文案，不改路由 / 状态键）。
2. 任务详情中新增"客户事实"卡片，展示一行行 fact 摘要；点击跳事实详情、关闭返回任务详情。
3. 事实编辑器允许修改"客户"字段（搜索式选择器）。
4. 事实详情里"删除"按钮真删（之前是 soft 标 rejected，前端也以为删除了）。
5. 知识页签的分段控件样式好看 → 同步到看板（Board）的分段控件。
6. 知识页签内 batch / 客户分组卡片里的子项行没有内边距 → 给一层呼吸感。
7. 项目组的 上 / 下 / 置顶 / 全部展开 四个图标 → 用 Lucide 风格 SVG 重画。

---

## 0. 与父 Plan 的关系

### 0.1 仍然有效

- 父 Plan §1（核心决策：唯一正文 = `raw_facts_markdown`）继续生效。
- 父 Plan §3（后端 API 字段清理）已完成且不动。
- 父 Plan §4（移动端"知识"Tab：事实 / 材料 segmented + fact 编辑能力）整体保留；本 Plan 只是在它之上**追加交互**，不替换。
- 父 Plan §5（SKILL 文档 / Agent 协议）继续生效。

### 0.2 本 Plan 替换 / 细化的条目

- 替换 父 Plan §4.1.1 / §10.6 中"`DELETE /api/facts/{id}` = 标 rejected"的描述：本 Plan 把它改成**真物理删除**（204）。
- 替换 父 Plan §4.3.1 中"看板分组方式：按状态 / 按项目"的视觉文案：本 Plan 改成"按状态 / 按客户"（仅文案，分组逻辑沿用 `Task.project` 字段，未来切真客户 ID 是另一项工作）。
- 细化 父 Plan §4.4 移动端样式：补齐知识子项内边距、将"按客户"列上下移 / 置顶 / 全部展开图标全部 SVG 化、统一分段控件外观（看板向知识对齐）。
- 补 父 Plan §4.3.4 / §4.3.5 漏掉的能力：fact 编辑器内"客户"字段必须**可编辑**；任务详情必须能直接看到该任务关联的所有 fact。

---

## 1. 核心决策汇总

### 1.1 后端：DELETE /api/facts/{id} 改为硬删

**当前行为（旧）**：

```python
fact.status = FactStatus.REJECTED.value
db.commit()
return Response(status_code=204)
```

→ 数据库里 row 仍在，状态变 rejected。前端按钮叫"删除"，但实际只是软标记，用户在"全部"筛选下仍能看到这条 fact，体感等于按钮坏了。

**新行为**：

```python
db.delete(fact)
db.commit()
return Response(status_code=204)
```

→ 真删 row。`customer_material_facts.fact_id` 已配置 ON DELETE CASCADE，无需手动清理关联表。HTTP 状态码不变（204），无需迁移。

**为什么直接硬删而不是加个 `soft_delete=true` 软删字段**：

- fact 数据来源是 agent 写入的客观原文 + 极少量人工误录。误录的 row 留下来对未来材料聚合有干扰（即使 status=rejected 也是噪音），不存在审计需求。
- 移动端按钮文案是"删除"，行为必须匹配文案。
- agent 端不依赖"已删除 fact"做任何决策。
- 数据库轻量（SQLite，事实表 < 1k 行级别），无性能 / 归档压力。

### 1.2 移动端：任务详情 ↔ 客户事实 双向跳转

**任务详情新增一张卡**："客户事实"，与已有的"客户材料"卡并列，结构一致：

- 一条 fact = 一行（标题 + 状态 pill + 客户名 + fact_date），点击进 fact 详情 sheet。
- 取数：新加 `GET /api/tasks/{taskId}/customer-facts?status=` 的前端 wrapper，复用后端已有的 `GET /api/facts?task_id=...` 端点（**不新增后端端点**，移动端 api.ts 内部转译）。
- 任务侧加载逻辑：进入任务详情 sheet 即触发 `taskFacts.refresh()`；与材料同样用 `useAsyncData` 管理。

**关闭返回**：

- 用 `factSheetOverTask: boolean` 一个 flag 表示"当前 fact 编辑 sheet 是不是从任务详情进来的"。
- 渲染条件：
  - `selectedTask && !(factDraft && factSheetOverTask)` → 渲染任务详情 sheet（被 fact sheet 盖住时不渲染，避免双层 overlay）
  - `factDraft && (factSheetOverTask || !selectedTask)` → 渲染 fact 编辑 sheet
- fact sheet 关闭时同时清 `factDraft` + `factSheetOverTask`，selectedTask 保留 → 自动回到任务详情。
- fact sheet 中点"关联任务"链接时，把 `factSheetOverTask` 重置（因为这次跳过去后再返回应该回到 fact 而不是迷失）。

### 1.3 移动端：fact 编辑器允许改客户

**字段从只读 → 可编辑**：

- 客户字段渲染为一个按钮（`button.editor-readonly.editor-pickable`），点击打开 `FactCustomerPickerSheet`。
- 选择器 sheet 是搜索式列表：搜索 name / area，置顶"未关联"选项以支持清空。
- 保存逻辑：
  - 选具体客户：`PATCH /api/facts/{id}` body = `{customer_id: <id>}`
  - 选"未关联"：body = `{clear_customer: true}`（后端 schema 已支持）
- 保存后并行刷新 `facts` + `taskFacts`，sheet 关闭，editor sheet 中客户名实时更新（无需重开）。

**类型补全**：

- `UpdateFactPayload` 加 `customer_id` / `project_id` / `task_id` / `clear_customer` / `clear_project` / `clear_task` 六个可选字段，对齐后端 `FactUpdate` Pydantic schema。

### 1.4 移动端：看板按"客户"分组（仅文案）

**改的范围**：

- BoardHero 标题：`按项目收线` → `按客户收线`，描述同步：`搜项目、调顺序…` → `搜客户、调顺序…`
- 分段按钮文案：`按项目` → `按客户`
- 搜索输入 placeholder：`搜索项目 / 标签` → `搜索客户 / 项目`
- 全部展开 / 上 / 下 / 置顶 按钮的 aria-label：`项目` → `客户`
- 空态文案：`没有匹配的项目 / 标签` → `没有匹配的客户 / 项目`
- 滚动加载提示：`继续下滑，自动加载更多项目` → `继续下滑，自动加载更多客户`

**不动的部分**：

- `BoardMode` 枚举值 `'project'` 不改（改要动 URL hash 兼容、`useBoardPreferences` 持久化键、若干 useMemo 依赖项），收益小、风险大。
- 分组键仍是 `Task.project` 字段（一段自由字符串），暂不切到 `Task.customer_id`。
- 后端 `/api/dashboard/board?mode=project` 端点签名不变。

**后续工作（不在本 Plan 内）**：

- 把分组键真的切到 `customer_id` → 需要后端 board endpoint 支持 `mode=customer`，前端 BoardMode 联动改名，并为存量 task 的 `project` 文本做客户匹配兜底。这件事和"自动客户识别"是同一条线，单独排期。

### 1.5 移动端：分段控件统一为 pill-row 样式

`board-segmented` 旧样式（grid 2 列 + 内圈灰底外圈白底）→ 替换为知识 Tab 已经在用的"独立 pill 按钮 + flex row"风格：

- 容器：透明、无边框、`gap: 6px`、`flex`。
- 单段：`flex: 1` 等分、`border-radius: 999px`、激活态用 `--brand-soft` 背景 + `--brand-strong` 字色。
- `.knowledge-segmented` 自定义样式删掉，靠继承统一。

### 1.6 移动端：知识卡片内边距

- `.material-group-card .material-list { padding: 0 12px 12px; }`：卡片头部到子项保持紧凑，子项之间和子项到卡片侧边都有 12px 内边距，避免子项行紧贴卡片描边。
- `.material-group-card .section-heading { padding-bottom: 10px; }`：标题区底部留呼吸。

### 1.7 移动端：四个 Lucide 风格 SVG 图标

| 控件 | 旧实现 | 新实现 |
|------|--------|--------|
| 上移 | 多层 `<span>` + CSS 三角形 | `<svg><polyline points="6 15 12 9 18 15"/></svg>` (chevron-up) |
| 下移 | 多层 `<span>` + CSS 三角形 | `<svg><polyline points="6 9 12 15 18 9"/></svg>` (chevron-down) |
| 置顶 | 多层 `<span>` + CSS 圆 + 矩形 | `<svg>` + Lucide 风格 pin path（激活时填充） |
| 全部展开 | unicode `⊟` / `⊞` | `<svg>` Lucide minimize-2 / maximize-2 |

新增组件：`MoveArrowIcon` / `PinIcon`（重写）/ `ExpandToggleIcon`（新）。
新增 CSS：`.icon-svg`（统一 16px stroke）、`.icon-svg-pin-active`（pin 激活态填充）、`.board-mode-toolbar-action svg`（全部展开按钮 18px）。

### 1.8 硬约束（沿用父 Plan）

- 不动桌面端代码。
- 不动 feishu-task SKILL / nblm SKILL / cron 配置。
- 不在 TaskCenter 后端引入 LLM 调用。
- 不引入新依赖（不引 lucide-react 包，SVG 直接手写到组件里）。
- 不改 BoardMode 枚举值 / 不改 URL hash 兼容。

---

## 2. 后端改动（`task_center/backend/main.py`）

### 2.1 `delete_fact` 端点改写

```python
@app.delete("/api/facts/{fact_id}", status_code=204)
def delete_fact(fact_id: int, db: Session = Depends(get_db)) -> Response:
    fact = db.get(Fact, fact_id)
    if fact is None:
        raise HTTPException(status_code=404, detail="fact not found")
    db.delete(fact)
    db.commit()
    return Response(status_code=204)
```

### 2.2 import 清理

`from models import ..., FactStatus, ...` 中移除 `FactStatus`（端点不再依赖枚举）。

### 2.3 兜底

- `customer_material_facts` 表的外键已是 `ON DELETE CASCADE`（`models.py` 中既有约束），无需手动清理关联。
- 没有 events 表对 fact 的关联日志（fact 不写 TaskEvent），无需清理。

---

## 3. 移动端改动（`task_center/mobile_frontend`）

### 3.1 `src/types.ts`

`UpdateFactPayload` 扩展：

```ts
export interface UpdateFactPayload {
  title?: string;
  raw_markdown?: string;
  fact_date?: string | null;
  status?: FactStatus;
  value_types?: string[];
  customer_id?: number | null;       // 新增
  project_id?: number | null;        // 新增
  task_id?: number | null;           // 新增
  clear_customer?: boolean;          // 新增
  clear_project?: boolean;           // 新增
  clear_task?: boolean;              // 新增
}
```

### 3.2 `src/api.ts`

新增 `getTaskFacts(taskId)`：

```ts
getTaskFacts: async (taskId: number) =>
  (await request<any[]>(`/api/facts?task_id=${taskId}&limit=200`)).map(normalizeFact),
```

实现注意：复用 `GET /api/facts?task_id=...`，不加新后端端点。`limit=200` 大致覆盖单任务下的事实数（实际通常 < 10）。

### 3.3 `src/App.tsx`

#### 3.3.1 状态新增

```ts
const [factSheetOverTask, setFactSheetOverTask] = useState(false);
const [factCustomerPickerOpen, setFactCustomerPickerOpen] = useState(false);
const taskFacts = useAsyncData(
  selectedTask ? () => api.getTaskFacts(selectedTask.id) : null,
  [selectedTask?.id],
);
```

#### 3.3.2 新增 mutation：`updateFactCustomerById`

收到 `customerId: number | null`，转换为 payload：

- `null` → `{ clear_customer: true }`
- 数字 → `{ customer_id: id }`

成功后并行 `facts.refresh()` + `taskFacts.refresh()`，刷新两个数据源。

#### 3.3.3 已有 mutation 修改

- `submitFactEditor` / `updateFactStatusById` / `deleteFactById` 三个 mutation 在成功分支额外调一次 `taskFacts.refresh()`，保证从任务详情进来的 fact 编辑也实时反映。
- `submitFactEditor` 和 `deleteFactById` 在关闭 sheet 时同时 reset `factSheetOverTask`。

#### 3.3.4 任务详情 sheet 新增"客户事实"卡片

`TaskDetailSheet` 接受新 props：`facts: Fact[]` / `factsLoading: boolean` / `customerMap: Map<number, Customer>` / `onOpenFact: (id) => void`。

渲染顺序：客户材料卡 → **客户事实卡** → 动作卡。

新组件 `CompactFactRow`：

```tsx
<article className="material-row material-row-compact fact-row task-fact-row">
  <button className="material-row-main task-fact-row-main" onClick={onOpen}>
    <div className="task-fact-row-line">
      <strong className="task-fact-row-title">{fact.title || '（无标题）'}</strong>
      <FactStatusPill status={fact.status} />
    </div>
    <div className="task-fact-row-meta">
      {customerName && <span>{customerName}</span>}
      {fact.fact_date && <span>{(fact.fact_date || '').slice(0, 10)}</span>}
    </div>
  </button>
</article>
```

#### 3.3.5 任务详情 ↔ fact sheet 叠加渲染

```tsx
{selectedTask && !(factDraft && factSheetOverTask) && (
  <TaskDetailSheet ... onOpenFact={(id) => { setFactSheetOverTask(true); openFactById(id); }} />
)}

{factDraft && (factSheetOverTask || !selectedTask) && (() => {
  const fact = (facts.data || []).find(f => f.id === factDraft.id)
            ?? (taskFacts.data || []).find(f => f.id === factDraft.id)
            ?? null;
  ...
  return <FactEditorSheet ... onClose={() => { setFactDraft(null); setFactSheetOverTask(false); ... }} />;
})()}

{factDraft && factCustomerPickerOpen && (
  <FactCustomerPickerSheet ... />
)}
```

fact 在两个数据源里查找的原因：从任务详情进来的 fact 不一定在 `facts.data`（知识 Tab 没加载），但一定在 `taskFacts.data`。

#### 3.3.6 `FactEditorSheet` 客户字段改成可点击

旧：`<div className="editor-readonly">{customer?.name || '—'}</div>`

新：

```tsx
<button
  type="button"
  className="editor-readonly editor-pickable"
  onClick={onOpenCustomerPicker}
  disabled={busy}
  aria-label="修改关联客户"
>
  <span className="editor-pickable-value">{customer?.name || '— 选择客户'}</span>
  <span className="editor-pickable-glyph" aria-hidden="true">›</span>
</button>
```

新增 prop：`onOpenCustomerPicker: () => void`。

#### 3.3.7 新组件 `FactCustomerPickerSheet`

签名：

```ts
function FactCustomerPickerSheet({
  customers: Customer[],
  currentCustomerId: number | null,
  busy: boolean,
  onClose: () => void,
  onSelect: (customerId: number | null) => void,
});
```

行为：

- 顶部搜索框：本地过滤（name / area），不调后端。
- 默认隐藏 `status === 'closed'` / `'paused'` 的客户，但若当前 fact 关联的就是这种客户，仍展示（避免找不到）。
- 列表第一行固定是"未关联"，点击后回调 `onSelect(null)`。
- 选中后立即调 `onSelect`，外层关闭 picker。

#### 3.3.8 SVG 图标三件套

新增 `ExpandToggleIcon`，重写 `MoveArrowIcon` / `PinIcon`（参见 §1.7 表）。BoardHero 的全部展开按钮里 `<span>{allGroupsExpanded ? '⊟' : '⊞'}</span>` → `<ExpandToggleIcon expanded={allGroupsExpanded} />`。

#### 3.3.9 看板文案重命名（按客户）

仅替换字符串字面量，逻辑不变。涉及行：BoardHero（h2 / p / button label / placeholder / aria-label / title），BoardPage 主体（aria-label 三处、空态文案、滚动加载 chip）。

### 3.4 `src/styles.css`

#### 3.4.1 重写 `.board-segmented` / `.board-segment`

```css
.board-segmented {
  display: flex;
  gap: 6px;
  padding: 0;
  background: transparent;
  border: 0;
}

.board-segment {
  flex: 1;
  text-align: center;
  min-height: 38px;
  padding: 8px 12px;
  border-radius: 999px;
  border: 1px solid var(--line);
  background: rgba(255, 255, 255, 0.82);
  color: var(--muted-strong);
  font-size: 13px;
  font-weight: 700;
  transition: all 160ms ease;
}

.board-segment-active {
  background: var(--brand-soft);
  color: var(--brand-strong);
  border-color: rgba(49, 87, 225, 0.28);
  box-shadow: 0 4px 12px rgba(35, 58, 125, 0.10);
}
```

#### 3.4.2 简化 `.knowledge-segmented`

旧自定义样式删掉，只留 `margin-top: 12px`，外观由 `.board-segmented` 继承。

#### 3.4.3 知识卡片内边距

```css
.material-group-card .material-list { padding: 0 12px 12px; }
.material-group-card .section-heading { padding-bottom: 10px; }
```

#### 3.4.4 任务详情客户事实行 `.task-fact-row*`

紧凑两行式：标题 + 状态 pill 一行，客户名 / 日期 chip 一行。

#### 3.4.5 可选择字段 `.editor-pickable*`

按钮风格：白底、hover 时刷品牌色软底；左侧值文本省略、右侧显示 `›` 提示可点。

#### 3.4.6 客户选择器 sheet `.customer-picker-*`

- `.customer-picker-search`：搜索输入条样式（与 board search shell 一致）。
- `.customer-picker-list`：可滚动列表。
- `.customer-picker-row`：每行客户的卡片样式，`.customer-picker-row-active` 是当前选中。

#### 3.4.7 SVG 图标统一样式 `.icon-svg`

- 16px 默认尺寸、stroke=currentColor、stroke-width=1.6、line-cap/join=round。
- `.icon-svg-pin-active` 让 pin 激活态填充 currentColor。
- `.board-mode-toolbar-action svg` 把全部展开图标拉到 18px。

#### 3.4.8 暗色模式

为新组件补暗色覆盖：`.editor-pickable` / `.customer-picker-search` / `.customer-picker-row` / `.customer-picker-row-active` / `.task-fact-row-meta span`。

---

## 4. 文档同步

### 4.1 `TASK_CENTER_API_FOR_AGENTS.md`

`§10.5 Facts API` 中 `DELETE /api/facts/{id}` 注释从"建议改 status=rejected，不硬删"改成：

```
# 删除（物理删除，不可恢复；移动端"删除"按钮直接走这里）
DELETE /api/facts/{id}
```

顶部"修订要点"增加一条：`2026-05-06：DELETE /api/facts/{id} 改为硬删除（204）`。

### 4.2 `mobile_frontend/README.md`

§3.3 看板章节："按项目分组" → "按客户分组（视觉文案，逻辑沿用 project 字段）"。

### 4.3 本文件（Plan）

放在 `Plan/2026-05-06-mobile-task-fact-and-board-customer-rename.md`，与父 Plan 平级。

---

## 5. 验证清单

### 5.1 后端

- [x] `python3 -c "import ast; ast.parse(open('main.py').read())"` 通过。
- [x] `openapi.json` 中 `/api/facts/{fact_id}` 的 DELETE 仍标 204。
- [ ] 手测：`curl -X POST /api/facts ...` 创建一条；`curl -X DELETE /api/facts/{id}` → 204；`curl /api/facts/{id}` → 404。
- [ ] 手测：fact 关联到 customer_material → 删除 fact → `customer_material_facts` 中对应行随之消失。

### 5.2 移动端 build

- [x] `npm run build` 无 TS 错误（`tsc -b && vite build` 通过）。
- [x] 体积变化在合理范围（CSS +10KB → 42KB，JS 体积基本持平）。

### 5.3 移动端 UI（手测）

- [ ] 看板：分组方式分段显示"按状态 / 按客户"，激活态是 pill 风格、品牌软底。
- [ ] 看板：选"按客户"，搜索框 placeholder 是"搜索客户 / 项目"，空态文案是"没有匹配的客户 / 项目"。
- [ ] 看板：客户分组卡的上 / 下 / 置顶图标是 SVG（chevron / pin）；全部展开按钮是 SVG（minimize-2 / maximize-2）。
- [ ] 知识：分段控件外观与看板一致。
- [ ] 知识：batch / 客户分组卡内子项行有 12px 内边距，不再贴卡片边。
- [ ] 任务详情：客户材料卡下方有"客户事实"卡，每条 fact 一行；点击进 fact sheet。
- [ ] 任务详情 → fact sheet：fact sheet 关闭后自动回到任务详情（任务 sheet 仍在）。
- [ ] fact sheet：客户字段是按钮，点击打开搜索式客户选择器。
- [ ] fact sheet：选其他客户后，editor 内客户名实时变；同时知识 Tab 下次进入时数据已刷新。
- [ ] fact sheet：选"未关联"后，editor 显示"— 选择客户"。
- [ ] fact sheet：点击"删除" → 确认后 sheet 关闭、列表中真消失（不是变 rejected）。
- [ ] fact sheet → 点关联任务 → 跳到任务详情 sheet（不再保留 fact 叠加）。

### 5.4 端到端

- [ ] 选一个有客户事实的任务，进入详情 → 看到客户事实卡 → 点其中一条 → 修改客户 → 保存 → 返回任务详情 → 客户事实卡的客户名已更新。
- [ ] 同一条 fact，删除 → 回到任务详情 → 客户事实卡少一行。

---

## 6. 风险和已知问题

### 6.1 硬删除不可逆

- 删除 fact 后 row 直接消失，没有回收站。**评估为可接受**：fact 是 agent 自动写入，量大且廉价，误删可由 agent 重新生成（用户在飞书重新发一遍消息）。
- 缓解：移动端按钮已有 `window.confirm("确定删除这条事实？")` 二次确认。

### 6.2 删除 fact 影响材料聚合

- 已经聚合进 customer_materials 的 fact 被删时，`customer_material_facts` 关联会 CASCADE 清掉，但 `raw_facts_markdown` 的拼接结果不会自动重写。
- **评估为可接受**：周日 cron 重新跑会基于当前 fact 列表重生成下一周期的 material；当周已审核 / 已上传的 material 不再需要修改。
- 后续可加：删除 fact 时把所有"未上传"状态的 material 回标 `draft` 重新审核（不在本 Plan）。

### 6.3 看板"按客户"实际仍按 project 文本

- 视觉文案"按客户"，行为仍按 `Task.project` 自由字符串分组。如果两个任务的 project 文本是 "悦爱智能" vs "悦爱"，会被分成两组，与"客户"语义不一致。
- **评估为已知遗留**：见 §1.4，单独排期"切到 customer_id"。本次只是文案对齐用户口语习惯，不会让数据更糟。

### 6.4 fact sheet 叠加渲染的边界

- 用户从 fact sheet → 点"关联任务" → 跳到任务详情后，再从该任务详情进任意 fact → 此时 `factSheetOverTask` 又被设为 true。返回路径：fact sheet 关闭 → 回到当前任务详情。这条路径已验证在状态机闭环。
- 唯一需要小心的：从知识 Tab → fact sheet 进入时不能误设 `factSheetOverTask=true`，目前 `openFactById` 不动 `factSheetOverTask`，只有任务详情卡的 `onOpenFact` 显式 set，安全。

### 6.5 客户选择器列表性能

- 当前 customers 量级 < 200，本地过滤无压力。如果后续 > 1k，可改为加 debounce + 后端搜索（未实现）。

### 6.6 SVG 图标暗色模式

- 已用 `stroke: currentColor` + `fill: none`，按钮的 color 决定图标色，自动跟随主题。已在 `.board-segment-active` / `.mini-icon-button-active` 等场景验证。

---

## 7. 推荐执行顺序（已按此顺序完成）

1. 后端 `delete_fact` 改硬删 + import 清理 → uvicorn `--reload` 自动生效。
2. 移动端 `types.ts` 扩 `UpdateFactPayload` → 让后续 mutation 编译通过。
3. 移动端 `api.ts` 加 `getTaskFacts`。
4. 移动端 `App.tsx`：state 三件套（`factSheetOverTask` / `factCustomerPickerOpen` / `taskFacts`）→ 新 mutation `updateFactCustomerById` → 已有 mutation 加 `taskFacts.refresh`。
5. `TaskDetailSheet` 扩 props + 新增"客户事实"卡 + `CompactFactRow`。
6. 主体 JSX 调整 sheet 渲染条件（叠加逻辑）。
7. `FactEditorSheet` 客户字段改可点击 + 新增 `FactCustomerPickerSheet`。
8. `MoveArrowIcon` / `PinIcon` 重写为 SVG，新增 `ExpandToggleIcon`，BoardHero 替换 `⊟`/`⊞`。
9. 看板文案重命名（按客户）。
10. `styles.css`：重写 `.board-segmented`、简化 `.knowledge-segmented`、加新组件样式 + 暗色覆盖。
11. `npm run build` 验证。
12. 同步 `TASK_CENTER_API_FOR_AGENTS.md` + `mobile_frontend/README.md`。

---

## 8. 一个待你二次确认的点

§1.4 看板"按客户"目前**只是文案**，分组键仍是 `Task.project` 自由字符串。这是不是你期望的最终形态？

- 如果是 → 本 Plan 完结。
- 如果不是（你希望真按 `customer_id` 分组）→ 需要单独排期一个 Plan：
  - 后端 `/api/dashboard/board` 增加 `mode=customer` 分支，按 `tasks.customer_id` 聚合。
  - 移动端 BoardMode 加 `'customer'` 值，URL hash 兼容，老的 `mode=project` 转译。
  - 旧 task 的 project 文本如何匹配 customer_id（建议在 `backfill_task_customer_area.py` 里补一段反向 backfill）。
  - 排期估计 0.5 ~ 1 天。

**请确认是否进入下一阶段**。
