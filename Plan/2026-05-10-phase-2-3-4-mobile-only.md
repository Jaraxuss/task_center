# Task Center Phase 2/3/4 — 移动端 + 后端收尾（桌面端归档）

桌面 `frontend/` 整体归档到 `archive/frontend/`，移动端引入 OpenAPI codegen 替换手写类型，再把 3537 行的 `mobile_frontend/src/App.tsx` 拆成多文件，最后做后端 V1→V2 数据模型收尾（`Task.project` 字符串、CustomerMaterial legacy 字段、ProjectV2 命名）。

## 进度

| 子项 | 状态 | commit | 日期 |
|---|---|---|---|
| 2.0 桌面前端归档 | ✅ 完成 | `4d33a56` (主仓) | 2026-05-10 |
| 2.1 后端 OpenAPI 导出 + 快照测试 | ✅ 完成 | `9012397` (主仓) + `3eb9b65` (子仓) | 2026-05-10 |
| 2.2 移动端 codegen 集成 | ✅ 完成 | `3c924e3` (主仓 bump) + `c9a0da1` (子仓) | 2026-05-10 |
| 2.3 移动端 api.ts 瘦身 | ✅ 完成 | `9f9763c` (主仓 bump) + `99f3811`/`ec3007b` (子仓) | 2026-05-10 |
| 3.1–3.9 App.tsx 拆分 | ⏳ 待开始 | | |
| 4.A Task.project 下线 | ⏳ 待开始 | | |
| 4.B CustomerMaterial legacy | ⏳ 待开始 | | |
| 4.C ProjectV2 命名统一 | ⏳ 待开始 | | |

---

## 0. 与已有 Plan 的关系

### 0.1 父 Plan

- `Plan/2026-05-06-backend-phase-0-1-routers-services-split.md`（后端工程化 Phase 0 + 1）。
  - Phase 0 / 1.A / 1.B **已全部完成**。本 Plan 的 Phase 2（OpenAPI 管道）和 Phase 4（数据模型收尾）直接建立在 Phase 1 拆分后的 routers / services / schemas 骨架之上。
  - Phase 1 Plan §9 列出的 Phase 2 候选中，§9.2（`routers/projects.py` vs `projects_v2.py` 合并）和 §9.3（`main.py` re-export 清理）被本 Plan Phase 4.A / 4.C 正式接管。

### 0.2 兄弟 Plan（仍然有效）

- `Plan/2026-05-07-mobile-knowledge-project-facts.md`（移动端知识事实按客户项目组织）。
  - 该 Plan 引入的 `GET /api/knowledge/facts/overview` 接口、知识偏好（`KnowledgePreference`）、客户→项目→事实三级结构**继续生效**，本 Plan Phase 3 拆 `src/views/knowledge/` 时保持这些行为等价。
  - 该 Plan 中对事实页懒加载、overview 数字的实现**不改动**。
- `Plan/2026-05-06-mobile-task-fact-and-board-customer-rename.md`（移动端任务详情接入事实 + 看板客户重命名）。
  - fact 编辑、删除、任务详情跳 fact 的能力**继续生效**，Phase 3 拆 sheets 时保持行为等价。
  - 看板"按客户"仅文案层改名，不在本 Plan 中切真客户分组。
- `Plan/2026-05-04-material-cleanup-and-mobile-knowledge.md`（CustomerMaterial 字段收口 + 移动端知识 Tab）。
  - 该 Plan 的字段收口工作**已完成**。本 Plan Phase 4.B 进一步下线 CustomerMaterial 6 个 legacy 字段，是其自然延续。

### 0.3 祖先 Plan（已完成，不再改动）

- `Plan/2026-05-04-customer-knowledge-revision.md` → `Plan/2026-05-03-customer-knowledge-roadmap.md`。
  - 5 表架构（customers / projects / facts / customer_materials / review_batches）和 v1/v2 收口**已落地**，本 Plan 不触碰这些表结构的设计，只做字段级下线和命名统一。
- `Plan/2026-05-03-customer-materials-api-consolidation.md`（v1/v2 接口收口）。
  - 收口**已完成**。本 Plan Phase 4.C 的 URL `/api/projects-v2` → `/api/projects` 是最后一次 v2 命名残余清理。

### 0.4 已确认的决策

- **桌面 `frontend/`** → 归档到 `archive/frontend/`（`git mv`，保留历史）。
- **Phase 2 方向**：引 `openapi-typescript`，后端导出 `openapi.json`，移动端 api.ts 瘦身到只剩 normalize 层。
- **Phase 5（前端解耦其余项 / React Query / 桌面拆分）暂不考虑**。
- 移动端是独立 git submodule（`task_center/mobile_frontend/`，仓库 `task_center_mobile_frontend`）。每个涉及移动端的子项 = **子仓 commit + 主仓 bump 指针** 两步。

## 1. 工程依赖顺序（与原编号有偏移）

原计划编号是 2/3/4，但工程上更顺手的顺序是 **2 → 3 → 4**：
- Phase 2 先做**基础设施**（归档桌面、铺 OpenAPI 管道）——风险最低、为后续提供类型保障。
- Phase 3 在已有干净类型的基础上**拆 App.tsx**——有类型护栏后拆分更安全。
- Phase 4 最后做**数据模型收尾**——跨后端 + 移动端，依赖前两步把移动端代码组织清楚。

保留原编号便于回顾，但每个 Phase 内部按"风险递增"排子项。

---

## 2. Phase 2 — 桌面归档 + OpenAPI 客户端基础设施

### 2.0 桌面前端归档（主仓，1 commit）

- `git mv frontend archive/frontend`
- `archive/README.md` 新增，说明：保留历史不再维护，最后一次实际功能改动 commit 是哪个，对应版本与移动端是否同步。
- `docs/PROJECT_OVERVIEW.md` §B 改为 "已归档"；§C 移到 §B；§"仓库边界"改成只剩主仓 + mobile 子仓两条。
- `README.md` / `BOOTSTRAP_BRIEF.md` 同步措辞。
- **不动** `archive/frontend/package.json` 内容；不在 CI 上构建它。
- **退出条件**：`grep -n "frontend/" docs/ README.md BOOTSTRAP_BRIEF.md` 全部指向 `archive/frontend/` 或显式标 deprecated；后端 + 移动端跑起来不受影响。

### 2.1 后端 OpenAPI 导出脚本（主仓，1 commit）

- 新增 `backend/scripts/dump_openapi.py`：

  ```python
  from main import app
  import json, sys
  json.dump(app.openapi(), sys.stdout, ensure_ascii=False, indent=2, sort_keys=True)
  ```

- `Makefile`（如果没有就建，否则加 target）：`make openapi` → 跑脚本写 `mobile_frontend/openapi.json`。
- `mobile_frontend/openapi.json` 落入 git 跟踪，作为前后端 API 契约快照。
- 加一个 pytest 校验：`tests/test_openapi_snapshot.py` 跑一次 `app.openapi()` 比对 checked-in 的 `openapi.json`，diff 即 fail。这样后端任何 schema 改动都会**强制**触发 spec 更新，避免漂移。
- **退出条件**：pytest 加 1 个新测试，`make openapi` 落地，CI 跑通。

### 2.2 移动端 codegen 集成（子仓，1–2 commit）

- `mobile_frontend/package.json` 新增 dev dep：`openapi-typescript`。
  - **不引** `openapi-fetch`，因为 normalize 层要继续做字段清洗、null/undefined 转换、enum 兜底等，自己包一层 `request<T>(...)` 比换 client 更稳。
- 新增 `mobile_frontend/src/api/generated.ts`：codegen 输出（grep-friendly 文件头注释禁止手改）。
- `package.json` 加 script：`"codegen": "openapi-typescript ./openapi.json -o src/api/generated.ts"`。
- `mobile_frontend/openapi.json` 通过 git submodule 同步指针引入（每次主仓 `make openapi` 后 commit 子仓）。或者更直接：**子仓自己抓 backend `/openapi.json`**——但需要后端跑起来。两者权衡：
  - **方案 A**：spec 由主仓写入子仓 (`backend/scripts/dump_openapi.py` 输出路径就是 `mobile_frontend/openapi.json`)。子仓只负责 codegen。✅ **推荐**。
  - **方案 B**：子仓 codegen 时 fetch live backend。简单但需要 dev backend 跑着。❌ 不推荐。
- **退出条件**：`npm run codegen` 在子仓里跑通；`generated.ts` 包含全部 47 个端点的 path/operation 类型 + 全部 schemas/__init__.py 暴露的 Pydantic 模型。

### 2.3 移动端 api.ts 瘦身（子仓，2–3 commit）

当前 `mobile_frontend/src/api.ts` 538 行做三件事：①手写每个端点的 URL + fetch 包装；②手写 normalize 函数把后端 `any` 转成前端 `Task` / `Customer` / 等；③手写前端类型（重复 `types.ts`）。

替换策略：

- **保留**：normalize 函数（`normalizeTask` / `normalizeCustomerMaterial` / `normalizeFact` / 等），这些做了字段清洗、`null → undefined`、字符串 trim、enum 兜底，有业务语义。
- **替换**：URL + fetch 包装 + 手写类型。
  - `request<T>(...)` 改成 `request<paths[Path][Method]['responses']['200']['content']['application/json']>(...)`。
  - `Task` 等前端类型从 `types.ts` 导出改为 re-export `paths['/api/tasks/{task_id}']['get']['responses']['200']['content']['application/json']` 的别名。
- **预期成果**：api.ts 538 → ~150 行（normalize 层 + thin endpoint wrappers）；`types.ts` 305 → ~50 行（仅前端衍生类型，如 `TaskFormState` / `MaterialFormState`）。
- **回归测试**：每改完一个领域（tasks / customers / materials / facts / knowledge），手动跑移动端：今日 / 计划 / 看板 / 历史 / 知识库 五个 tab 各点一遍，所有详情 sheet 各打开一次。
- **退出条件**：`grep -c "^export interface\|^export type" src/types.ts` 大幅下降；api.ts 行数 < 200；移动端手测无回归。

**Phase 2 总成本**：归档 0.5 天 + 后端管道 0.5 天 + 移动端 1.5 天 ≈ **2.5 天**，跨 2–3 次会话。

---

## 3. Phase 3 — 移动端 App.tsx 拆分

### 3.0 现状盘点

`mobile_frontend/src/App.tsx` = 3537 行 / 55+ 内嵌函数，大致分布：

| 段落 | 行号 | 内容 | 目标位置 |
|---|---|---|---|
| 头部 utils | 1–520 | `truncateText` / `formatDateTimeInput` / `makeXxxFormState` / `groupMaterialsByBatch` / `sortTasksWithPreference` 等 25+ 纯函数 | `src/lib/` 多文件 |
| `App()` | 535–1668 | 顶层 shell：状态、effect、handlers、JSX 路由 | `src/App.tsx`（~500 行收尾态） |
| view Hero | 1668–2310 | `SummaryStrip` / `TodayHero` / `PlanHero` / `BoardHero` / `HistoryHero` / `KnowledgeHero` | `src/views/<tab>/Hero.tsx` |
| view Section | 1808–2563 | `TaskGroupSection` / `PlanDaySection` / `HistoryDaySection` / `MaterialBatchGroupSection` / `FactCustomerGroupSection` / `KnowledgeFactCustomerCard` | `src/views/<tab>/<Section>.tsx` |
| Row / 原子 | 2145–2647 | `TaskRow` / `MaterialRow` / `FactRow` / `CompactFactRow` + 各 `StatusPill` + 图标 | `src/components/` |
| Sheet | 2658–3528 | 8 个 Sheet：`TaskDetailSheet` / `TaskActionSheet` / `TaskEditorSheet` / `MaterialEditorSheet` / `FactEditorSheet` / `FactCustomerPickerSheet` / `HistoryFilterSheet` / `SettingsSheet` | `src/sheets/` |
| 空态 | 3529–3537 | `StateCard` / `EmptyHint` | `src/components/` |

### 3.1 子项拆分顺序（每个 = 1 个子仓 commit）

按"**风险递增**"——纯函数先动，shell 最后动：

1. **`src/lib/` 抽纯函数**（最无风险）：所有 head-of-file utility 拆分到 `src/lib/format.ts`、`src/lib/forms.ts`、`src/lib/grouping.ts`、`src/lib/sort.ts`、`src/lib/route.ts`。**零行为变化**。
2. **`src/components/` 抽原子**：`StatusPill` / `MaterialStatusPill` / `FactStatusPill` / `MoveArrowIcon` / `PinIcon` / `ExpandToggleIcon` / `StateCard` / `EmptyHint` / `TaskRow` / `MaterialRow` / `FactRow` / `CompactFactRow`。这些是无副作用 presentational 组件，每个 ~30 行。
3. **`src/sheets/` 抽 8 个 Sheet**：每个 sheet 一个文件，prop 化所有外部状态。`TaskActionSheet` / `TaskDetailSheet` / `TaskEditorSheet` / `MaterialEditorSheet` / `FactEditorSheet` / `FactCustomerPickerSheet` / `HistoryFilterSheet` / `SettingsSheet`。
4. **`src/views/today/` 抽今日**：`Hero.tsx` + `TaskGroupSection.tsx` + `index.tsx`（exports `<TodayView ...props/>`）。
5. **`src/views/plan/`** 抽计划：`Hero.tsx` + `DaySection.tsx` + `index.tsx`。
6. **`src/views/board/`** 抽看板：`Hero.tsx` + `index.tsx`（板视图的 statusGroups / projectGroups 切换在 view 内部决策）。
7. **`src/views/history/`** 抽历史：`Hero.tsx` + `DaySection.tsx` + `index.tsx`。
8. **`src/views/knowledge/`** 抽知识库：`Hero.tsx` + `MaterialBatchGroupSection.tsx` + `FactCustomerGroupSection.tsx` + `KnowledgeFactCustomerCard.tsx` + `index.tsx`。
9. **`App.tsx` shell 最终态**：保留 useState / useEffect / api 调用 / handlers / routing，按 `activeTab` switch 渲染 view。目标行数 ≤ 600。

### 3.2 拆分的工程纪律

- **行为等价**：每个 commit 跑完后，UI 不变。手测项：每个 tab 进入一次、每个 sheet 打开一次、保存 / 取消 / 删除三类操作各跑一次。
- **prop 显式**：原本闭包捕获的状态 + handlers 全部显式传 prop。**禁止**用 Context 或全局 store 偷懒——这次只是拆文件，不引入新架构。
- **类型从 OpenAPI 来**：拆分过程中任何遇到 `any` / 自己拼 props 的地方，优先用 Phase 2 已经生成的类型。
- **每子项独立 commit**：commit message 格式 `refactor(mobile): Phase 3.X — extract <module> from App.tsx`。
- **回滚单元 = 单个子项**：3 子项失败立刻回滚到 2，不会影响 4-9。

### 3.3 退出条件

- `mobile_frontend/src/App.tsx` 行数 ≤ 600。
- `mobile_frontend/src/` 目录结构：

  ```
  src/
    App.tsx
    main.tsx
    api/
      generated.ts
      index.ts        # 原 api.ts thin wrapper
    lib/              # 纯函数
    components/       # 原子 + Row
    sheets/           # 8 个 sheet
    views/
      today/
      plan/
      board/
      history/
      knowledge/
    config.ts hooks.ts styles.css types.ts utils.ts
  ```

- 每次切 tab + 打开 sheet 手测无回归。

**Phase 3 总成本**：9 个子项 × 0.3–0.6 天 ≈ **4–5 天**，跨 4–6 次会话。

---

## 4. Phase 4 — V1 → V2 数据模型收尾

### 4.1 三件事的实际复杂度（与原表述对比）

原表述：
- (a) `tasks.project` 字符串字段下线，全切 `project_id`
- (b) CustomerMaterial legacy 字段下线
- (c) Project / ProjectV2 命名统一

实际剖析：

**(a) `Task.project: str` 下线**——是大动作，因为以下都在用：
- `services/dashboard.py:groupTasksByProject`（看板 project mode 分组）
- `services/tasks.py:64`（搜索 ilike）
- `routers/projects.py`（GET 列表 + PATCH rename，两端点）
- `mobile App.tsx`（pill 显示 + datalist 编辑）
- 所有现有 task 行的 `project` 字符串数据要先 backfill 到 `project_id`，否则下线后看板分组、搜索全部废。

**(b) CustomerMaterial 6 个 legacy 字段** (`project / source_type / source / source_refs / value_types / task_id`)：
- 移动端只 read-only 显示 `material.project`（行 3098）和 `material.task_id`（行 2639）。
- 其余 4 个已**完全无 UI 引用**，可以无缝下线。
- `task_id` 显示其实可以从反向 relation `task.related_materials` 推回去；或干脆删掉这个 UI 显示。

**(c) ProjectV2 命名统一**：
- `models.Project`（类名）已经是 V2 了，是 `routers/projects.py` 占着 `/api/projects` URL。
- 真正要做：① schemas `ProjectV2Read/Create/Update` → `ProjectRead/Create/Update`；② router 文件 `projects_v2.py` → `projects.py`（**前提**是旧的 `projects.py` 已经下线）；③ URL `/api/projects-v2` → `/api/projects`；④ 移动端 `api.getProjects()` 切到新 URL。

### 4.2 子项依赖图

```
4.1 backfill task.project_id  ──┐
                                ├─→ 4.2 dashboard 改 join Project
                                ├─→ 4.3 search 改 join Project
                                ├─→ 4.4 移动端 project picker 切 project_id
4.4 ──→ 4.5 alembic drop Task.project column
        4.5 + 4.6 旧 /api/projects 端点下线
                ──→ 4.7 schemas 改名 ProjectV2* → Project*
                ──→ 4.8 URL /api/projects-v2 → /api/projects
                ──→ 4.9 移动端 api.getProjects 切新 URL
4.10 CustomerMaterial legacy 字段下线（独立链路，与 4.1-4.9 并行）
```

### 4.3 子项详情

#### 4.A `Task.project` 下线（最大子链，5 commit）

- **4.A.1 backfill 脚本**（后端，1 commit）：`backend/scripts/backfill_task_project_id.py`：
  - 扫所有 `task.project_id IS NULL AND task.project IS NOT NULL`。
  - 按 `(task.customer_id, task.project)` 在 `projects` 表里找匹配 row。
  - 找到 → 写 `task.project_id`。
  - 找不到 → 创建新 `Project` 行（用 `task.project` 当 name，`task.customer_id` 当 fk，`area` 用 customer.area）。
  - 输出 dry-run 报告 + 实际执行选项（`--apply`）。
  - 加 pytest 覆盖至少 3 个分支（match / no-match-create / customer-less）。
- **4.A.2 dashboard 改 join**（后端，1 commit）：`services/dashboard.py:groupTasksByProject` 改成基于 `task.project_id` JOIN `projects.name`。同时 `services/tasks.py:64` 搜索改 `or_(... Project.name.ilike(like) ...)`。
- **4.A.3 移动端 project picker**（子仓，1 commit）：替换 `<input list="project-options">` 为基于 `/api/projects-v2` 的 `<select>`（按客户分组）。`task.project: string` 字段从 normalize 层移除 / 改 derive。
- **4.A.4 `/api/projects` 旧端点下线**（后端，1 commit）：删 `routers/projects.py`、`schemas/_common.ProjectSummary` / `ProjectRenameRequest` / `ProjectRenameResponse`，删 `add_event(EventType.PROJECT_RENAMED)`。`scripts/normalize_customer_projects.py` 同步更新或归档。
- **4.A.5 alembic drop column**（后端，1 commit）：alembic revision，drop `tasks.project` column。同步 `models.py` 删 `Task.project` 字段。**前提**：4.A.1 的 backfill 必须已在生产 DB 跑过 + 验证 `SELECT count(*) FROM tasks WHERE project IS NOT NULL AND project_id IS NULL = 0`。

#### 4.B CustomerMaterial legacy 字段下线（3 commit）

- **4.B.1 移动端清理只读显示**（子仓，1 commit）：删 `material.task_id` 在行 2639 的显示；`material.project` 改成从 `material.project_v2_id` lookup `Project.name` 显示。normalize 层移除 6 个 legacy 字段。
- **4.B.2 后端 schemas / router 移除字段**（后端，1 commit）：`schemas/customer_materials.py` 的 `CustomerMaterialRead` 移除 6 个字段；router create/update 不再接受这些字段；service 序列化层移除。
- **4.B.3 alembic drop columns**（后端，1 commit）：drop 6 列。前提：生产 DB 已确认无依赖（FK 反向用 task → materials 的关系替代 `material.task_id`）。

#### 4.C ProjectV2 命名统一（4 commit）

按依赖顺序，**必须在 4.A 全部做完之后才开始**：

- **4.C.1 schemas 改名**（后端，1 commit）：`schemas/projects_v2.py` → `schemas/projects.py`，类名 `ProjectV2*` → `Project*`，`schemas/__init__.py` re-export 调整。导入此名的所有 router / service 一并改。
- **4.C.2 services 改名**（后端，1 commit）：`services/projects_v2.py` → `services/projects.py`。导入它的代码同步改。
- **4.C.3 router URL 切换 + 文件改名**（后端，1 commit）：`/api/projects-v2` → `/api/projects`。`routers/projects_v2.py` → `routers/projects.py`（这时旧文件 4.A.4 已删除，可以无冲突 rename）。
- **4.C.4 移动端 URL 切换**（子仓，1 commit）：`api.ts` 的 `request<...>('/api/projects-v2'...)` → `'/api/projects'`。同步 OpenAPI codegen 重跑。

### 4.4 子项总数 & 估时

| 子项群 | commit 数 | 估时 |
|---|---|---|
| 4.A `Task.project` 下线 | 5 | 2.5 天 |
| 4.B CustomerMaterial legacy | 3 | 1 天 |
| 4.C ProjectV2 命名统一 | 4 | 1 天 |
| **合计** | **12** | **4.5 天** |

每个 commit 必须验证：
- 后端 commit：pytest 73+/73+ 全过、ruff clean、mypy 不增。
- 移动端 commit：手测对应 tab + sheet。
- 涉及 alembic：`alembic upgrade head` 在测试 DB + 备份后的生产 DB 副本上各跑一次，diff 输出存进 commit message。

---

## 5. 风险与回滚

| 风险 | 缓解 |
|---|---|
| Phase 2 OpenAPI codegen 输出与 Pydantic 实际行为有偏差（比如 `Optional[X]` 在 spec 里是 `X \| null`，前端类型可能多个 `null` 分支） | 第一次落地时手动审 `generated.ts`，必要时给后端 schema 加显式 `Field(default=None)` 让生成更干净 |
| Phase 3 拆分过程中 closure 状态漏传 | 每子项独立 commit + 手测；单子项失败可回滚不影响其他 |
| Phase 4.A.1 backfill 脚本误生成大量重复 Project 行 | dry-run + count 比对先做；生产 DB 跑前 backup |
| Phase 4 alembic drop column 数据丢失 | drop 前确保 backfill 已完成；alembic 上一步加 select count == 0 校验 |
| 子仓 / 主仓 commit 节奏错乱 | 每个 Phase 子项明确标注 "子仓" / "主仓"；`docs/PROJECT_OVERVIEW.md` §仓库边界保留 |

回滚策略：

- Phase 2.0 归档：`git mv archive/frontend frontend` 即可。
- Phase 2.1–2.3：每子项独立 commit，逐个 revert。
- Phase 3：每子项独立 commit，逐个 revert（子仓 + 主仓 submodule 指针都要 reset）。
- Phase 4：alembic 有对应 downgrade；schemas/services 改名也是单 commit revert。**唯一不可逆**：4.A.5 / 4.B.3 的 drop column 之后，旧字段数据永久丢失（依赖 backup）。

---

## 6. 出完整 Plan 之后下一步

- 用户确认 Plan 后，**实现按 Phase 拆多次会话**，每次会话推进 1–3 个子项：
  - Session A：Phase 2.0 + 2.1 + 2.2（基础设施铺好）
  - Session B：Phase 2.3（api.ts 瘦身）
  - Session C–F：Phase 3.1 → 3.9（每会话 2–3 个子项）
  - Session G：Phase 4.A.1 + 4.A.2（backfill + dashboard）
  - Session H：Phase 4.A.3 + 4.A.4 + 4.A.5（移动端切 + 旧端点下线 + drop column）
  - Session I：Phase 4.B.1 + 4.B.2 + 4.B.3（CustomerMaterial legacy）
  - Session J：Phase 4.C.1 → 4.C.4（ProjectV2 改名）
- 每次会话开始前：`git status` 确认干净；session 结束前：commit + 推送 + 更新本 Plan 的进度表。
- 进度表跟进位置：本 Plan 顶部加一个表，类似 `Plan/2026-05-06-backend-phase-0-1-routers-services-split.md` 顶部的"进度"。

---

## 7. 不在本 Plan 内的事

- **桌面前端的任何功能/重构改动**：归档后不再投入。
- **React Query / TanStack Query**：用户明确暂不考虑。
- **桌面 components.tsx 拆分 + 桌面 App.tsx 拆 views**：归档后无意义。
- **shared/ 跨端共享模块**：原本是给桌面 + 移动共用，桌面归档后无消费方，**不做**。如果未来需要给 agent SDK 共享类型，重起一个独立 Plan。
- **mypy 全仓 strict / 严格岛扩到 schemas 子包**：留作 Phase 5 候选（参考 `Plan/2026-05-06-backend-phase-0-1-routers-services-split.md` §9）。
- **`services/schema_compat.py` 手写 ALTER 链清理**：同上 §9.4，待生产 DB 全部 `alembic stamp head` 后再做。
