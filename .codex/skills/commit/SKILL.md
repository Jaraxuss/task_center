---
name: commit
description: Lightweight commit discipline for the task_center monorepo. Use when wrapping up a unit of work (a feature step, a refactor phase, a fix, a docs update) to produce a clean, atomic git commit with a Conventional-Commits message. Also use as a checklist before pausing or handing off.
argument-hint: "[scope (backend, mobile, frontend, docs, plan, agent-api...)]"
---

# Commit skill — 何时提交、怎么提交

这个 skill 不是工作流自动化，而是一份**纪律清单**：每次写完一段可独立工作的代码/文档，就走一遍这套流程，避免出现"巨型提交"或"混杂提交"。默认在 task_center 仓库根目录执行。

---

## 1. 何时提交（trigger）

只要满足下面任一条件，就应该停下来提交：

- 完成了一个**可独立描述的逻辑单元**（一个 phase、一个 bug 修复、一个新端点、一次文档修订、一次依赖升级）。
- 准备**切换上下文**（去做另一个无关任务、暂停、交班给用户）。
- **测试/lint/类型检查全绿**，且修改集合自洽。
- 文件树里出现了**和当前任务无关的脏改动**——说明该提一次了，把无关改动单独处理。

**反模式**：
- "等全部 phase 都做完再一次性提交"——会丢失中间历史，回滚成本高。
- "改了 10 个文件，commit message 写成 'wip'"——半年后没人能理解。
- `git add -A` / `git commit -am`——会把未审阅的文件一起提进去。

---

## 2. 提交前检查（pre-commit checklist）

按子项目分别检查，只跑和当前 diff 相关的那一类：

### 2.1 Backend（`backend/`）

```bash
cd backend
.venv/bin/python -m pytest -q
.venv/bin/python -m ruff check .
.venv/bin/python -m mypy .
```

- pytest 必须全绿。
- ruff 必须 0 error；如果是新引入的、可自动修的格式问题，可以 `--fix` 后再次检查。
- mypy 严格岛（`pyproject.toml` 的 `tool.mypy.overrides`）必须 0 error。整体仓库残留的 legacy 错误不阻塞，但**不能新增**。

### 2.2 Frontend / Mobile（`frontend/`、`mobile_frontend/`）

按各自子项目的 `package.json` 跑 lint/typecheck/build。Mobile 是 git submodule，提交规则在子模块自身仓库内执行；父仓库这边只 bump submodule 指针。

### 2.3 文档/Plan（`Plan/`、`docs/`、`*.md`）

- 检查 markdown 渲染是否完整（无半截代码块、无悬挂表格）。
- 涉及 API 契约的更新，确认 `TASK_CENTER_API_FOR_AGENTS.md` 已同步。

---

## 3. 工作树整理（staging discipline）

- **审阅 diff**：先 `git status`，再 `git diff` 看具体内容。每个文件都要心里有底"为什么改它"。
- **显式 add**：列出真正属于这次提交的文件，逐个或按目录 `git add`，**不要** `git add -A`。
- **隔离无关改动**：
  - 自己的临时脚本、半成品、`.bak` 文件——`rm` 或留作后续 untracked。
  - 子模块（`mobile_frontend`、其它 submodule）的指针变化——只在确实要 bump 的提交里 add，否则保持 unstaged。
  - 仅由格式化工具产生的 churn——可单独成一次 `style(...)` 提交。
- **二次审阅**：`git diff --staged` 确认 staging 区只包含本次主题的变更。

---

## 4. 提交信息规范（message）

采用 **Conventional Commits + scope**，subject 简洁，正文解释 why。subject 中英文混排可，但术语要稳定。

### 4.1 格式

```
<type>(<scope>): <短描述，<= 72 字符>

<可选正文：解释 why、what 的动机、影响面、回滚提示>

<可选 footer：BREAKING CHANGE / Co-authored-by / Refs #...>
```

### 4.2 type 取值

| type       | 用途                                                                 |
| ---------- | -------------------------------------------------------------------- |
| `feat`     | 新功能、新端点、新页面                                               |
| `fix`      | 修 bug                                                               |
| `refactor` | 内部重构，无外部行为变化                                             |
| `docs`     | 仅文档/注释/Plan                                                     |
| `chore`    | 构建脚本、依赖、submodule bump、工具配置                             |
| `test`     | 仅新增/修改测试                                                      |
| `style`    | 仅代码格式化、import 排序，无逻辑变化                                |
| `perf`     | 性能优化                                                             |

### 4.3 scope 取值

按子项目或子领域命名，保持稳定（参见 `git log` 历史）：

- `backend`、`mobile`、`frontend`、`agent-api`、`tasks`、`plan`、`docs`、`recurrence`、`customer-materials`、`board`、`projects`，等等。
- 一次提交只聚焦一个 scope；跨 scope 的改动应当拆分为多次提交。

### 4.4 示例（参考本仓库历史）

```
feat(tasks): add source_type label field
fix align web task dates with Asia/Shanghai semantics
refactor(backend): Phase 1 — split main.py into routers + services
docs(plan): add 2026-05-04 customer knowledge revision plan
chore(mobile): bump mobile_frontend submodule (Phase 2 Knowledge tab)
```

### 4.5 写正文的判断

- subject 一行能讲清楚的（typo、rename、依赖小升级）→ 不写正文。
- 影响多个模块、引入新约定、有迁移风险、改动 > ~50 行 → 写正文，分点列出：
  - 做了什么（what changed）
  - 为什么（why，动机/上游需求）
  - 验证（tests/lint/手测结论）
  - 已知遗留 / 跟进项

---

## 5. 提交后

- 不立刻 `git push`；除非用户明确要求或当前分支是个人临时分支。`main` 上的提交先在本地堆积，等用户审阅或主动 push。
- 在对话里**简要回报**这次提交的 hash 和主题，方便用户一眼对账。
- 如果还有遗留 TODO（推迟的子任务、已识别的后续优化），用 `todo_list` 工具记录，不要靠记忆。

---

## 6. 快速口令版（折叠）

> **写完一段** → `git status` → 审 diff → 跑测试/lint → 显式 `git add` → `git diff --staged` 复核 → `git commit -m "<type>(<scope>): ..."` → 简要回报。**不要** `add -A`，**不要** `wip` 信息，**不要** 顺手 push。
