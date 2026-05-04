# TaskCenter 客户知识链路修订计划（2026-05-04）

创建时间：2026-05-04
负责人：南哥 / OpenClaw main / Cascade
目标：在 2026-05-03 已落地的 5 表架构（customers / projects / facts / customer_materials / review_batches / customer_material_facts）和 v1/v2 收口基础上，把"周期客户材料生成"和"事实写入"两条核心链路从"靠主代理 LLM 实时判断"改为"确定性脚本 + SKILL 硬约定"，从根本上解决：
- 周期 cron agentTurn 在客户/事实量上来后必然超时；
- 主代理对 fact 是否要写、写成什么内容的判断每次不一致，导致 NotebookLM 客户画像质量随机。

---

## 0. 与原计划的关系

### 0.1 仍然有效的部分

- `Plan/2026-05-03-customer-knowledge-roadmap.md` 第 1~2 节（业务目标、最终表结构）整体保留。
- `Plan/2026-05-03-customer-materials-api-consolidation.md` 全部保留（v1/v2 收口已基本落地）。
- 不改桌面前端、不改 `feishu-task` Skill、不改第三方 `nblm` Skill。
- 不给 TaskCenter 配 LLM / NotebookLM API Key。
- 任务表保留旧 `project` 字段做兼容，新流程使用 `area / customer_id / project_id`。

### 0.2 本次修订替换的条目

| 原计划位置 | 原方案 | 本次替换为 |
|---|---|---|
| roadmap 5.1 周期 cron payload | isolated agentTurn，让 LLM 生成 `raw_facts_markdown` / `summary_markdown` / `insights_markdown` | **Python 脚本**，**只生成 `raw_facts_markdown`**，summary/insights 字段保留但永远为空 |
| roadmap 4.3 fact 自动写入规则 | 主代理按软性规则在多种场景判断写不写 fact | **后端不派生 fact**；SKILL 硬约定：转发/截图/会议纪要场景 openclaw 必须两步走（先建 task 后建 fact），其他场景一律不写 fact |
| roadmap 2.4 customer_materials | 上传 markdown 拼接三层标题（完整事实/简要纪要/洞察建议） | **只保留事实层**：`# {customer}｜{project}｜{period}` + raw_facts，summary/insights 不参与拼接 |
| roadmap 2.4 字段废弃 | `candidate_markdown / review_note` 等已废弃 | 加上：`summary_markdown / insights_markdown` 在新流程中不写入但**字段保留**（避免迁移破坏） |
| roadmap 6 子任务 C 周期生成器 | "第一版可让 agentTurn 负责 LLM 生成" | 撤销。改为纯 Python 脚本入口，禁用 LLM |

---

## 1. 核心决策汇总

### 1.1 cron 链路

- 触发：北京时间每周日 20:00。
- 执行：Python 脚本，**不调 LLM、不走 agentTurn**。
- 内容：拉本周 `confirmed` facts → 按 `customer_id + project_id` 分组 → 建 `review_batch` → 为每组建一份 `customer_material`，只填 `raw_facts_markdown`，`summary_markdown` / `insights_markdown` 留空 → 建 `customer_material_facts` 关联。
- 一致性检查：脚本退出前扫本周 `tasks.source_type ∈ {forwarded_message, screenshot, meeting_note}` 但**无关联 fact** 的 task，作为 warning 列入通知。
- 通知：飞书消息只发"batch_id + 每份 material 的 id/客户/项目 + warning 列表"，**不发全文**，让南哥到 TaskCenter 移动端审核。

### 1.2 上传链路

- 南哥审核完成后，飞书回复格式：`审核完成 #A #B #C`（或 `审核完成 batch #N` 表示该批所有 approved 的）。
- OpenClaw 主代理：
  1. 按 id 列表读 customer_materials。
  2. 过滤 `status='approved'`，跳过其他状态并简短报告跳过原因。
  3. 拼 markdown：

     ```markdown
     # {customer.name}｜{project.name 或 客户级}｜{period_start} ~ {period_end}

     {raw_facts_markdown}
     ```

  4. 调 nblm Skill 上传到对应客户 NotebookLM。
  5. `POST /api/customer-materials/{id}/mark-uploaded`。
  6. 回报南哥每份 material 上传成败。

### 1.3 Fact 写入链路

- 后端**完全不派生 fact**：`POST /api/tasks/{id}/complete` 不再有任何 fact 副作用。
- SKILL 硬约定：openclaw 在以下场景必须两步走：
  - 用户**转发飞书消息/会话记录**：`source_type='forwarded_message'`
  - 用户**发截图**：`source_type='screenshot'`
  - 用户**给会议纪要**：`source_type='meeting_note'`
  - 步骤：
    1. `POST /api/tasks`，task 字段 + `source_type` 标签。
    2. `POST /api/facts`，`task_id=新建task.id`、`raw_markdown=原始内容（不删减、不加工，截图转写为多人对话原文 + 图片描述）`、`source_type=同上`、`status='confirmed'`、`customer_id/project_id` 同 task。
- 普通提醒任务（`source_type='user_chat'` 或不填）：**不写 fact**。
- 不伴随 task 的纯事实场景（偶尔出现）：openclaw 创建一个 `status=done` 的载体 task，再写 fact，保持以 task 为中心的链路。
- **不做 draft fact 批量处理界面**。

### 1.4 数据冗余处理

- **事实原文只存在 `facts.raw_markdown`** 一处。
- `tasks` 表**不加 `source_raw_markdown`** 字段。
- `tasks` 表**新增 `source_type`** 枚举标签字段（仅分类标签，无内容）。

---

## 2. 数据模型变更

### 2.1 `tasks` 表新增字段

| 字段 | 类型 | 说明 |
|---|---|---|
| `source_type` | string(32) nullable | 任务来源标签。枚举：`forwarded_message` / `screenshot` / `meeting_note` / `user_chat` / `manual_input`。默认 nullable。仅作分类标签，**不存原文内容**。 |

迁移策略：`ALTER TABLE tasks ADD COLUMN source_type VARCHAR(32) NULL`。旧任务该字段为 NULL，不影响任何旧 API。

### 2.2 `customer_materials` 表

无字段变更。`summary_markdown` / `insights_markdown` 字段保留但新流程不写入。审核页若读到为空，正常显示空。

### 2.3 其他表

无变更。

---

## 3. 后端 API 变更

### 3.1 `POST /api/tasks` / `PATCH /api/tasks/{id}`

- 接收新增字段 `source_type`（可选）。
- Schema 加入枚举校验（也可只做软校验）：建议允许任意字符串以避免 422 阻塞，但在文档里明确推荐枚举值。
- 不做"必须配套写 fact"的强校验（避免脆弱）。

### 3.2 `POST /api/tasks/{id}/complete`

- **不变**。完成时不派生 fact。

### 3.3 `POST /api/facts`

- **不变**。openclaw 主动写入。
- 文档强调：转发/截图/会议纪要场景 `raw_markdown` 必须为原始内容、不允许 LLM 加工。

### 3.4 `GET /api/facts`

- **不变**。需支持按 `from`/`to`/`customer_id`/`project_id`/`status` 过滤（已在 main.py 实现）。

### 3.5 `GET /api/customer-materials`

- 增加 / 确认支持按 `review_batch_id` 过滤（已在 main.py 实现）。

### 3.6 序列化

- `TaskRead` / `TaskDetail` 输出新增 `source_type` 字段。
- 其余无变化。

---

## 4. cron 改造

### 4.1 原 cron payload 处理

- 现有 `03ce7136-0071-4593-a77f-352f9362e69a`（"临时测试：每周客户材料生成"）：保留 `enabled=false`，作为历史。
- 现有正式周报 cron `aa277837-981a-41f2-b7cb-adf812d85873`（"周六17:00 客户跟进周总结"）：保留**不动**，它是基于 done 任务的人类可读周总结，与新链路并行存在，互不干扰。
- **新建一条 cron**：每周日 20:00 北京时间触发，调用新脚本生成 customer materials。

### 4.2 新 cron 配置建议

```yaml
schedule: "0 20 * * 0"
tz: Asia/Shanghai
type: shell           # 不是 agentTurn
command: python3 /home/velen/.openclaw/workspace/scripts/customer_materials_weekly.py
timeoutSeconds: 60    # 脚本应在 5~10 秒内完成；60 秒留充足 buffer
notify_on_finish: true
```

执行完毕后，由 OpenClaw 主代理通过现有飞书通知机制把脚本输出（JSON）转换为人类可读消息发给南哥。

### 4.3 脚本骨架

**位置**：`/home/velen/.openclaw/workspace/scripts/customer_materials_weekly.py`

**职责**：

1. 计算本周时间窗口：上周一 00:00:00 ~ 本周一 00:00:00（北京时间）。
2. 通过 HTTP 调 TaskCenter 本地 API，**不直连 SQLite**，保证未来 TaskCenter 部署位置变化时脚本不破。
3. 拉 facts、tasks，组织数据，调用 API 写 batch + materials + 关联。
4. 输出 JSON 报告到 stdout，供主代理转人类可读消息。

**伪代码**：

```python
import os, sys, json
from datetime import datetime, timedelta, timezone
from urllib.request import Request, urlopen

BASE = os.environ.get("TASK_CENTER_API", "http://127.0.0.1:8000")
TZ_BJ = timezone(timedelta(hours=8))

def api(method, path, body=None):
    data = json.dumps(body).encode() if body is not None else None
    req = Request(f"{BASE}{path}", data=data, method=method,
                  headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=15) as r:
        return json.loads(r.read())

def week_window(now_bj):
    # 上周一 00:00 ~ 本周一 00:00（北京时间）
    today = now_bj.replace(hour=0, minute=0, second=0, microsecond=0)
    end = today - timedelta(days=today.weekday())   # 本周一 00:00
    start = end - timedelta(days=7)                 # 上周一 00:00
    return start, end

def main():
    now = datetime.now(TZ_BJ)
    start, end = week_window(now)

    # 1. 拉本周 confirmed facts
    facts = api("GET", f"/api/facts?status=confirmed"
                       f"&from={start.isoformat()}&to={end.isoformat()}&limit=500")

    # 2. 按 customer_id + project_id 分组
    groups = {}
    for f in facts:
        key = (f.get("customer_id"), f.get("project_id"))
        groups.setdefault(key, []).append(f)

    if not groups:
        print(json.dumps({"status": "ok", "message": "no_facts_this_week",
                          "period": [start.isoformat(), end.isoformat()],
                          "warnings": collect_warnings(start, end)}))
        return

    # 3. 拉客户/项目元数据用于 title
    customers = {c["id"]: c for c in api("GET", "/api/customers")}
    projects = {p["id"]: p for p in api("GET", "/api/projects-v2")}

    # 4. 创建 review_batch
    batch = api("POST", "/api/review-batches", {
        "batch_type": "weekly_customer_summary",
        "title": f"{start.date()} ~ {end.date()} 客户周期材料",
        "period_start": start.isoformat(),
        "period_end": end.isoformat(),
        "status": "pending",
        "material_count": len(groups),
        "created_by": "cron",
    })

    # 5. 为每组创建 material 并关联 facts
    materials_out = []
    for (cid, pid), group_facts in groups.items():
        cust = customers.get(cid, {})
        proj = projects.get(pid, {}) if pid else None
        title = f"{cust.get('name', '未知客户')}｜{proj['name'] if proj else '客户级'}"

        # 按 fact_date 排序，原文拼接
        group_facts.sort(key=lambda f: f.get("fact_date", ""))
        raw_facts_md = "\n\n---\n\n".join(
            f"## {f.get('title','(无标题)')}（{f.get('fact_date','')[:10]}）\n\n{f.get('raw_markdown','')}"
            for f in group_facts
        )

        material = api("POST", "/api/customer-materials", {
            "customer_id": cid,
            "project_v2_id": pid,
            "review_batch_id": batch["id"],
            "title": title,
            "material_type": "period_summary",
            "period_start": start.isoformat(),
            "period_end": end.isoformat(),
            "raw_facts_markdown": raw_facts_md,
            "summary_markdown": None,
            "insights_markdown": None,
            "status": "pending",
            "generation_meta": {
                "fact_count": len(group_facts),
                "generated_by": "customer_materials_weekly.py",
                "generated_at": now.isoformat(),
            },
        })

        for idx, f in enumerate(group_facts):
            api("POST", f"/api/customer-materials/{material['id']}/facts", {
                "fact_id": f["id"],
                "sort_order": idx,
            })

        materials_out.append({
            "id": material["id"],
            "customer": cust.get("name"),
            "project": proj["name"] if proj else None,
            "fact_count": len(group_facts),
        })

    # 6. 一致性检查：本周 source_type 为转发/截图类但无 fact 的 task
    warnings = collect_warnings(start, end)

    print(json.dumps({
        "status": "ok",
        "batch_id": batch["id"],
        "period": [start.isoformat(), end.isoformat()],
        "materials": materials_out,
        "warnings": warnings,
    }, ensure_ascii=False))

def collect_warnings(start, end):
    """扫本周 source_type 应该有 fact 但无 fact 的 task"""
    suspicious_types = {"forwarded_message", "screenshot", "meeting_note"}
    tasks = api("GET", f"/api/tasks?from={start.isoformat()}&to={end.isoformat()}&limit=500")
    warnings = []
    for t in tasks:
        if t.get("source_type") in suspicious_types:
            t_facts = api("GET", f"/api/facts?task_id={t['id']}&limit=5")
            if not t_facts:
                warnings.append({
                    "task_id": t["id"],
                    "title": t["title"],
                    "source_type": t["source_type"],
                    "reason": "missing_fact",
                })
    return warnings

if __name__ == "__main__":
    main()
```

> 子代理实现时可微调 API 路径、查询参数、字段名以匹配当前 main.py 实际签名。`/api/tasks` 若未支持 `from`/`to` 时间范围参数，可改用列出全部 + 在脚本中按 `created_at` 过滤；或在后端补上参数。

### 4.4 主代理消费脚本输出

主代理收到 cron 完成事件后，读 stdout 的 JSON，转人类可读消息：

```
南哥，本周客户材料已生成，待审核：
- batch #{batch_id}（{period_start} ~ {period_end}）
- 共 N 份 material：
  - #{id} {customer}｜{project}（{fact_count} 条事实）
  - ...
- 审核完成请回复："审核完成 #{id} #{id} ..."，我会按列表上传到 NotebookLM。

⚠️ 本周 K 条任务疑似漏写 fact：
  - task #{id} {title}（source_type={source_type}）
  - ...
（如确实不需要 fact 可忽略；如需补，请把原始内容再发给我一次）
```

如果脚本输出 `status=ok, message=no_facts_this_week`，主代理只发"本周无可生成 facts，已跳过"+ warning 列表。

---

## 5. SKILL 文档更新（`task-center-customer-knowledge`）

### 5.1 写 fact 的硬约定

修订 SKILL.md 中"事实写入规则"一节，明确：

```text
强制规则：

1. 用户转发飞书消息 / 转发会话记录：
   - 必须 POST /api/tasks，source_type='forwarded_message'
   - 必须 POST /api/facts，task_id=新建task.id, source_type='forwarded_message',
     raw_markdown=原始多人对话文本（保留发言人、时间、原句，不删减、不总结）,
     status='confirmed'

2. 用户发截图：
   - 必须 POST /api/tasks，source_type='screenshot'
   - 必须 POST /api/facts，task_id=新建task.id, source_type='screenshot',
     raw_markdown=截图转写后的多人对话原文 + 图片元素 [此处为xx图片] 描述,
     status='confirmed'

3. 用户给会议纪要：
   - 必须 POST /api/tasks，source_type='meeting_note'
   - 必须 POST /api/facts，task_id=新建task.id, source_type='meeting_note',
     raw_markdown=纪要原文,
     status='confirmed'

4. 普通"提醒我做 X" 场景：
   - 只 POST /api/tasks（source_type='user_chat' 或不填）
   - 不写 fact
   - 任务完成后如果有有价值的结果，由用户主动转发给主代理后再走转发场景

5. 偶尔的纯事实（用户转发但明确说不需要跟进）：
   - POST /api/tasks，status='done', source_type='forwarded_message'/'screenshot' 等
   - POST /api/facts，同上规则
   - 即"载体 task + fact" 配对，保持 task 为中心

禁止：
- LLM 加工 raw_markdown 内容；只能直接搬运用户给的原始材料。
- 把 fact 内容拼到 task.title / task.description 后省略写 fact。
- 在 task complete 时主动调用 POST /api/facts 派生（后端也不会派生）。
```

### 5.2 上传链路约定

修订 SKILL.md 中"周期材料拼接规则"和"审核后上传"两节，明确：

```text
- 上传 markdown 仅包含：
  # {customer.name}｜{project.name 或 客户级}｜{period_start} ~ {period_end}

  {raw_facts_markdown}

  不要拼"简要纪要 / 洞察 / 风险 / 下一步建议"段落。
  summary_markdown / insights_markdown 字段在数据库中长期为空，不参与上传。

- 用户回复"审核完成 #A #B #C"或"审核完成 batch #N"时：
  - 按 id 读 material；
  - 过滤 status='approved'；非 approved 跳过并报告跳过原因；
  - 调 nblm Skill 按客户名匹配 NotebookLM 目标上传；
  - 上传成功后 POST /api/customer-materials/{id}/mark-uploaded；
  - 整批完成后回报每份 material 上传成败。
```

### 5.3 周期 cron 在 SKILL 中的角色

修订"周期材料拼接规则"一节顶部，明确：

```text
本 SKILL 不再描述 LLM 生成材料的方式。周期材料生成由 customer_materials_weekly.py
脚本确定性完成，主代理只在以下两个时点参与：
1. 转发/截图场景写 fact（事前）。
2. 用户回复"审核完成 #..."后上传到 NotebookLM（事后）。
```

---

## 6. 移动端审核页更新（mobile_frontend）

### 6.1 必须改的

- material 编辑 sheet 中：
  - 保留并允许编辑 `raw_facts_markdown`（修错别字、不准确描述）。
  - **隐藏或删除** `summary_markdown` / `insights_markdown` 编辑入口。
- material 列表页支持按 `review_batch_id` 分组展示（已部分实现，确认可见）。
- 审核流程按钮：保留"通过 / 跳过 / 标记已上传 / 归档"。

### 6.2 不做的

- 不做 draft fact 批量处理界面。
- 不加"生成纪要"按钮。
- 不加"重新生成"按钮。

### 6.3 兼容旧数据

- 已存在但 `summary_markdown` / `insights_markdown` 非空的旧 material：保持显示（只读），允许通过 PATCH 清空。
- 移动端可在 sheet 顶部加一行小字：`本批材料只展示原始事实，简要纪要 / 洞察由 NotebookLM 生成`。

---

## 7. 实施任务拆分

建议三个并行子代理（model: `glm/glm-5.1`, think: high）：

### 7.1 子代理 R1：后端 + 脚本

范围：

- 修改 `task_center/backend/models.py`：`Task.source_type` 字段。
- 修改 `task_center/backend/schemas.py`：`TaskCreate`、`TaskUpdate`、`TaskRead`、`TaskDetail` 加 `source_type`。
- 修改 `task_center/backend/main.py`：
  - `ensure_schema_compatibility()` 中 ALTER 加列。
  - 序列化函数加 `source_type`。
  - 确认 `GET /api/tasks` 支持时间范围参数（如不支持则补 `from`/`to`）。
- 新建 `/home/velen/.openclaw/workspace/scripts/customer_materials_weekly.py`：按第 4.3 节伪代码实现。
- 跑最小验证：
  - `python -m py_compile main.py models.py schemas.py`
  - 启动后端，curl 创建一个带 `source_type='forwarded_message'` 的 task。
  - 手动跑脚本一次（构造 1~2 条 confirmed fact）观察输出 JSON 和数据库写入。

### 7.2 子代理 R2：SKILL + 文档

范围：

- 修订 `skills/task-center-customer-knowledge/SKILL.md`：按第 5 节更新硬约定、上传链路约定、周期 cron 在 SKILL 中的角色。
- 修订 `task_center/TASK_CENTER_API_FOR_AGENTS.md`：
  - 加入 `Task.source_type` 字段说明。
  - 加入"转发/截图/会议纪要场景必须配套写 fact"的契约。
  - 删除或标注废弃 `summary_markdown` / `insights_markdown` 在新流程中的位置。
- 不动 `feishu-task` SKILL，不动 `nblm` SKILL。

### 7.3 子代理 R3：移动端 + cron 配置

范围：

- 修改移动端 material 编辑 sheet：隐藏 / 移除 summary/insights 编辑入口。
- 修改 material 列表页文案，加"只展示原始事实"提示。
- 修改 OpenClaw cron 配置：
  - 新建 `weekly_customer_materials_v2` cron，时间 `0 20 * * 0` Asia/Shanghai，type=shell，command=`python3 .../customer_materials_weekly.py`。
  - 旧 `03ce7136` 保持 `enabled=false`。
  - 旧 `aa277837`（周六 17:00 客户跟进周总结）**不动**。
- npm run build 通过；移动端启动后人工点几下确认审核页可用。

### 7.4 主代理（OpenClaw main）

- 等三个子代理收口后，统一验收（执行第 8 节验收清单）。
- git commit。
- 通知南哥下周日 20:00 自动触发，可端到端验证。

---

## 8. 验收清单

### 8.1 后端

- [ ] `tasks` 表有 `source_type` 字段；旧任务该字段为 NULL。
- [ ] `POST /api/tasks` 接受 `source_type='forwarded_message'`，返回值包含该字段。
- [ ] `POST /api/tasks/{id}/complete` 不再产生新 fact（前后查 facts 表行数确认）。
- [ ] `python -m py_compile` 通过；服务可启动；旧 `/api/tasks` / `/api/customer-materials` / `/api/facts` 均不破坏。

### 8.2 脚本

- [ ] 手动构造：1 个客户、1 个项目、3 条本周 confirmed fact。
- [ ] 运行 `customer_materials_weekly.py`，观察：
  - stdout JSON 含 batch_id、materials 列表、warnings 列表。
  - 数据库出现 1 个新 review_batch、1 份 material（raw_facts_markdown 非空，summary/insights 为空）、3 条 customer_material_facts。
- [ ] 构造 1 个 source_type='forwarded_message' 但无 fact 的 task，再跑脚本，warnings 列表应包含该 task。
- [ ] 没有 fact 时跑脚本：输出 `status=ok, message=no_facts_this_week`，不创建 batch。

### 8.3 SKILL/文档

- [ ] SKILL.md 明确转发/截图/会议纪要场景两步走规则。
- [ ] SKILL.md 明确不再生成 summary/insights。
- [ ] `TASK_CENTER_API_FOR_AGENTS.md` 包含 source_type 字段说明。

### 8.4 移动端

- [ ] material 编辑 sheet 不再显示 summary/insights 编辑入口。
- [ ] 旧 material 仍能正常显示。
- [ ] `npm run build` 通过。

### 8.5 cron

- [ ] 新 cron 配置存在，schedule `0 20 * * 0` Asia/Shanghai。
- [ ] 旧 `03ce7136` 仍 `enabled=false`。
- [ ] 旧 `aa277837` 配置未变。

### 8.6 端到端（下周日自动验证）

- [ ] 周日 20:00 cron 自动触发，5~30 秒内完成。
- [ ] 飞书收到南哥通知，含 batch_id 和 material id 列表。
- [ ] 南哥在移动端审核 1 份 material（修一处错别字 + PATCH approved）。
- [ ] 南哥飞书回复 "审核完成 #N"。
- [ ] 主代理拼 markdown、调 nblm 上传、`POST /mark-uploaded` 成功。
- [ ] material status 在审核页显示为 `uploaded`。

---

## 9. 对执行子代理的硬约束

- 不改桌面前端。
- 不改 `feishu-task` SKILL。
- 不改第三方 `nblm` SKILL。
- 不删除任何旧字段（包括 `customer_materials.summary_markdown` / `insights_markdown` / `candidate_markdown` / `review_note` / `task_id`）。
- 不在后端任何 API 中添加 LLM 调用。
- 不在 `POST /api/tasks/{id}/complete` 中添加 fact 派生副作用。
- 不在 `POST /api/tasks` 中对 `source_type` 做硬枚举校验阻塞（避免 422 脆弱），可在 schema 层做软校验或注释推荐枚举。
- `customer_materials_weekly.py` 必须**只通过 HTTP API** 操作 TaskCenter，禁止直连 SQLite。
- 如果文档和实现冲突，以 `task_center/backend/main.py`、`schemas.py`、`models.py` 为准；若发现现状已和本计划描述不符（例如 main.py 的 API 签名与伪代码不一致），以代码现状为准并在 PR/commit 信息中说明。
- 修改完成后必须运行能跑的最小验证；不能跑要说明原因。
- 提交 git commit 信息使用清晰的中文描述本次修订要点。

---

## 10. 风险与处理

### 10.1 SKILL 硬约定不被遵守

风险：openclaw 在转发场景下漏写 fact，或把 fact 内容 LLM 加工。

处理：
- 脚本一致性检查会在每周 warning 中暴露漏写。
- 加工内容这一条无法自动检测，靠 SKILL 文档 + 不定期人工抽查。
- 长期可考虑在 SKILL 中加 self-check 步骤，或在主代理处理转发场景时让其在写 task/fact 后输出"我做了：1. POST tasks #X, source_type=Y; 2. POST facts #Z, raw_markdown 长度 N"自我审计。

### 10.2 旧 material 数据残留

风险：测试期残留的 material（如 5/3 20:41 的"测试客户"批次、5/4 09:11 的临时验证 batch）混入未来周期。

处理：
- 实施前由南哥手动在审核页归档（`archived_at` 非空）这些测试 material 和对应 batch。
- 脚本不要重新读已归档的旧 fact。

### 10.3 客户/项目元数据缺失

风险：fact 上有 customer_id 但 customers 表里那条已被改名/删除。

处理：
- 脚本对 `customers.get(cid, {})` 做 fallback：取不到名字就用 "未知客户(id=X)"。
- 不阻塞流程，只在 warning 中提示。

### 10.4 cron 脚本调用本地 API 失败

风险：周日 20:00 时 TaskCenter 服务挂了。

处理：
- 脚本捕获 `urllib.error.URLError`，向 stderr 打印明确错误，退出码非零。
- OpenClaw cron 失败通知会送达南哥。
- 不试图自动重启服务。

### 10.5 source_type 标签未来扩展

风险：以后可能加 `email_forward` / `voice_note` 等新枚举值。

处理：
- 字段类型 string(32) 而非数据库 ENUM，扩展无需迁移。
- 一致性检查的 `suspicious_types` 集合在脚本中维护，加新值时改脚本。

---

## 11. 推荐执行顺序

1. R1 后端 schema + 脚本 → 跑最小验证。
2. R2 SKILL + 文档（与 R1 并行可，但 SKILL 中字段名以 R1 落定为准）。
3. R3 移动端 + cron 配置（R1 完成后启动，确保字段已上线）。
4. 主代理统一验收 + git commit。
5. 南哥手动跑一次脚本（不通过 cron，直接命令行）端到端确认。
6. 周日 20:00 等自动触发，做 8.6 端到端验证。

---

（本文件由 Cascade 起草，2026-05-04，根据南哥与 Cascade 当日讨论结果写成。原 2026-05-03 两份 plan 中被本次修订替换的条目以本文件为准。）
