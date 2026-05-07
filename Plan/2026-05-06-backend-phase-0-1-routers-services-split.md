# 后端工程化 Phase 0 + Phase 1（2026-05-06 起，含 Phase 1.A 已完成 / Phase 1.B 进行中）

创建时间：2026-05-07（倒序落档；2026-05-07 下午校准为 Phase 1.A / 1.B 两阶段记法）
负责人：南哥 / Cascade

## Phase 1 完整范围（按最初计划）

按本会话开头的拆解，Phase 1 = **6 个子项**：

1. **lifespan**（FastAPI 0.110+ 推荐写法，替换 deprecated `@app.on_event`）
2. **拆 routers**（按 URL 前缀切 10 个 `routers/<domain>.py`）
3. **提 services**（按领域切 10 个 `services/<domain>.py`，纯逻辑可进 mypy 严格岛）
4. **拆 schemas**（`schemas.py` ~900 行 → `schemas/<domain>.py` 多文件，和 routers / services 三件套对齐）
5. **公共 helper**（提取 routers PATCH / 序列化里重复的模板代码——`json.dumps(..., ensure_ascii=False)` 包装、`*_json` 字段的 set 模板、`clear_*` boolean + FK 的处理对子，等等）
6. **JSON TypeDecorator**（`*_json` TEXT 列在 ORM 层自动 `loads` / `dumps`，删掉 `services/json_utils.py` 大部分代码 + 各 router 里手工 `json.dumps` 模板）

## 进度（2026-05-07 下午）

| 子项 | 状态 | 落地 commit |
|---|---|---|
| lifespan | ✅ 完成 | `0a71c27`（和 Phase 0 一起提交） |
| 拆 routers | ✅ 完成 | `c1a60a9` |
| 提 services | ✅ 完成 | `c1a60a9` |
| 拆 schemas | ⏳ 待做 | Phase 1.B |
| 公共 helper | ⏳ 待做 | Phase 1.B |
| JSON TypeDecorator | ⏳ 待做 | Phase 1.B |

本文档原版（commit `123f9c8` 落档时）把后三项错误归类成「Phase 2 候选」。本次校准把它们重新归回 Phase 1，命名为 **Phase 1.B 剩余工作**（见 §8）。真正的 Phase 2 候选另列 §9。

相关 commit（按时间序）：
- `0a71c27` refactor(backend): Phase 0 + lifespan — test scaffolding, Alembic baseline, env-driven DB URL
- `c1a60a9` refactor(backend): Phase 1 — split main.py into routers + services（即 Phase 1.A 主体）
- `301ff8f` docs(skills): add commit-discipline skill（Phase 1.A 期间顺手补的协作规范）
- `4dabef7` feat(tasks): /api/tasks 支持 customer_id / project_id 筛选（Phase 1.A 后第一个落在新结构上的功能改动）
- `8108766` docs(agent-api): 更新 §1 服务位置以反映 routers/services 拆分
- `123f9c8` docs(plan): 本 Plan 初版（倒序落档 Phase 0 + Phase 1.A）

目标：把 `backend/main.py` 从 1701 行的"全部 HTTP + 业务逻辑 + schema compat + 启动钩子"的胖文件，拆成**入口 / 路由 / 服务 / 模型 / schema / 迁移**六层骨架；并消除 `*_json` TEXT 列在路由层的样板代码、收敛重复的 PATCH 模板。给这次拆分建立安全网（测试 + Alembic 基线 + mypy 严格岛）。

---

## 0. 与父 Plan / 路线图的关系

### 0.1 没有显式父 Plan

这次不像 `2026-05-03-customer-knowledge-roadmap.md` → `2026-05-04-customer-knowledge-revision.md` → `2026-05-06-mobile-task-fact-and-board-customer-rename.md` 这条线是围绕"客户知识"业务主题展开的。后端工程化**没有一份上游业务 Plan**；起因是长期开发累积出 `main.py` 1701 行的技术债，调用方（agent / 前端 / mobile）已经分不清一个端点属于哪个领域、改一个小逻辑要翻十几处。

### 0.2 与已有 Plan 的互动

- 父 Plan `2026-05-04-customer-knowledge-revision.md` §3 后端 API 字段清理**已经完成并且不动**；Phase 1 的拆分严格按"行为等价"执行，47 个端点 URL / 响应结构 / 副作用全部不变。
- 子 Plan `2026-05-06-mobile-task-fact-and-board-customer-rename.md` 的后端部分（`DELETE /api/facts/{id}` 改硬删）在 Phase 0 和 Phase 1 之间穿插进行；Phase 1 拆分时已经把这个行为迁进了 `routers/facts.py` + `services/facts.py`。
- **不影响**任何业务契约、DB schema、agent 交互协议。

### 0.3 本 Plan 的时间线

- **Phase 0**（你在本会话之前完成）：工程安全网。commit `0a71c27` 在 2026-05-06 16:06 UTC 落地。
- **Phase 1.A**（本会话完成）：lifespan + `main.py` 拆分（routers + services）。lifespan 包在 `0a71c27` 里、routers/services 拆分在 `c1a60a9`，2026-05-06 晚落地。
- **Phase 1.A 后续**：顺手补了 commit 纪律 skill（`301ff8f`）；基于新骨架做了第一个真功能改动（`4dabef7`，`/api/tasks?customer_id=...`）；修正了 agent 文档里"后端代码：main.py"这种被拆分前的描述（`8108766`）；本 Plan 初版落档（`123f9c8`）。
- **Phase 1.B**（本次校准后开工）：拆 schemas + 公共 helper + JSON TypeDecorator。预计跨多次会话；每个子项可独立提交、独立验证（pytest + ruff + mypy 严格岛全过）。

---

## 1. 核心决策

### 1.1 双层架构：`routers/` + `services/`

**决策**：不走 "一层 `api/`" 或 "FastAPI `APIRouter` 直接塞业务逻辑"，而是强制分两层。

- `backend/routers/<domain>.py`：**只**处理 HTTP 层的事——参数绑定、Query/Path 参数、Pydantic request model、response_model、状态码。**禁止**写 SQL、禁止写领域规则、禁止写 JSON 合并逻辑。
- `backend/services/<domain>.py`：**所有领域逻辑**——DB 查询、ORM 组合、序列化、规则校验、副作用（add_event 等）。对 FastAPI 的依赖只保留一个：可以 `raise HTTPException`（把"找不到实体"这种跨切面的 404 当作领域规则的一部分，而不是强迫每个 service 返回 `Optional` 让 router 翻译）。

**为什么**：

- 端点越来越多（47 个），如果把业务都塞在 router 函数里，改一个跨端点的规则（比如 board 排序规则）要翻 N 个文件，很快退化回 1701 行的老 `main.py`。
- service 是**纯函数为主**，可以进 mypy 严格岛（见 §1.4），router 因为依赖 FastAPI 的各种 `Depends` / `Query` 无法简单严格。
- 这不是 DDD，不是 Clean Architecture，只是**把可测试的纯逻辑和 HTTP 框架胶水隔离**。规则定得越少越容易守住。

### 1.2 领域划分方式

**决策**：按"URL 前缀第一段"切分领域，不按 ORM 模型切。

实际落地的 10 个领域（和 URL 前缀一一对应）：

| 领域 | URL 前缀 | router 文件 | service 文件 |
|---|---|---|---|
| 健康检查 | `/api/health`, `/api/nightly-review` | `routers/health.py` | （无，直接查 DB） |
| 板偏好 | `/api/preferences/board` | `routers/preferences.py` | `services/board.py` |
| 旧字符串项目 | `/api/projects`, `/api/projects/rename` | `routers/projects.py` | 复用 `services/dashboard.py` + `services/board.py` |
| 任务 | `/api/tasks` | `routers/tasks.py` | `services/tasks.py`（最大的一个，~310 行）|
| 看板 / 今日 / 计划 / 历史 | `/api/dashboard/*`, `/api/history` | `routers/dashboard.py` | `services/dashboard.py` |
| 客户材料 | `/api/customer-materials` | `routers/customer_materials.py` | `services/customer_materials.py` |
| 客户 V2 | `/api/customers` | `routers/customers.py` | `services/customers.py` |
| 项目 V2 | `/api/projects-v2` | `routers/projects_v2.py` | `services/projects_v2.py` |
| 事实 | `/api/facts` | `routers/facts.py` | `services/facts.py` |
| 评审批次 | `/api/review-batches` | `routers/review_batches.py` | `services/review_batches.py` |

**注意两对容易混淆的孪生模块**（留档说明）：

- **`routers/projects.py` vs `routers/projects_v2.py`**：前者操作的是 `Task.project`（字符串 label，旧模型），后者是 `Project` 表（FK，客户视角的项目实体）。URL 前缀故意保留 v2 后缀区分，短期不合并——因为前端 / mobile 还在用旧的 `Task.project`，板分组也还按字符串分组。
- **`services/board.py` vs `services/dashboard.py`**：前者只管 `BoardPreference` 表的读写 + 自定义排序元数据；后者是 today/plan/board/history 四种聚合视图的构造器。板偏好是配置，看板是展示，两件事。

### 1.3 schema 拆分推迟到 Phase 1.B

**决策**：`backend/schemas.py` 在 Phase 1.A **不拆**，留到 Phase 1.B 完成。

**为什么 Phase 1.A 先不动**：

- 拆 schemas 要回答一个比较难的问题：按领域拆（`schemas/tasks.py`、`schemas/facts.py`…）还是按用途拆（`schemas/requests.py`、`schemas/responses.py`）？
- Pydantic 模型之间有互相引用（`TaskDetail` 引用 `ReminderRead` / `TaskRecurrenceRead` / `TaskEventRead`），跨文件拆要处理循环依赖。
- Phase 1.A 已经在改 `main.py` + 新增 20 个文件，再叠 schemas 拆分会让 commit 体积失控、行为等价验证范围模糊。

**Phase 1.B 的方案**（见 §8.1）：按领域拆，和 routers / services 的命名对齐（每个 domain 形成 router + service + schema 三件套）。建议和 §8.3 JSON TypeDecorator 一起做，避免同一个 schema 文件被动两次。

### 1.4 mypy 严格岛而不是全仓 strict

**决策**：不把整个 `backend/` 切成 `strict = true`，而是逐模块加入严格岛。

Phase 0 启动时的严格岛：`recurrence`、`timeutils`、`config`（都是纯函数 + 无 ORM 依赖）。

Phase 1 扩到：加上 `services.board`、`services.customer_materials`、`services.customers`、`services.dashboard`、`services.facts`、`services.json_utils`、`services.projects_v2`、`services.review_batches`。

**留在外面的**：`services.tasks`（有一处 `query_tasks` 缺返回类型标注，SQLAlchemy `Select[tuple[Task]]` 在当前 SA 2.x + mypy 组合下标注成本较高，留 Phase 2）；所有 `routers/*`（FastAPI `Depends(...)` 在 mypy strict 下需要额外的 stub 才好看）；`models.py`（`class X(Base)` 里 Base 是 Any，整个文件都会炸）；`main.py`（仅胶水）。

**原则**：严格岛**只吸收真正的纯逻辑**。一个模块进来的前提是改动它不会引入新的 `Any` 污染，并且加了类型能真的抓到 bug。

### 1.5 `main.py` 保留兼容 re-export

**决策**：拆完后 `main.py` 仍然 re-export 四个名字：`init_db`、`add_event`、`rename_project`、`update_task`。

**为什么**：

- `seed_demo.py` 里写着 `from main import add_event, init_db`。
- `scripts/normalize_customer_projects.py` 里写着 `from main import rename_project, update_task`。
- 这些脚本属于**项目历史遗留**，不属于 Phase 1 的 scope，不该在一次 PR 里顺手改；`from main import` 失败会打断你手头的运维流程。
- re-export 只有 4 行，代价极小，**比在 Phase 1 commit 里多改两个 script 文件要干净**。

新代码应当 `from services.tasks import add_event` / `from services.schema_compat import init_db` / `from routers.projects import rename_project` 等，不要再走 `main`。

### 1.6 行为等价 = 验证底线

**决策**：Phase 1 是**纯结构性重构**，对外行为 0 变化。底线是：

- 47 个端点的 URL、HTTP 方法、请求 schema、响应 schema、状态码、副作用事件、事件 payload 字段——**完全等价**。
- 所有 59 个既有测试（覆盖 recurrence 26 + timeutils 17 + API smoke 13 + Alembic parity 1 + DB isolation 3）——**全部继续通过，不改测试**。
- DB schema **零变更**（Phase 0 已经对齐 Alembic baseline）。

任何"顺手改行为"的冲动都压到后续独立 commit（如 `4dabef7` 加 `customer_id` 过滤），不混进 Phase 1。

---

## 2. Phase 0 已做（commit `0a71c27`）

Phase 0 是 Phase 1 拆分的**前置安全网**：没有它，拆 1701 行的胖文件就是在没有安全绳的情况下走钢丝。

### 2.1 环境变量驱动的 DB URL

- `config.py`：`Settings.database_url` / `Settings.database_path` 新增，分别接受 `TASK_CENTER_DATABASE_URL` / `TASK_CENTER_DATABASE_PATH` 覆盖。默认值保持生产行为：`backend/data/task_center.db`。
- `db.py`：engine 改从 `settings.database_url` 构造，`DATABASE_PATH` 也改为从 settings 导出。

**效果**：测试可以注入 `TASK_CENTER_DATABASE_URL=sqlite:///$TMPDIR/task_center_test.db`，不再碰生产 DB 文件。

### 2.2 测试脚手架

新增 `backend/tests/`：

| 测试文件 | 覆盖内容 | 数量 |
|---|---|---|
| `test_recurrence.py` | recurrence 规则计算 | 26 |
| `test_timeutils.py` | 时区 / 本地日界 / ISO 序列化 | 17 |
| `test_api_tasks.py` | 端到端：create / get / update / complete / defer / cancel / recurrence 推进 / 404 / dashboard 契约 | 13 |
| `test_alembic_baseline.py` | 迁移结果 vs `Base.metadata.create_all` 的 schema 对齐 | 1 |
| `test_db_isolation.py` | 确保测试 engine 指向临时 DB，不会污染生产 | 3 |

`conftest.py` 做了**两层防线**：
- 强制 pytest 启动时 `TASK_CENTER_DATABASE_URL` 指向 `$TMPDIR` 下的临时 DB。
- `api_client` fixture 启动 FastAPI 之前再核对一次 engine.url 是临时 DB，不是就 fail 整个 session。

测试总数：**59**（Phase 1 后增到 60，Phase 1 后的 `4dabef7` 又加了 1 条 customer_id 过滤测试也算在这个骨架上）。

### 2.3 Alembic 基线

新增 `backend/alembic/`：

- `alembic.ini` + `env.py`（读 settings 里的 DB URL，不 hardcode）+ `script.py.mako`。
- `versions/612481f0ad55_baseline_schema.py`：把当前生产 schema 完整捕获为一次 baseline migration（368 行），包括所有枚举、外键、索引、JSON TEXT 列。
- 对**既有生产 DB** 的升级路径：运行 `alembic stamp head` 把 baseline 打标，以后的 schema 变更全走新的 Alembic 版本。
- `test_alembic_baseline.py` 保证：`alembic upgrade head` 空 DB 跑出来的 schema 和 ORM `Base.metadata.create_all()` 出来的 schema 100% 对齐。

### 2.4 lint / type 工具链

`pyproject.toml` 新增：

- **ruff**：`select = ["E", "F", "I", "B", "UP"]`；`line-length = 120`；`ignore` 了 `B008`（FastAPI `Depends(...)` 默认值）、`E501`、`UP017`（`datetime.UTC` 别名）、几个 UP 样式预期。
- **mypy**：全仓 `ignore_missing_imports = true`、`follow_imports = silent`、`warn_unused_ignores = true`，严格只在 §1.4 列出的"严格岛"生效。

`requirements-dev.txt` 新增：`pytest` / `pytest-cov` / `ruff` / `mypy` / `alembic` / `httpx` 的 pin 版本。

### 2.5 FastAPI lifespan

`main.py` 把 `@app.on_event("startup")` 换成 `@asynccontextmanager` + `lifespan=lifespan`（FastAPI 0.110+ 推荐写法，避免 deprecation warning）。`pyproject.toml` 里 `filterwarnings` 暂时还保留一条 fastapi 的忽略，等 Phase 1 拆完一起清掉（实际上 Phase 1 后已经不再需要，但条目保留不碍事）。

### 2.6 .gitignore 整理

递归 `__pycache__/`（之前只忽略 `backend/__pycache__/`，不包括 `backend/alembic/__pycache__/` 等）+ `.mypy_cache` / `.pytest_cache` / `.ruff_cache`。

### 2.7 没改的

- 生产 DB 文件的 mtime / size 全程不变（所有测试走 `$TMPDIR`）。
- `main.py` 除了 lifespan 改写**没有其它重构**（Phase 1 才动）。
- ORM 模型 0 变化、schema 0 变化、任何端点 0 变化。

---

## 3. Phase 1.A 已做（commit `c1a60a9`）

### 3.1 数字对账

- `main.py`：**1701 行 → 109 行**，只保留 lifespan、CORS、10 个 `include_router`、4 个 re-export、`if __name__ == "__main__"` uvicorn 入口。
- 新增 `backend/routers/`：10 个 router 文件 + `__init__.py`，共约 1100 行。
- 新增 `backend/services/`：10 个 service 文件 + `__init__.py`，共约 1200 行（其中 `services/tasks.py` 最大，~310 行；`services/dashboard.py` 次之，~190 行）。
- 47 个端点全部验证路由表一致（重构前后 `app.routes` 列表 diff 为空）。
- 测试：59/59 → 59/59（没新增也没丢）。

### 3.2 从 `main.py` 抽出的内容去向

| 原 `main.py` 内容 | 去向 |
|---|---|
| `ensure_schema_compatibility` + `normalize_datetime_storage` | `services/schema_compat.py` |
| `add_event` / `get_task_or_404` / `serialize_task` / `task_detail_response` / recurrence 工具 / `query_tasks` / `task_load_options` | `services/tasks.py` |
| `BoardPreference` 读写 + `sort_tasks_for_board` | `services/board.py` |
| `build_today_summary` / `build_plan_summary` / `build_board_summary` / `build_history_summary` / `build_project_summaries` | `services/dashboard.py` |
| 客户材料序列化 + 引用校验 + 状态校验 | `services/customer_materials.py` |
| 客户 / 项目 V2 / 事实 / 评审批次 的序列化 | 各自 `services/*.py`（每个约 25-30 行） |
| 所有 `@app.get/@app.post/@app.patch/@app.delete` | `routers/<domain>.py` |
| lifespan / CORS / include_router / 兼容 re-export | 留在 `main.py` |

### 3.3 新增的工具模块 `services/json_utils.py`

专门为了遗留的 TEXT JSON 列（`pinned_projects_json`、`task_order_json`、`project_order_json`、`tags_json`、`aliases_json`、`source_refs_json`、`value_types_json`、`generation_meta_json`）做**容错**解析：

```python
def parse_json_object(raw_value: str | None) -> dict[str, Any]: ...
def parse_json_list(raw_value: str | None) -> list[str]: ...
```

- 不抛异常（坏数据返回空 dict / 空 list），因为旧数据可能有历史脏数据。
- `parse_json_list` 顺手做去重、去空白、字符串化。

### 3.4 领域间的内部依赖

Phase 1 强制**单向依赖**：router → service；service 之间可以相互引用，但不得引用任何 router。

实际落地的跨 service 引用（只有几处，都合理）：

- `services/dashboard.py` 依赖 `services/board.py`（dashboard 需要板自定义排序元数据）。
- `services/dashboard.py` 依赖 `services/tasks.py`（查询、序列化）。
- `routers/projects.py` 依赖 `services/board.py` + `services/dashboard.py` + `services/tasks.py`（rename 要改任务、同步板偏好、触发事件）——这是 router 编排多 service 的合法场景。
- `routers/customer_materials.py` / `routers/review_batches.py` 都调 `services/customer_materials.py::serialize_customer_material`。

### 3.5 路由注册顺序

`main.py` 里 `include_router` 调用顺序：health → preferences → projects → tasks → dashboard → customer_materials → customers → projects_v2 → facts → review_batches。顺序只影响 OpenAPI 文档里的 tag 顺序，不影响实际路由匹配。

### 3.6 没改的（防止回归的底线）

- `backend/schemas.py` 0 改动。
- `backend/models.py` 0 改动。
- `backend/alembic/` 0 改动。
- `backend/recurrence.py` 0 改动。
- `backend/timeutils.py` 0 改动。
- 任何测试文件 0 改动（测试是契约快照，拆分**不准**改）。

### 3.7 ruff 附带清理

`ruff --fix` 在重构途中触发了一些 legacy 文件的 import 整理：

- `schemas.py`：删掉一批已经不再需要的 `from models import ...`（实际已被 `Literal` 字面量替代）。
- `alembic/env.py`、`alembic/versions/612481f0ad55_baseline_schema.py`、`config.py`、`scripts/smoke_customer_materials_api.py`、`tests/test_alembic_baseline.py`：仅 import 排序 / `Union[...] → X | Y` 升级 / 多余空行。

**这些顺手的 style 改动全部和 Phase 1 一起提交在 `c1a60a9`**。按 `.codex/skills/commit/SKILL.md` 的纪律，本来应该拆一个独立 `style(...)` commit，但都是 ruff 自动产物、和重构时机耦合，合在一起可接受；下次类似情况建议分两个 commit。

---

## 4. 文档同步

### 4.1 `TASK_CENTER_API_FOR_AGENTS.md` §1 服务位置（commit `8108766`）

改动前：

```
- 后端代码：backend/main.py
- Schema 定义：backend/schemas.py
```

改动后：一张三列表（入口 / 路由 / 服务 / schema / ORM / 迁移）+ 一句导航口令「看一个端点的实现 = 先去 `routers/<domain>.py` 再跳 `services/<domain>.py`」+ 权威源从 `main.py` 改为 `routers/* + services/* + schemas.py`。

### 4.2 `TASK_CENTER_API_FOR_AGENTS.md` 顶部修订条目（commit `4dabef7`）

加了一条 2026-05-07 修订，记录 `/api/tasks` 新增 `customer_id` / `project_id` 过滤。这是 Phase 1 之后的业务增量，不是重构本身，但对 agent 来说"四类列表都能按客户聚合"是有用的指南。

### 4.3 本 Plan（本次提交）

倒序落档。没有父 Plan 可挂，本身作为 backend 工程化的 Phase 0 + Phase 1 根记录。

### 4.4 `.codex/skills/commit/SKILL.md`（commit `301ff8f`）

严格说不是 Phase 1 文档，但 Phase 1 commit 做完后**立刻**补的协作规范，覆盖：何时提交 / 提交前 pytest+ruff+mypy 检查 / 避免 `git add -A` / Conventional Commits 格式 / 不自动 push。

---

## 5. 验证

### 5.1 Phase 0 验证

- `pytest` → 59 通过。
- `ruff check .` → clean。
- `mypy recurrence.py timeutils.py config.py` → clean（严格）。
- `alembic upgrade head` 在空 DB 上 → 和 ORM create_all 结果完全对齐（`test_alembic_baseline.py`）。

### 5.2 Phase 1 验证

- **路由表对账**：提取 `app.routes` 的 `(path, methods)` 集合，重构前后完全相同（47 个业务端点 + 4 个 FastAPI 内置 `/docs` / `/redoc` / `/openapi.json` / `/docs/oauth2-redirect`）。
- `pytest` → 59 通过（之后 `4dabef7` 增到 60）。
- `ruff check .` → clean。
- `mypy .` → **严格岛 8 个新 service 全 clean**；项目级残留 91 错误全部在 legacy code（`models.py` / `scripts/` / `tests/` / `seed_demo.py`）——和 Phase 1 前基线数量一致，**0 新增错误**。
- 手测：`.venv/bin/python -c "from main import add_event, init_db, rename_project, update_task"` → 兼容 re-export 正常工作。
- `seed_demo.py` / `scripts/normalize_customer_projects.py` 的 `from main import ...` 继续工作。

### 5.3 生产 DB

**整个 Phase 0 + Phase 1 过程中生产 DB 文件 mtime / size 零变化。**

---

## 6. 风险和已知问题

### 6.1 `services/tasks.py::query_tasks` 缺返回类型

```python
def query_tasks(db: Session, *, status=..., ...,):   # 无 -> Select[...]
```

SQLAlchemy 2.x `Select[tuple[Task]]` 的类型在 mypy 严格下稍繁，Phase 1 不 block 在这里。**后果**：`services.tasks` 不在严格岛里。**后续**：Phase 2 补标注后加进去。

### 6.2 `main.py` 的兼容 re-export 是历史债

4 个 re-export 名字（`init_db` / `add_event` / `rename_project` / `update_task`）靠着几个 legacy 脚本续命。真要清理，需要同步改：

- `seed_demo.py`
- `scripts/normalize_customer_projects.py`

这是一两行的小改动，但**不属于重构 scope**，留作 Phase 2 或顺手清理。

### 6.3 `routers/projects.py` 和 `routers/projects_v2.py` 长期并存

- 前者暴露 `/api/projects`，数据来自 `Task.project` 字符串字段，board 分组依赖它。
- 后者暴露 `/api/projects-v2`，操作的是 `Project` 表，有 `customer_id` FK。

前端 / mobile 看板还在用字符串，短期内**不能删旧的**。长期计划：等所有 UI 迁到 FK 项目、并补齐 `Task.project_id` 数据后，把 `Task.project` 字段（以及整个 `routers/projects.py`）淘汰。Phase 1 的职责是**并列保留两者**，不做迁移。

### 6.4 ruff 和 Phase 1 混在同一 commit

见 §3.7。`c1a60a9` 里混入了部分 legacy 文件的 ruff 自动 fix。问题不大（全是无副作用的 style 改动），但不符合 `.codex/skills/commit/SKILL.md` §3 单一主题原则。下次做类似"大重构 + 工具自动 fix"组合时，先跑一次 `ruff --fix` 用 `style(...)` 单独提交，再做结构重构。

### 6.5 `backend/schemas.py` 没拆（Phase 1.B 待办）

~900 行单文件继续存在。在 Phase 1.B 完成前的额外注意点：如果先做 §8.3 JSON TypeDecorator，schemas 里一批 `*_json: str` 会变成 `dict / list`，改动面跨领域扩散；建议 §8.1 schemas 拆分和 §8.3 TypeDecorator 协调好顺序（推荐先拆 schemas、再做 TypeDecorator，让 TypeDecorator 的字段改写在每个 schema 文件内本地完成）。

---

## 7. 回滚路径

非常简单（因为 Phase 1 是纯结构性重构，DB / 契约 0 变化）：

```bash
git revert c1a60a9   # 回到 Phase 0 状态（1701 行 main.py）
# 如果 Phase 0 也要回：
git revert 0a71c27   # 回到工程化前的原始代码（但会丢测试脚手架 + Alembic baseline）
```

由于 `4dabef7`（customer_id 过滤）、`301ff8f`（commit skill）、`8108766`（§1 文档）都依赖新结构：

- `4dabef7` 改的是 `services/tasks.py` + `routers/tasks.py`——revert `c1a60a9` 之前必须先 revert 它，或手工把同样的两行 `customer_id/project_id` filter 挪进旧 `main.py` 的 `list_tasks` 函数。
- `301ff8f` 和 `8108766` 是纯文档，revert `c1a60a9` 也不会冲突。

**不建议回滚**——Phase 1 行为等价经过了完整测试验证，回滚只会重新背上 1701 行的技术债。

---

## 8. Phase 1.B 剩余工作

按最初的 Phase 1 范围，下面三项是必须做完的（不是可选）。建议按 §8.1 → §8.2 → §8.3 的顺序，每一项独立 commit、独立跑全套验证。

### 8.1 拆 `schemas.py`

**目标**：`backend/schemas.py` 按领域拆成 `backend/schemas/__init__.py` + `backend/schemas/<domain>.py`，和 routers / services 的命名对齐，形成「router + service + schema 三件套」。

**拆分粒度**（草案，落地时可调）：

- `schemas/common.py`：跨领域的小类型 + Literal 别名（`CustomerStatusValue` / `ProjectStatusValue` / `FactStatusValue` / `TaskStatusValue` / …）+ `normalize_project_name` 之类的 helper。
- `schemas/tasks.py`：`TaskBase` / `TaskCreate` / `TaskUpdate` / `TaskRead` / `TaskDetail` / `TaskEventRead` / `ReminderRead` / `TaskRecurrenceRead` / `TaskRecurrenceWrite` / `ProjectRenameRequest` / `BoardPreferenceRead` / `BoardPreferenceUpdate`。
- `schemas/dashboard.py`：`HealthResponse` / `NightlyReviewPlaceholder` / dashboard 系列响应。
- `schemas/customer_materials.py`：`CustomerMaterialRead` / `Create` / `Update`。
- `schemas/customers.py`：`CustomerRead` / `Create` / `Update`。
- `schemas/projects_v2.py`：`ProjectV2Read` / `Create` / `Update`。
- `schemas/facts.py`：`FactRead` / `Create` / `Update`。
- `schemas/review_batches.py`：`ReviewBatchRead` / `Create` / `Update`。
- `schemas/__init__.py`：**完全 re-export 旧 `schemas` 模块的所有公开符号**，让 `from schemas import TaskRead` 这种现有用法继续工作（routers / services / tests / scripts 全都不改）。

**风险点**：

- **循环引用**：`TaskDetail` 引用 `ReminderRead` / `TaskRecurrenceRead` / `TaskEventRead`——它们都在 `schemas/tasks.py` 里同一文件，这是合并而非循环。如果跨文件需要前向引用，用 `from __future__ import annotations` + `model_rebuild()`。
- **Pydantic v2 model_validator / field_validator**：跨模型的 validator 不要散在多文件，集中在 `schemas/<domain>.py` 内。
- **常量名稳定**：所有从 `schemas` 直接 import 的名字，**`schemas/__init__.py` 必须 100% re-export**。可以临时跑一遍 `grep -r "from schemas import" backend/ frontend/` 列出全部依赖，对账。

**验证**：60 测试全过；ruff clean；mypy 严格岛若已包含 schemas 子模块，要 clean。

### 8.2 公共 helper（routers / services 模板代码收敛）

**目标**：消除 routers / services 里观察到的几类重复模板代码。Phase 1.A 拆完之后这些重复变得显眼，但当时没动以保证「行为等价」。

**已识别的重复模式**：

1. **`json.dumps(..., ensure_ascii=False)` 散落**（routers/customers.py / projects_v2.py / facts.py / review_batches.py / customer_materials.py / preferences.py 的 PATCH/POST 都在写）。**预计 §8.3 JSON TypeDecorator 落地后会消失大部分**，但有少数动态决定的字段（如 `value_types`）依然要手写——可以提一个极薄的 `services/json_utils.py::dump_json(value)` 收敛。
2. **PATCH 里的 `clear_<fk>` 处理**：`routers/projects_v2.py::update_project_v2`、`routers/facts.py::update_fact` 都有一段「pop `clear_customer` / `clear_project` / `clear_task`，updates 里赋值后再根据 boolean 把 FK 设回 None」的样板代码。可以做一个 `apply_patch(model, updates, *, fk_clears: dict[str, str])` helper。但要小心**不要过度抽象**——就两三个 router 用，宁可重复也别造一个谁都不想读的 mini-DSL。
3. **`db.get(Model, id) → 404`**：`routers/*` 里反复写 `entity = db.get(Model, id)` + `if not entity: raise HTTPException(404, "... not found")`。FastAPI 没有内置好用的 helper；可以加一个 `services/common.py::get_or_404(db, Model, id, name="<noun>")`。**这个值得做**，覆盖面广。
4. **list 端点的 ILIKE 拼接**：`routers/customers.py::list_customers` 和 `routers/customer_materials.py::list_customer_materials` 都拿 `q` 拼 `%{q}%` 然后 `or_(field1.ilike, field2.ilike, ...)`。可以但不强求收敛，因为字段集合每个 domain 不一样。

**验证**：必须维持行为等价，所有现有测试全过。helper 本身建议加单元测试。

**反诱惑**：不要顺手把 routers / services 改成 "通用 CRUD generator"。这条路通向不可读的元编程，本仓的领域规则差异不足以支撑。

### 8.3 JSON `TypeDecorator`

**目标**：`models.py` 里所有 `*_json: Mapped[str]`（TEXT 列存 JSON 字符串）改成 `Mapped[dict[str, Any]]` / `Mapped[list[str]]`，配一个 `JSONText` `TypeDecorator`，自动 `loads` / `dumps`。

**当前 TEXT JSON 列清单**（落地前再核对一遍）：

- `Task.tags_json` (list[str])
- `BoardPreference.task_order_json` / `pinned_projects_json` / `project_order_json`（list[str] / dict[str, list[str]] / list[str]）
- `Customer.aliases_json` / `tags_json`
- `Project.tags_json`
- `CustomerMaterial.source_refs_json` / `generation_meta_json`
- `Fact.value_types_json`
- 其他可能漏掉的——靠 `grep -nE '_json' backend/models.py` 拉清单。

**实现要点**：

```python
# services/sa_types.py（新文件）
class JSONText(TypeDecorator):
    impl = Text
    cache_ok = True
    def process_bind_param(self, value, dialect):
        if value is None: return None
        return json.dumps(value, ensure_ascii=False)
    def process_result_value(self, value, dialect):
        if value is None or value == "": return None
        try: return json.loads(value)
        except json.JSONDecodeError: return None  # 容错：脏数据返回 None
```

**收益**：

- 删掉 `services/json_utils.py` 大部分代码（`parse_json_list` / `parse_json_object` 不再被 service 调用）。
- routers PATCH 里 `if "tags" in updates: customer.tags_json = json.dumps(updates["tags"], ...)` 这堆模板**全部消失**——直接 `customer.tags = updates["tags"]`。
- schemas 的 `tags_json: str` / `tags: list[str]` 双字段 + `model_validator` 拼接逻辑可以简化。

**风险**：

- **历史脏数据**：现有生产 DB 里如果某行 `tags_json` 是 `"hello"`（坏 JSON），新 ORM load 会 raise（除非 `process_result_value` 做容错——草案里返回 None）。**强烈建议**：
  1. 落地前跑一次扫描脚本，列出所有坏 JSON 的行。
  2. 选择策略：要么写 SQL 修复，要么 `process_result_value` 用 try/except 兜底返回 `None` / `[]`。
- **schema 字段语义变化**：`Task.tags` 之前是 `Mapped[str]`（TEXT JSON），现在是 `Mapped[list[str]]`。所有访问点（`task.tags_json`、`json.loads(task.tags_json)`）都要改。这是跨 routers / services / dashboard / tests 的批量改动，需要 `grep -rn "_json"` 全仓搜一遍。
- **Pydantic schema**：`TaskRead.tags: list[str]` 等字段已经是 list 形式（通过 validator 转换），落地后 validator 改简单，但**响应 JSON 字段名要保持** —— 注意 Pydantic 的 alias / serialization_alias 用法。
- **Alembic 迁移**：只是类型声明变化，SQLite 层依然 TEXT，**不需要 schema 迁移**。但建议加一条空 migration 做"标记已升级"的 marker，避免后人困惑。

**验证**：
- 所有现有 60 测试全过。
- 加专门测试覆盖 `JSONText`：None / "" / 合法 JSON / 坏 JSON 四种 round-trip。
- 起一次本地服务，对 `Customer` / `Task` / `Fact` 各做一次 list / get / patch，肉眼对比响应 JSON 和 Phase 1.A 时的版本。

### 8.4 Phase 1.B 完成的退出条件

- 60+ 测试全过（其中至少新增：schemas 拆分对账测试 1+、JSONText round-trip 测试 4、`get_or_404` 单测 2）。
- ruff clean。
- mypy 严格岛扩到 schemas 子包（每个 schema 子文件本身是纯 Pydantic，应当能进岛）。
- `services/json_utils.py` 行数从 41 降到 ≤10 或彻底删掉。
- `routers/*.py` 里 `json.dumps` 出现次数 ≈ 0（grep 验证）。
- 本 Plan 加一节「Phase 1.B 已做」记录实际落地情况，类似 §3 之于 Phase 1.A。

---

## 9. Phase 2 候选（未来工作，与 Phase 1 收尾无关）

Phase 1.B 完成之后才考虑这些。

### 9.1 `services/tasks.py::query_tasks` 补返回类型 + 进严格岛

小改动。补 `-> Select[tuple[Task]]` 类型并把 `services.tasks` 加进 mypy 严格岛，覆盖率从 80% 提到接近 100%。Phase 1.B 收尾后的第一个低成本收益点。

### 9.2 `routers/projects.py` vs `routers/projects_v2.py` 最终合并

等 UI（前端 + mobile）全部迁到 FK 项目、`Task.project_id` 数据补全后，淘汰 `Task.project` 字符串字段。跨前端 / mobile / 后端的大动作，不属于纯后端 Phase。

### 9.3 清理 `main.py` re-export

删掉 4 个 re-export（`init_db` / `add_event` / `rename_project` / `update_task`） + 改 `seed_demo.py` / `scripts/normalize_customer_projects.py`。小改动，可以任何时候顺手做；也可以不做，留着不碍事。

### 9.4 考虑删除 `services/schema_compat.py` 的手写 ALTER 链

Alembic baseline 已经覆盖了当前 schema，`ensure_schema_compatibility()` 里那条 v1 → v2 手写 ALTER 链**理论上**已经不需要了（所有新部署都走 `alembic upgrade head`）。但：

- 有没有存量生产 DB 还在用 v1？需要确认。
- 删掉后如果有 DB 没升级，启动会 500。

**建议**：等确认所有生产 DB 已经 `alembic stamp head` 后再删；或者先加一条 Alembic revision 做等价 migration，然后删手写链。

---

## 10. 附录：关键文件速查

| 文件 | 行数（2026-05-07） | 关键 |
|---|---|---|
| `backend/main.py` | 109 | 只有胶水，90% 阅读时间可跳过 |
| `backend/routers/tasks.py` | 286 | 任务端点编排 |
| `backend/routers/customer_materials.py` | 223 | 客户材料 7 个端点 |
| `backend/routers/facts.py` | 119 | 事实 CRUD |
| `backend/services/tasks.py` | 310 | 重构后最大的 service，含 recurrence |
| `backend/services/dashboard.py` | 192 | 看板 / 今日 / 计划 / 历史聚合 |
| `backend/services/schema_compat.py` | 144 | 遗留手写 ALTER 链（见 §9.4） |
| `backend/services/customer_materials.py` | 112 | 材料序列化 + 引用校验 |
| `backend/services/board.py` | 81 | 板偏好 + 自定义排序元数据 |
| `backend/services/json_utils.py` | 41 | 容错 JSON 解析（Phase 1.B §8.3 落地后大幅缩水或删除） |
| `backend/schemas.py` | ~900 | 单文件，Phase 1.B §8.1 待拆 |
| `backend/pyproject.toml` | 51 | ruff + mypy 严格岛名单 |

---

**—— Phase 0 + Phase 1.A 的目标已达成：`main.py` 不再是"所有改动的战场"，新功能（`4dabef7` 的 `customer_id` 过滤就是第一个例子）天然落在正确的 router + service 位置。Phase 1.B 三项（schemas 拆分 / 公共 helper / JSON TypeDecorator）开始执行后，会在本文件追加 §3.B 实录。**
