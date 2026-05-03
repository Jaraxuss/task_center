# Customer Materials API 收口改造清单

创建时间：2026-05-03
背景：当前 TaskCenter 后端同时存在 `/api/customer-materials` 与 `/api/customer-materials-v2` 两套客户材料接口。它们不是简单版本差异，而是旧材料模型与新“客户/项目/审核批次/周期材料”模型并存，导致 agent/cron 调用方需要猜接口，容易出现字段调试和流程分叉。

---

## 1. 收口目标

只保留一个公开入口：`/api/customer-materials`。

`/api/customer-materials` 应承载新模型字段；旧字段仅作为兼容层保留，不再驱动新流程。

最终状态：

- Agent、cron、Skill、文档都只调用 `/api/customer-materials`。
- `/api/customer-materials-v2` 不再作为公开 API 出现在 Agent 文档中。
- 若短期需要兼容，`v2` 路由只能作为内部 alias/过渡层，不能再形成第二套业务语义。

---

## 2. 当前问题

### 2.1 两套路由并存

当前代码中同时存在：

- `GET/POST/PATCH/DELETE /api/customer-materials`
- `GET/POST/PATCH /api/customer-materials-v2`
- `POST /api/customer-materials-v2/{id}/mark-uploaded`
- `GET/POST /api/customer-materials-v2/{id}/facts`
- `GET /api/review-batches/{id}/customer-materials`

### 2.2 两套 Schema 并存

当前 Schema 大致分为：

旧模型：

- `CustomerMaterialCreate`
- `CustomerMaterialUpdate`
- `CustomerMaterialRead`

新模型：

- `CustomerMaterialV2Create`
- `CustomerMaterialV2Update`
- `CustomerMaterialV2Read`

### 2.3 语义不一致

旧模型更像“通用客户材料/备注”：

- `project`
- `source_type`
- `candidate_markdown`
- `review_note`
- `task_id`

新模型更像“审核批次驱动的周期材料”：

- `customer_id`
- `project_id`
- `review_batch_id`
- `material_type`
- `period_start`
- `period_end`
- `raw_facts_markdown`
- `summary_markdown`
- `insights_markdown`
- `generation_meta_json`

这会导致调用方不知道该以哪个接口为准，也会让后续 Skill/cron 实现出现“调字段而不是按稳定契约开发”的问题。

---

## 3. 推荐保留方案

### 3.1 保留 `/api/customer-materials`

原因：

1. 这是已有公开路径，兼容成本最低。
2. `TASK_CENTER_API_FOR_AGENTS.md` 已明确写了“保留现有路径 `/api/customer-materials`，迁移到新字段”。
3. 新旧能力可以在同一路径下渐进迁移，避免让 agent/cron 分辨 v1/v2。

### 3.2 下线或内部化 `/api/customer-materials-v2`

建议分两阶段：

- 阶段 A：`v2` 路由保留为 alias，但内部直接复用 `/api/customer-materials` 的 service/schema 逻辑。
- 阶段 B：确认无调用方依赖后，从文档和代码中删除 `v2` 路由。

如果当前没有外部稳定调用方，优先直接删除 `v2` 公开路由，减少维护面。

---

## 4. 具体改造清单

### 4.1 Schema 收口

把新模型字段并入主 Schema：

- `CustomerMaterialCreate`
- `CustomerMaterialUpdate`
- `CustomerMaterialRead`

主 Schema 应支持：

- `customer_id`
- `project_id`
- `review_batch_id`
- `title`
- `material_type`
- `period_start`
- `period_end`
- `raw_facts_markdown`
- `summary_markdown`
- `insights_markdown`
- `status`
- `generation_meta_json` / `generation_meta`
- `created_at`
- `updated_at`

兼容字段可继续存在，但标为 legacy：

- `project`
- `source_type`
- `candidate_markdown`
- `review_note`
- `task_id`

### 4.2 路由收口

`/api/customer-materials` 需要覆盖当前 v2 的主要能力：

- `GET /api/customer-materials`
  - 支持按 `customer_id`、`project_id`、`review_batch_id`、`status`、`material_type` 过滤。
  - 可继续兼容旧 `project` 查询。
- `POST /api/customer-materials`
  - 创建新周期材料。
  - 支持写入 raw facts、summary、insights、generation meta。
- `GET /api/customer-materials/{id}`
  - 返回统一 Material Read 模型。
- `PATCH /api/customer-materials/{id}`
  - 支持审核编辑、状态修改、内容调整。
- `POST /api/customer-materials/{id}/mark-uploaded`
  - 标记上传完成。
- `GET /api/customer-materials/{id}/facts`
  - 查询材料关联 facts。
- `POST /api/customer-materials/{id}/facts`
  - 添加材料-fact 关联。

### 4.3 Review Batch 相关接口调整

保留审核批次接口，但不要返回独立 v2 schema。

- `GET /api/review-batches/{id}/customer-materials`
  - 返回统一 `CustomerMaterialRead`。
  - 内部等价于 `GET /api/customer-materials?review_batch_id={id}`。

### 4.4 Service/序列化逻辑收口

当前若存在 `serialize_material_v2` 一类函数，需要改成统一序列化函数：

- `serialize_customer_material`
- 或直接通过 Pydantic `from_attributes` 输出

不要维护两套字段映射。

### 4.5 文档收口

更新 `TASK_CENTER_API_FOR_AGENTS.md`：

- 删除或迁移 `/api/customer-materials-v2` 示例。
- 明确新流程只调用 `/api/customer-materials`。
- 保留 legacy 字段说明，但标明“不再作为新流程主字段”。
- 增加 agent/cron 推荐调用样例。

### 4.6 调用方收口

后续新 Skill / cron 实现时：

- 只调用 `/api/customer-materials`。
- 不允许在调用方写“如果 v1 失败再试 v2”这种兼容猜测。
- 如果字段不匹配，应改后端契约，而不是在 agent 侧反复调试 payload。

### 4.7 测试/验证

最小验证建议：

1. `python3 -m py_compile backend/main.py backend/models.py backend/schemas.py`
2. 若有测试框架，补充以下用例：
   - 创建新字段 material 成功。
   - 通过 `customer_id/status` 查询成功。
   - 通过 `review_batch_id` 查询成功。
   - mark uploaded 成功。
   - material facts 添加/查询成功。
   - legacy `project` 查询仍不破坏旧数据。
3. 启动 FastAPI 后手动 curl 关键路径。

---

## 5. 实现顺序建议

1. 先统一 Schema：主 `CustomerMaterial*` 吃下 v2 字段。
2. 再把 `/api/customer-materials` 路由补齐 v2 能力。
3. 改 review batch 返回统一 schema。
4. 把 `v2` 路由改成 alias 或删除。
5. 更新文档，确保 Agent 只看到一套路由。
6. 跑最小验证。
7. 单独提交这次 API 收口改造。

---

## 6. 给执行 model 的一句话任务

请把 TaskCenter 的客户材料 API 收口为单一路径 `/api/customer-materials`：主 Schema 合并现有 v2 字段，旧字段保留兼容但不再作为新流程主字段；补齐 mark-uploaded 与 material-facts 能力；将 `/api/customer-materials-v2` 删除或降级为内部 alias；更新 `TASK_CENTER_API_FOR_AGENTS.md` 并完成最小验证。
