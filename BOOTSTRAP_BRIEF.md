# 轻量任务中心 Bootstrap Brief

> **历史文档**：这是项目初期的 MVP 启动文档。其中 `frontend/` 已归档至 `archive/frontend/`，不再维护。当前活跃前端为 `mobile_frontend/`。

## 目标
构建一个本地轻量任务中心（MVP），满足：
1. 用户可继续通过聊天自然语言新建/调整/取消/完成任务与提醒
2. 浏览器中可查看并直接操作当天与历史任务
3. 每晚 22:00 进行今日任务收口：用户回复未完成项及延期时间；已回复前提下，未提及的今日待办自动标记为已完成

## 技术路线（当前锁定）
- 前端：React
- 后端：Python FastAPI
- 持久化：SQLite
- 项目目录：`/home/velen/.openclaw/workspace/task_center`

## MVP 范围
### 必做
- 任务（Task）主对象
- 提醒（Reminder）作为任务附属对象，可一对多
- 任务状态：todo / doing / done / deferred / canceled
- 视图：
  - 今日视图（按时间排序）
  - 看板视图（按状态分组）
  - 历史视图（查看过往任务与变更）
- 任务详情操作：
  - 标记完成
  - 改时间
  - 新增提醒
  - 延期
  - 取消
  - 查看历史变更
- 操作日志 / 变更记录
- 22:00 晚间收口所需的数据支持

### 先不做
- 复杂权限系统
- 多用户
- 飞书/Notion/Bitable 同步
- 自然语言自动解析引擎（后续可接）
- 重复任务高级规则

## 建议数据模型
### tasks
- id
- title
- description
- due_at
- status
- project
- tags_json
- source (chat/web/system)
- created_at
- updated_at
- completed_at
- canceled_at
- deferred_to

### reminders
- id
- task_id
- remind_at
- channel
- status (scheduled/fired/canceled)
- note
- created_at
- updated_at

### task_events
- id
- task_id
- event_type (created/updated/status_changed/reminder_added/reminder_fired/deferred/completed/canceled/nightly_reviewed)
- payload_json
- created_at

## API 草案（可优化）
- GET /api/health
- GET /api/tasks?date=today&status=
- GET /api/tasks/:id
- POST /api/tasks
- PATCH /api/tasks/:id
- POST /api/tasks/:id/complete
- POST /api/tasks/:id/defer
- POST /api/tasks/:id/cancel
- POST /api/tasks/:id/reminders
- GET /api/history?date=&status=&q=
- GET /api/dashboard/today
- GET /api/dashboard/board
- GET /api/dashboard/history

## 前端要求（已归档，当前前端为 `mobile_frontend/`）
- React 实现，不必追求炫，先稳定可用
- 页面清晰、操作路径短
- 优先把“今日视图”和“任务详情操作”打通
- 数据层不要写死，走 API client

## 后端要求
- FastAPI + SQLite
- 数据模型清晰，迁移简单
- 给前端稳定 REST API
- 提供初始化脚本 / README / 启动说明
- 为未来接 cron 和聊天指令预留扩展点

## PM 要求
- 产出 PRD、信息架构、字段定义、状态机、交互流程、晚间收口规则、验收标准
- 对前后端进行明确分工，避免边界混乱
- 最后读代码树，给一版集成建议和下一轮迭代建议

## 协作规则
- PM 主要写 docs/ 里的产品与接口文档
- FE 主要写 mobile_frontend/（原 frontend/ 已归档至 archive/frontend/）
- BE 主要写 backend/
- 尽量避免多人同时改同一文件
- README 可以最后补，若需改共享文档，优先增量而非覆盖

## 成功标准（MVP）
- 本地可启动前后端
- 浏览器可看到今日/看板/历史 3 个核心视图
- 可以创建任务、修改任务、完成任务、延期任务、取消任务、添加提醒
- 任务变更有事件日志
- 结构上能支持 22:00 晚间收口
