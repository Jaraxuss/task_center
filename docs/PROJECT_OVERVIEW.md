# Task Center 项目总览（当前可快速接手版）

> 目标：当聊天上下文被清空、或接手人不是刚参与过上一轮开发时，能在 5~10 分钟内重新建立正确心智模型，知道应该改哪里、先读哪里、哪些地方最容易误踩。

---

## 1. 这是什么项目

`task_center` 是一个围绕“任务 + 提醒 + 周期任务 + 操作历史 + 晚间收口”构建的本地任务中心。

它不是单纯待办列表，而是希望同时承接三类能力：

1. **聊天侧任务编排**
   - 用户可通过聊天创建、改时间、延期、完成、取消任务
   - 后续也可继续挂接 reminder / cron / task_center 主账本协同

2. **桌面 Web 可视化操作**
   - 在浏览器里查看 Today / Plan / Board / History
   - 直接在任务详情里做完成、延期、取消、改时间、加提醒等动作

3. **移动端轻量处理**
   - 用手机快速看今天、计划、看板、历史
   - 以移动端友好的轻详情和操作流处理任务

---

## 2. 当前工程怎么拆

当前项目由 **2 个活跃代码单元** 组成（桌面端已归档）：

### A. `backend/`
- 技术栈：FastAPI + SQLAlchemy + SQLite
- 角色：系统数据与业务规则的单一事实来源
- 负责：
  - Task / Reminder / TaskEvent / TaskRecurrence
  - dashboard 聚合接口
  - 状态流转
  - 周期任务 next run 计算
  - 历史事件记录
  - 数据初始化与兼容迁移

### B. `mobile_frontend/`
- 技术栈：React + TypeScript + Vite
- 角色：独立移动端前端
- 特别注意：**它是独立 git 仓库**
- 负责：
  - 手机端 Today / Plan / Board / History
  - 移动端详情层与基础任务动作
  - 针对触屏与窄屏重新组织信息架构

### C. `archive/frontend/`（已归档）
- 原桌面 Web 前端（React + TypeScript + Vite），不再维护。
- 最后功能提交：`7986760 fix align web task dates with Asia/Shanghai semantics`。
- 详见 `archive/README.md`。

### 仓库边界说明
- **主仓**：`task_center/`
  - 包含 `backend/`、`docs/`、`archive/`
- **子仓**：`task_center/mobile_frontend/`
  - 独立提交、独立历史

因此改代码时要先判断：
- 这是后端逻辑？
- 这是移动端？

不要把 `mobile_frontend/` 当成主仓普通目录一起 commit。

---

## 3. 现在最重要的系统约定

## 3.1 后端是业务真相源
凡是涉及：
- 状态流转
- 事件落账
- 周期规则
- dashboard 聚合口径
- 时间语义

优先以后端实现为准。前端可以适配展示，但不要悄悄长出第二套规则。

## 3.2 时间语义已经做过一轮统一治理
当前约定是：

- **DB 存 UTC aware 时间**
- **API 返回 ISO 8601 UTC 字符串**
- **前端展示与按日分组统一按 `Asia/Shanghai`**

这意味着后续改时间逻辑时，以下写法都要谨慎：

- `slice(0, 10)` 直接拿日期
- 裸 `new Date(value)` 后直接按宿主时区做业务判断
- naive datetime 直接写库

详细文档见：`docs/TIMEZONE_DESIGN.md`

## 3.3 Web 与 Mobile 时间语义已对齐
最近已经专门修过：
- 今日统计
- 逾期判断
- 计划分组
- 历史日期分桶
- `datetime-local` 输入输出

所以如果后面又出现“北京时间看起来对，但分组不对”，优先检查：
- 有没有绕开现有 utils / helper
- 有没有重新引入裸日期截断逻辑

---

## 4. 典型修改应该落在哪

### 场景 1：改任务字段 / API / 状态流转
先看：
- `backend/models.py`
- `backend/schemas.py`
- `backend/main.py`

### 场景 2：改周期任务
先看：
- `backend/recurrence.py`
- `backend/main.py`
- `backend/models.py`

### 场景 3：改手机端页面展示或详情交互
先看：
- `mobile_frontend/src/App.tsx`
- `mobile_frontend/src/api.ts`
- `mobile_frontend/src/utils.ts`

### 场景 4：改“跨端共识”
比如：
- 状态含义
- 时间口径
- dashboard 统计口径
- API 字段解释

建议顺序：
1. 先改 docs
2. 再改 backend
3. 最后补 mobile_frontend 适配

---

## 5. 当前几个关键文件的意义

### 后端
- `backend/main.py`
  - 路由入口 + 大量聚合/动作逻辑
  - 当前不算很薄，改动前最好先搜索关联函数
- `backend/models.py`
  - SQLAlchemy 模型
  - 现在时间字段已统一走 UTC aware 存取封装
- `backend/schemas.py`
  - Pydantic 输入输出模型
  - 时间输入标准化也在这里做了一层
- `backend/recurrence.py`
  - 周期规则核心计算
- `backend/timeutils.py`
  - 当前时间语义辅助函数集中处

### 移动端
- `mobile_frontend/src/App.tsx`
  - 页面主体与移动端交互流
- `mobile_frontend/src/api.ts`
  - 移动端 API adapter
- `mobile_frontend/src/utils.ts`
  - 移动端时间/分组工具函数

---

## 6. 当前已知“别乱碰”的坑位

### 6.1 `docs/HANDOFF.md` 是历史文档，不是当前真相快照
它更像项目早期的分工/初始化交接记录。

可以参考，但不要默认里面描述的“项目现状”仍然准确。

### 6.2 主仓会看到 `mobile_frontend/` 显示成一个目录
这是因为它本身是嵌套独立 git 仓。

- 对主仓提交：不要顺手把它当普通目录处理
- 对移动端修改：进入 `mobile_frontend/` 单独 commit

### 6.3 时间问题往往不是 UI 小 bug，而是语义 bug
如果你只是把显示格式修漂亮，但没有统一：
- 存储
- API
- 分组
- 表单输入

那后面大概率还会复发。

---

## 7. 本地启动与验证入口

### 主仓后端
看：`backend/README.md`

### 移动端
看：`mobile_frontend/README.md`

### 快速验证思路
改完代码后，通常最小验证是：

1. 后端：至少确认 Python 代码可编译/启动
2. 移动端：`npm run build`

如果改的是时间语义或 dashboard 逻辑，最好顺带人工检查：
- 今日
- 计划
- 历史
- 任务详情里的时间展示

---

## 8. 最近一轮关键改动（值得保留脑图）

### 8.1 跟进结果展示
桌面与移动端详情页都已经补了“跟进结果”展示：
- 优先展示 `completion_note`
- 周期任务回到 `todo` 后，也会尝试从最近一次完成/推进事件里回看 note

### 8.2 时区治理
这是近期更大的一条主线：
- 后端时间字段统一按 UTC aware 存储
- recurrence 带 timezone 计算
- 启动时会规范化旧 datetime 存量
- Web / Mobile 都按北京时间语义做 today/plan/history 分组

所以接下来如果还要继续演进时间系统，应该延续这条线，而不是回退到 naive datetime 模式。

---

## 9. 推荐阅读顺序（清上下文后重建认知用）

如果后续聊天上下文被清掉，建议重新按这个顺序读：

1. `README.md`
2. `docs/PROJECT_OVERVIEW.md`
3. `docs/API_CONTRACT.md`
4. `docs/TIMEZONE_DESIGN.md`
5. 按任务类型进入对应代码目录

这样可以最快重新建立：
- 项目目标
- 三块代码单元的边界
- 哪些规则已经定死
- 下一刀应该落在哪

---

## 10. 一句话总结

把 `task_center` 理解成：

> **一个以后端为真相源、桌面与移动双前端消费、并且已经开始认真治理时间语义的任务中心系统。**

后续接手时，最重要的不是“会不会改 React/FastAPI”，而是先别把这三层边界和时间口径重新改乱。