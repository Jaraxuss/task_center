# 本地轻量任务中心开发交接说明

> ⚠️ 历史说明：本文档主要保留项目早期阶段的交接背景、初始分工与搭建建议，**不再作为当前项目现状的主入口**。
>
> 当前请优先阅读：
> - `../README.md`
> - `./PROJECT_OVERVIEW.md`
> - `./API_CONTRACT.md`
> - `./TIMEZONE_DESIGN.md`

## 1. 目标
本文件用于明确 React 前端与 FastAPI 后端在 MVP 阶段的职责边界、目录规范、联调方式，以及当前项目树下的集成建议，避免重复建设和边界打架。

当前项目根目录：`/home/velen/.openclaw/workspace/task_center`

当前项目现状（截至本次 PM 交付）：
- 已有：`BOOTSTRAP_BRIEF.md`
- 已补齐：`docs/PRD.md`、`docs/API_CONTRACT.md`、`docs/HANDOFF.md`、`docs/ITERATION_BACKLOG.md`
- 尚未看到前后端主体目录与初始化代码

这意味着：当前项目仍处于“规格先行”阶段，最适合按清晰目录一次性搭好骨架，然后前后端并行推进。

---

## 2. 前后端分工边界

## 2.1 前端（React）负责什么
前端负责：
1. 页面与交互实现
2. API Client 封装
3. 路由、状态管理、表单校验、列表展示
4. Task Detail 内的用户动作触发
5. Loading / Empty / Error 等体验层处理

前端不负责：
- 业务规则落库
- 状态机最终校验
- 22:00 收口判定逻辑
- 提醒调度
- 事件日志生成

### 前端最小交付件
- Today 页面
- Board 页面
- History 页面
- Task Detail 抽屉/弹层
- Create/Edit Task 表单
- Reminder 创建表单
- API Client 与类型定义

## 2.2 后端（FastAPI）负责什么
后端负责：
1. 数据模型定义（Task / Reminder / TaskEvent）
2. SQLite 持久化
3. 统一 REST API
4. 状态机校验与幂等处理
5. 每次关键变更的事件日志写入
6. 22:00 晚间收口候选集和提交处理逻辑
7. 数据初始化、迁移与启动说明

后端不负责：
- 页面布局
- 前端筛选器 UI
- 展示文案和交互细节

### 后端最小交付件
- 数据库 schema / migration
- 核心 CRUD API
- complete / defer / cancel / add reminder 动作接口
- history / dashboard / nightly-review 接口
- README 或 run guide

---

## 3. 推荐目录规范

建议尽快建立如下目录：

```text
task_center/
├── docs/
│   ├── PRD.md
│   ├── API_CONTRACT.md
│   ├── HANDOFF.md
│   └── ITERATION_BACKLOG.md
├── frontend/
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── pages/
│   │   ├── features/
│   │   │   ├── tasks/
│   │   │   ├── reminders/
│   │   │   └── history/
│   │   ├── types/
│   │   ├── hooks/
│   │   └── routes/
│   ├── public/
│   └── package.json
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── models/
│   │   ├── schemas/
│   │   ├── services/
│   │   ├── repositories/
│   │   ├── db/
│   │   └── main.py
│   ├── migrations/
│   ├── tests/
│   ├── requirements.txt
│   └── README.md
└── scripts/
    ├── dev.sh
    └── init_db.sh
```

### 目录职责说明
- `frontend/src/api/`：统一封装 API 请求，不允许页面里直接散写 fetch。
- `frontend/src/types/`：放接口模型与前端类型。
- `frontend/src/features/`：按业务域组织，不按“纯组件”堆砌。
- `backend/app/api/`：路由层，只做请求接收和响应组装。
- `backend/app/services/`：业务逻辑，例如任务完成、延期、晚间收口。
- `backend/app/repositories/`：数据库读写。
- `backend/app/schemas/`：Pydantic 请求/响应模型。
- `backend/app/models/`：ORM 模型或数据实体。

---

## 4. 前后端接口协作原则

## 4.1 单一事实来源
- 字段定义以 `docs/API_CONTRACT.md` 为准。
- 业务范围以 `docs/PRD.md` 为准。
- 若前后端实现与文档冲突，先改文档再改代码，避免“口头约定”。

## 4.2 接口边界
- 列表页优先使用 dashboard/history 聚合接口。
- 详情页优先使用 `/api/tasks/{id}`。
- 完成 / 延期 / 取消走专用 action API。
- 前端不得直接 PATCH `status=done/deferred/canceled` 替代专用动作。

## 4.3 事件日志原则
以下动作必须写 `task_events`：
- 创建任务
- 编辑任务基础信息
- 状态变更
- 新增提醒
- 取消提醒（若实现）
- 晚间收口处理

---

## 5. 联调方式

## 5.1 联调顺序建议
### 第 1 阶段：后端先出 contract-ready mock 真接口
后端优先提供：
1. `GET /api/health`
2. `GET /api/dashboard/today`
3. `GET /api/tasks/{id}`
4. `POST /api/tasks`
5. `POST /api/tasks/{id}/complete`
6. `POST /api/tasks/{id}/defer`
7. `POST /api/tasks/{id}/cancel`
7. `POST /api/tasks/{id}/reminders`

前端先打通 Today + Task Detail。

### 第 2 阶段：补齐 Board / History
后端补齐：
- `GET /api/dashboard/board`
- `GET /api/history` 或 `GET /api/dashboard/history`

前端补齐两个页面。

### 第 3 阶段：补齐晚间收口
后端实现：
- `GET /api/nightly-review/candidates`
- `POST /api/nightly-review/commit`

前端此阶段可只做只读展示，不一定要完整操作页。

## 5.2 本地开发约定
建议端口：
- Frontend: `http://localhost:5173`
- Backend: `http://localhost:8000`

建议前端通过 dev proxy 转发 `/api` 到后端，避免本地开发阶段 CORS 噪音。

## 5.3 Mock 与真接口切换
- 前端允许短期使用 mock 数据开发 UI。
- 但提交联调分支前，必须切换为 API client，不能保留写死 mock 逻辑。
- 若接口未就绪，可用 `fixtures/` 模拟，但 shape 必须与 API contract 完全一致。

---

## 6. 任务拆分建议

## 6.1 前端任务拆分
1. 搭脚手架、路由、Layout
2. 类型定义与 API client
3. Today 页
4. Task Detail 抽屉
5. Create/Edit Task 表单
6. Reminder 表单
7. Board 页
8. History 页
9. 全局错误与空态

## 6.2 后端任务拆分
1. 搭 FastAPI 工程骨架
2. SQLite 连接与 migration
3. ORM / schema 建模
4. Task CRUD
5. 状态动作接口
6. Reminder 接口
7. Event 写入逻辑
8. Dashboard / History 聚合接口
9. Nightly Review 服务

---

## 7. 集成建议（基于当前项目树）

当前项目树只有 bootstrap brief 和 docs，说明还没有真实的前后端脚手架。这反而是好事：现在最适合一次性把目录、契约和边界定死，避免后面“先写了再补规范”导致返工。

### 建议的集成策略
1. **先搭空骨架，再并行开发**：先创建 `frontend/` 与 `backend/` 目录和最小启动工程，保证 repo 结构稳定。
2. **先接口后页面细化**：后端先按 `API_CONTRACT.md` 提供最小可用接口，前端优先做 Today + Task Detail，不要一上来铺太多页面。
3. **聚合接口与资源接口并存**：Today/Board/History 页面走聚合接口，详情与动作走资源接口，这样前端页面逻辑会轻很多。
4. **事件日志做成后端强约束**：不要指望前端提醒后端写事件；凡是关键动作都在 service 层统一写 event，避免漏记。
5. **22:00 收口先做后端能力，不急着做 UI**：这个能力主要服务聊天接入层，前端 MVP 只要能查看结果和历史即可。
6. **共享变更只改 docs**：当前阶段 README、接口说明、字段名等共享内容都以 docs 为主，减少 FE/BE 同时改同一文件的概率。

一句话：这项目现在最怕的不是代码少，而是前后端各自脑补。先把 contract 当法律，开发会顺很多。

---

## 8. 风险与注意事项
- 风险 1：前端直接以页面需求驱动字段扩张，导致后端返回结构频繁变化。
- 风险 2：后端把数据库字段直接暴露给前端，例如 `tags_json`。
- 风险 3：晚间收口规则口头理解不一致，导致自动完成逻辑误伤任务。
- 风险 4：Board 页若一开始就做拖拽，MVP 会平白增加复杂度。

### 建议
- MVP 不做拖拽，状态变更用按钮。
- 先稳定字段和 API，再追求交互“丝滑”。
- 所有状态动作都以 service 层单点收口。

---

## 9. 交付检查清单

### 前端完成定义
- [ ] 能启动 React 项目
- [ ] 能调用真实 `/api`
- [ ] Today / Board / History 页面可访问
- [ ] 任务详情操作打通
- [ ] 页面具备空态/错误态

### 后端完成定义
- [ ] 能启动 FastAPI
- [ ] SQLite 可初始化
- [ ] 核心 API 可用
- [ ] 状态动作会写事件日志
- [ ] 晚间收口接口可用

### 联调完成定义
- [ ] 前后端在本地连通
- [ ] 创建任务到页面展示闭环完成
- [ ] 完成/延期/取消在 UI 和数据库中均正确反映
- [ ] 历史事件可见

结论：先把“Today + Detail + Task actions”做透，MVP 才算站稳；Board、History 和 Nightly Review 是扩展，不是先后端互相拖住的借口。