# Task Center

本项目是一个面向日常任务管理与提醒协同的本地任务中心，目标是把 **聊天侧的任务编排**、**浏览器里的可视化操作**、以及后续可能扩展的 **移动端查看与处理** 收到同一套数据与规则里。

## 现在的工程结构

当前项目由 **2 个活跃代码单元** 组成（桌面端已归档）：

1. **`backend/`**
   - FastAPI + SQLite
   - 负责任务、提醒、事件日志、周期任务、dashboard 聚合接口
   - 是整个系统的单一数据事实来源

2. **`mobile_frontend/`**
   - React + TypeScript + Vite
   - 独立移动端前端
   - **它是一个独立 git 仓库**，不和主仓历史混在一起

3. **`archive/frontend/`**（已归档，不再维护）
   - 原桌面 Web 前端，详见 `archive/README.md`

> 说明：`backend/` 位于主仓；`mobile_frontend/` 是嵌套的独立子仓。

## 先看哪里

如果是第一次接手，建议按这个顺序看：

1. `docs/PROJECT_OVERVIEW.md` —— 当前项目现状、三块代码职责、修改落点、联动关系
2. `docs/API_CONTRACT.md` —— 接口与字段约定
3. `docs/TIMEZONE_DESIGN.md` —— 当前时间语义，避免改时间逻辑时踩雷
4. `backend/README.md` / `mobile_frontend/README.md` —— 各自启动方式

## 当前关键约定

### 1. 数据与业务真相在后端
- `backend/` 是单一事实来源
- 前端可以做展示层兼容，但不要把核心业务规则偷偷分叉到前端

### 2. 时间语义已经统一
当前采用：

- **数据库：UTC aware 时间存储**
- **API：ISO 8601 UTC 字符串**
- **展示与按日分组：`Asia/Shanghai`**

改时间相关逻辑前，先读：`docs/TIMEZONE_DESIGN.md`

### 3. 移动端是独立仓
- `mobile_frontend/` 改动要在子仓里单独提交
- 不要把它当作主仓普通子目录一起 commit

### 4. 桌面端已归档
- `archive/frontend/` 保留历史但不再维护，不在 CI 上构建

## 开发时最常见的修改落点

- 改任务数据模型 / API / 周期任务：`backend/`
- 改手机端视图与交互：`mobile_frontend/`
- 改跨端公共语义（例如时间规则、字段口径、状态约定）：优先先改后端和 docs，再补前端适配

## 最近值得记住的一次演进

当前项目已经完成一轮比较重要的时间治理：

- 后端时间字段统一按 UTC aware 存储
- API 输入输出统一为 ISO 8601 UTC
- Web / Mobile 的今日、逾期、计划分组都改成按北京时间语义判断

因此，后续如果看到：
- `slice(0, 10)` 直接截日期
- 裸 `new Date()` 做业务日期判断
- naive datetime 直接写库

都应该优先怀疑，而不是继续沿用。

## 文档导航

- `docs/PROJECT_OVERVIEW.md`：**当前项目总览（推荐入口）**
- `docs/PRD.md`：产品目标与范围
- `docs/API_CONTRACT.md`：接口契约
- `docs/TIMEZONE_DESIGN.md`：时间系统设计
- `docs/HANDOFF.md`：早期交接文档（偏历史阶段说明）
- `docs/ITERATION_BACKLOG.md`：迭代积压

如果你是要“快速上手修改”，不要先埋头翻所有代码，先看 `docs/PROJECT_OVERVIEW.md`。