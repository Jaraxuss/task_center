# Cascade Chat Conversation

  Note: _This is purely the output of the chat conversation and does not contain any raw data, codebase snippets, etc. used to generate the output._

### User Input

检索一下整个项目，看看是否能把 task 这个对象（表）的几个 *_at 字段含义找出来

*Listed directory [task_center](file:///home/velen/.openclaw/workspace/task_center) *

*Found code context*

*Viewed [models.py](file:///home/velen/.openclaw/workspace/task_center/backend/models.py) *

*Grep searched codebase*

*Found code context*

*Found code context*

*Grep searched codebase*

*Grep searched codebase*

*Viewed [tasks.py](file:///home/velen/.openclaw/workspace/task_center/backend/routers/tasks.py) *

### Planner Response

根据已检索的代码，[Task](file:///home/velen/.openclaw/workspace/task_center/backend/models.py:244:0-270:107) 模型中所有 `*_at` 时间字段的含义如下（来源：`@/home/velen/.openclaw/workspace/task_center/backend/models.py:245-271` 及路由/服务层使用逻辑）：

| 字段 | 类型 | 含义 / 业务逻辑 |
|------|------|----------------|
| **`created_at`** | `datetime`, non-null | 任务创建时间。默认值为 `now_utc()`，新建记录时自动写入。 |
| **`updated_at`** | `datetime`, non-null | 任务最后更新时间。默认值为 `now_utc()`，且配置了 `onupdate=now_utc`，每次修改自动刷新。 |
| **`due_at`** | `datetime`, nullable | 任务截止时间/计划执行时间。用于今日筛选、排序，以及重复任务的下一次触发。 |
| **`completed_at`** | `datetime`, nullable | 任务实际完成时间。在 `POST /api/tasks/{id}/complete` 时被设置为当前时间（或传入的自定义时间）；若任务状态被改回非 `done`（如重新激活），该字段会被清空。 |
| **`canceled_at`** | `datetime`, nullable | 任务取消时间。在 `POST /api/tasks/{id}/cancel` 时被设置；若状态改回非 `canceled`，字段会被清空。 |
| **`deferred_to`** | `datetime`, nullable | 任务被推迟到的目标时间。在 `POST /api/tasks/{id}/defer` 或 PATCH 状态改为 `deferred` 时写入；同时 `due_at` 也会对齐到该值。状态恢复时清空。 |
| **`nightly_reviewed_at`** | `datetime`, nullable | 任务最近一次经过"晚间收口/夜间回顾"流程的时间。目前由前端/外部 cron 主动写入，配合 `nightly_bucket` 字段使用，标记该任务已被纳入晚间回顾处理。 |

**补充说明：**
- 有一个相关的非 `*_at` 但紧密配合的时间字段是 **`nightly_bucket`**（`str`, default="open"），用于标识任务在夜间回顾中的分类桶。
- 目前代码中**不存在 `started_at`** 字段，任务进入 `doing` 状态不会单独记录开始时间。
- 事件表 `task_events` 的 `created_at` 记录了各生命周期事件（创建、完成、取消、推迟等）的发生时间，可用于追溯历史。

*Viewed [models.py](file:///home/velen/.openclaw/workspace/task_center/backend/models.py) *

### User Input

客观评估这个设计

### Planner Response

# Task 表 `*_at` 字段设计评估

## 优点

- **生命周期可追溯**：`completed_at` / `canceled_at` / `deferred_to` 各自对应 `done` / `canceled` / `deferred` 三个终态/暂停态，配合 `task_events` 表实现"快照 + 事件流"双轨记录，适合后续做审计、统计与回看。
- **时区统一**：所有 datetime 通过自定义 [UTCDateTimeText](file:///home/velen/.openclaw/workspace/task_center/backend/models.py:15:0-27:84) 类型统一以 UTC 存入 TEXT，读取时再转换，避免 SQLite 没有原生 timezone 的常见坑。
- **`updated_at` 自动维护**：用 SQLAlchemy 的 `onupdate=now_utc`，不依赖应用层手动更新，几乎不会漏。
- **状态切换有清理逻辑**：`@/home/velen/.openclaw/workspace/task_center/backend/routers/tasks.py:148-152` 在状态不再是 `done` / `canceled` 时主动把 `completed_at` / `canceled_at` 清空，避免脏数据残留。

## 问题与风险

### 1. 字段语义与状态字段存在冗余/可能不一致
- `status` 已表达 `done`/`canceled`/`deferred`，再用 `completed_at`/`canceled_at`/`deferred_to` 是否非空冗余表达同一信息。
- 一致性完全依赖应用层手动同步（见 [update_task](file:///home/velen/.openclaw/workspace/task_center/backend/routers/tasks.py:118:0-159:44) 中的清理逻辑）。一旦有人绕过该路径直接写 DB 或新增 endpoint 忘记清理，就会出现"`status=todo` 但 `completed_at` 非空"的脏状态。
- **更稳妥的做法**：用 DB CHECK 约束（如 `CHECK (status='done' OR completed_at IS NULL)`），或者干脆不存 `*_at`，需要时从 `task_events` 派生。

### 2. `deferred_to` 命名/语义模糊
- 字段名暗示"推迟到的目标时间"，但实际 [defer_task](file:///home/velen/.openclaw/workspace/task_center/backend/routers/tasks.py:218:0-231:44) 同时把 `due_at` 也对齐到 `deferred_to`（`@/home/velen/.openclaw/workspace/task_center/backend/routers/tasks.py:223-224`），这意味着该字段和 `due_at` 在 `deferred` 状态下完全冗余。
- 此外它丢失了"原始 due_at 是什么"的信息——一旦推迟，原计划时间无法从 task 表恢复（只能翻 `task_events`）。
- **建议**：要么记录 `original_due_at`（推迟前的截止时间），要么干脆删掉 `deferred_to`，仅靠 `status + due_at + 事件历史` 表达。

### 3. 缺失 `started_at`
- 模型有 `TaskStatus.DOING`，但没有任何字段记录"什么时候开始做的"。要做"任务平均执行时长""WIP 时长"等指标时只能扫描 `task_events`，效率较差。
- 如果业务上不关心可以接受；若关心则建议补 `started_at`。

### 4. `nightly_*` 字段耦合度过高
- `nightly_bucket` (String) + `nightly_reviewed_at` (datetime) 把一个尚未实现的"晚间收口"功能直接固化在核心 `tasks` 表上（健康检查接口里也明确说 *"22:00 晚间收口流程暂未实现自动执行"*）。
- 这是典型的"为未来功能预留 schema"，但功能没落地之前，这两列在每一行 task 上都占空间且语义不清。
- **建议**：要么放到独立的 `nightly_reviews` 表（多对一），要么等功能定型后再加，不要污染核心表。

### 5. 完成/取消的"原因/备注"字段不对称
- 完成有 `completion_note`，取消却没有 `cancel_reason`（取消原因目前只能进 `task_events.payload`，无法在列表查询里直接展示）。
- 如果产品上需要展示"取消原因"，每次都要 join 事件表，效率与一致性都不理想。

### 6. `due_at` 与重复任务的语义复用
- 重复任务在完成后会把 `due_at` 重写为 `next_run_at`（`@/home/velen/.openclaw/workspace/task_center/backend/routers/tasks.py:189-195`）。这意味着 `due_at` 同时承担"本次截止时间"和"下次触发时间"两种语义，历史的 `due_at` 不可恢复。
- 任何想看"上次这个重复任务原本应在什么时候完成"的需求都得回到 `task_events`。

### 7. 索引覆盖偏少
- 只有 `due_at` 和 `status` 上建了索引。常见查询场景如"近 7 天完成的任务"会扫 `completed_at` 全表。
- 如果数据规模会增长，建议给 `completed_at`、`canceled_at`、`updated_at` 中至少一个常用排序/过滤字段加索引。

### 8. SQLite TEXT 存时间的检索代价
- [UTCDateTimeText](file:///home/velen/.openclaw/workspace/task_center/backend/models.py:15:0-27:84) 用 ISO-8601 文本存储，依赖字符串比较得出时间序。只要格式严格一致是可行的，但失去了原生时间运算（如 `BETWEEN` 在某些 dialect 下会有微妙行为差异）。在迁移到 Postgres/MySQL 时需要把列类型转换处理好。

## 综合判断

整体属于**"够用、命名清晰、生命周期完整"**的设计，符合一个个人/小团队任务系统的复杂度要求。主要待改进点按优先级：

1. **高**：`nightly_*` 两列在功能落地前应剥离或标注为实验字段，避免长期占用核心表。
2. **中**：`completed_at`/`canceled_at`/`deferred_to` 与 `status` 的一致性应该由 DB 约束兜底，而不是仅靠应用层。
3. **中**：`deferred_to` 在当前实现下与 `due_at` 冗余，要么改为记录"原 due_at"，要么删除。
4. **低**：补 `started_at`、`cancel_reason`，给常用查询字段加索引；如果以后迁移到 PG，考虑改用原生 `TIMESTAMPTZ`。

*Viewed [Untitled-1](untitled:Untitled-1) *

### User Input

OK，先查一下对于「周期性任务」，目前是怎么实现的？有没有可改进的？

*Found code context*

### Planner Response

# 周期性任务（Recurrence）当前实现概览

## 数据模型

[TaskRecurrence](file:///home/velen/.openclaw/workspace/task_center/backend/models.py:318:0-338:74) 与 [Task](file:///home/velen/.openclaw/workspace/task_center/backend/models.py:244:0-270:107) 是 **1 : 1**（`task_id` UNIQUE），存储在独立表 `task_recurrences`：

```@/home/velen/.openclaw/workspace/task_center/backend/models.py:319-340
class TaskRecurrence(Base):
    __tablename__ = "task_recurrences"
    ...
    enabled, frequency, interval, timezone, time_of_day,
    days_of_week (JSON), day_of_month,
    start_at, end_at,
    next_run_at (indexed), last_run_at,
    reminder_offsets_minutes (JSON)
```

支持频率：`daily` / `weekly` / `monthly`（白名单，见 `@/home/velen/.openclaw/workspace/task_center/backend/recurrence.py:9`）。

## 核心规则计算

集中在 `@/home/velen/.openclaw/workspace/task_center/backend/recurrence.py:80-148` 的 `compute_next_recurrence`：
- **daily**：从 anchor 起按 `interval` 天累加，直到 ≥ boundary。
- **weekly**：以 anchor 所在周的周一为锚，遍历 `days_of_week`（ISO 1-7），按 `interval` 周跳跃。
- **monthly**：按 `day_of_month`（用 `monthrange` 处理月末），按 `interval` 月跳跃。
- 计算在 `recurrence.timezone`（默认 `Asia/Shanghai`）的本地时间下进行，最后转回 UTC 存储；这点处理得比较干净。

## 触发机制（关键点）

**目前没有任何后台调度器/cron。** "下一次"完全是被动驱动：

1. **写入/更新规则时**：`upsert_recurrence` 立刻算出 `next_run_at`，并把 `task.due_at` 同步设为 `next_run_at`（`@/home/velen/.openclaw/workspace/task_center/backend/services/tasks.py:243-272`）。
2. **完成任务时**：`POST /api/tasks/{id}/complete` 检测到带 recurrence 后（`@/home/velen/.openclaw/workspace/task_center/backend/routers/tasks.py:178-207`）：
   - 把 `last_run_at` = 本次完成时间；
   - 以 `max(completed_at, due_at) + 1s` 为边界算下一个 `next_run_at`；
   - 若有：**复用同一条 task**，状态回 `todo`、清空 completion/cancel/defer 字段、`due_at` = `next_run_at`，写一条 `RECURRENCE_ADVANCED` 事件；
   - 若没有：真正落到 `done`。

也就是说：**周期任务是"原地推进"模型——只有一行 task，每次完成把游标往后挪**。

## 客观评估

### 设计亮点

- **数据结构清晰**：规则单独一张表，1:1 不与 task 行混淆；`next_run_at` 上有索引，方便未来加调度。
- **规则计算与时区解耦得不错**：所有比较都先转到规则自身的时区做日历运算，再转回 UTC 存储，避免 DST/月末等坑（月末用 `min(day_of_month, max_day)` 处理）。
- **校验集中**：`validate_recurrence_payload` 在 schema 层（`model_validator`）和服务层都会调用，规则非法不会写库。
- **事件审计完整**：`RECURRENCE_UPDATED` / `RECURRENCE_ADVANCED` 都进 `task_events`。

### 主要问题

#### 1. **没有后台调度器，错过了就错过**
- 如果用户在 `next_run_at` 当天没主动点完成，下一周期不会自动产生，`due_at` 就永远停在过去那一天。
- `health.py` 的 nightly-review 占位说明也确认了这点："暂未实现自动执行"。
- **影响**：诸如"每周一例会"这种任务，连续两周不点完成 → 规则上的"周二、周三还该出现"全部丢失，只剩一行过期 task。

#### 2. **"原地推进"模型抹掉了历史**
- 同一行 task 反复被改写 `due_at` / `completed_at`，单看 task 表完全看不出"这个周期任务历史上完成过几次、哪几次跳过了"。
- 想做"完成率""连续打卡天数"必须扫 `task_events`，做聚合查询效率低。
- **替代方案**：把 [Task](file:///home/velen/.openclaw/workspace/task_center/backend/models.py:244:0-270:107) 拆成"模板（series）"和"实例（occurrence）"——模板存规则，每次到点生成一个独立 occurrence。这是 Todoist / Things / Google Tasks 的主流模型，统计自然，跳过/补打卡都好处理。

#### 3. **defer 与 recurrence 的语义冲突**
- 在 [defer_task](file:///home/velen/.openclaw/workspace/task_center/backend/routers/tasks.py:218:0-231:44) 里：`if task.recurrence and task.recurrence.enabled: task.recurrence.next_run_at = task.due_at`（`@/home/velen/.openclaw/workspace/task_center/backend/routers/tasks.py:227-228`）。
- 也就是说"把这次推迟到下周二"会**同时把规则的下一次触发时间改到下周二**。如果规则是"每周一"，这就破坏了原始节律——下次完成后才会重新对齐。
- 是否符合产品意图存疑，至少要在事件 payload 里区分"本次顺延"和"规则平移"。

#### 4. **错过补跑（catch-up）逻辑缺失**
- `compute_next_recurrence` 用 `boundary = max(after_dt, anchor)`，永远只返回"将来的下一次"。
- 如果用户离线 3 天后回来完成上周一的例会任务，系统不会意识到中间还漏了 2 次。
- 对"日报"类强补打卡场景不够友好。

#### 5. **`weekly` 分支可能死循环（边界情况）**
- `compute_next_recurrence` 在 weekly 分支里 `while True` 没有 end_boundary 兜底退出（只有命中候选时才检查 `end_boundary`）：

```@/home/velen/.openclaw/workspace/task_center/backend/recurrence.py:121-135
if frequency == "weekly":
    week_start = effective_anchor.date() - timedelta(days=effective_anchor.isoweekday() - 1)
    week_offset = 0
    while True:
        current_week_start = week_start + timedelta(weeks=week_offset)
        for weekday in normalized_days:
            current = datetime.combine(current_week_start + timedelta(days=weekday - 1), candidate_time, tzinfo=tz)
            if current < effective_anchor:
                continue
            if current < boundary:
                continue
            if end_boundary and current > end_boundary:
                return None
            return current.astimezone(UTC)
        week_offset += interval
```

  如果某种边角输入下 `normalized_days` 在 `validate` 后又被外部清空，理论上会无限累加（实践被前置校验拦了，但加一个 `week_offset` 上限或外层 `for _ in range(N)` 更稳）。monthly 分支同理。

#### 6. **频率支持过窄**
- 只有 daily / weekly / monthly。**没有**：
  - "每年生日" / yearly
  - "每月最后一个工作日" / "每月第二个周三"（BYSETPOS）
  - "工作日（Mon-Fri）" 这种常见预设（虽然可以靠 weekly + days_of_week=[1,2,3,4,5] 表达，但 UI 通常会做快捷项）
  - 排除日（exclude dates）/ 节假日
- 想未来扩展，建议引入 RFC 5545 的 RRULE（Python 有现成的 `dateutil.rrule`），把现有 5-6 个字段折叠成一个标准 RRULE 字符串，既是行业标准也直接获得上述能力。

#### 7. **`reminder_offsets_minutes` 似乎没生效**
- 从代码看，`upsert_recurrence` 只把它存进 recurrence 表，没看到任何在生成下一次 task 时按 offset 自动创建 [Reminder](file:///home/velen/.openclaw/workspace/task_center/backend/models.py:303:0-315:73) 行的逻辑。需要确认是占位字段还是漏调。

#### 8. **时区字段在 task 上没有，规则上有**
- 规则有 `timezone`，但 task 本身没有 `timezone`。一旦用户出差换了系统时区，规则按规则时区算（OK），但 task 的 `due_at` 显示和 reminder 的本地化都依赖前端，缺少一致的"任务级时区"做兜底。

### 推荐改进（按优先级）

| 优先级 | 改进 | 收益 |
|--------|------|------|
| 高 | 加一个轻量调度器（FastAPI `BackgroundTasks` 不够，建议 APScheduler 或简单的 cron + `/api/internal/recurrence/tick` 端点）扫 `next_run_at <= now AND enabled` 自动推进 | 解决"不点就不动"的核心缺陷 |
| 高 | 把 `defer` 时同步修改 `next_run_at` 的行为改成可选（payload 加 `shift_recurrence: bool = False`），默认只动本次 | 修复语义冲突 |
| 中 | 引入 series/occurrence 模型（或先以视图形式从 `task_events` 聚合"完成历史"） | 支持完成率、补打卡统计 |
| 中 | weekly/monthly 分支加最大循环次数兜底（如 ≤ 520 周 / ≤ 600 月） | 防御性编程 |
| 中 | 在生成 `next_run_at` 后，若 `reminder_offsets_minutes` 非空，自动写入对应 [Reminder](file:///home/velen/.openclaw/workspace/task_center/backend/models.py:303:0-315:73) 行 | 兑现已有字段的承诺 |
| 低 | 长期：迁移到 RRULE 表达，用 `dateutil.rrule` 计算 | 行业标准 + 复杂规则 |
| 低 | 给 `task_recurrences.next_run_at` 加 `(enabled, next_run_at)` 复合索引 | 给后续 scheduler 准备 |

## 一句话结论

**当前实现"作为单机被动驱动的简易周期"是合格的、规则计算也写得不糙；但缺了调度器与历史化两条腿，难以承载"晚间收口 + 自动补提醒"这类已经在 README / 健康检查里承诺的场景**。短期最值得做的是补一个最小调度器把 `next_run_at` 跑活，长期再考虑 series/occurrence 重构。

*Viewed [recurrence.py](file:///home/velen/.openclaw/workspace/task_center/backend/recurrence.py) *

*User accepted the command `cd ../skills`*

*User accepted the command `l`*

*User accepted the command `cd ../workspace/skills`*

*User accepted the command `l`*

*User accepted the command `pwd`*

### User Input

我是通过 openclaw （主要是 skill 和 cron）结合 TaskCenter 来做的，你把cron（/home/velen/.openclaw/cron/ 下） 和相关 skill（/home/velen/.openclaw/workspace/skills/ 下） 阅读，综合判断

*User accepted the command `ls -la /home/velen/.openclaw/cron/ /home/velen/.openclaw/workspace/skills/`*

*User accepted the command `ls /home/velen/.openclaw/workspace/skills/task-center-customer-knowledge/ /home/velen/.openclaw/workspace/skills/task-center-reminder-sync/`*

*User accepted the command `python3 -c "import json,sys; d=json.load(open('/home/velen/.openclaw/cron/jobs.json')); print('count:',len(d) if isinstance(d,list) else 'dict'); import pprint; pprint.pprint(d[:5] if isinstance(d,list) else list(d.items())[:5])"`*

*User accepted the command `python3 << 'EOF'
import json, collections
d = json.load(open('/home/velen/.openclaw/cron/jobs.json'))
print('top type:', type(d).__name__)
if isinstance(d, dict):
    print('keys:', list(d.keys()))
    jobs = d.get('jobs') or d.get('items') or []
else:
    jobs = d
print('total jobs:', len(jobs))
kinds = collections.Counter()
sched = collections.Counter()
task_refs = 0
recurring = 0
for j in jobs:
    pk = (j.get('payload') or {}).get('kind') or 'unknown'
    kinds[pk] += 1
    s = j.get('schedule') or {}
    sched[s.get('kind') or 'unknown'] += 1
    if s.get('kind') == 'cron':
        recurring += 1
    text = (j.get('payload') or {}).get('text','') + (j.get('payload') or {}).get('message','')
    if 'task_center' in text.lower() or 'task #' in text.lower() or '#15' in text or 'tasks/' in text:
        task_refs += 1
print('payload kinds:', kinds)
print('schedule kinds:', sched)
print('task_center mentions:', task_refs)
print('recurring (cron) jobs:', recurring)
print('\n--- All cron jobs ---')
for j in jobs:
    s = j.get('schedule') or {}
    if s.get('kind') == 'cron':
        print(f"[{s.get('expr')} {s.get('tz')}] {j.get('name')}  -> agent={j.get('agentId')} target={j.get('sessionTarget')}")
EOF`*

*Viewed [SKILL.md](file:///home/velen/.openclaw/workspace/skills/task-center-reminder-sync/SKILL.md) *

*Viewed [SKILL.md](file:///home/velen/.openclaw/workspace/skills/task-center-customer-knowledge/SKILL.md) *

*User accepted the command `python3 << 'EOF'
import json
d = json.load(open('/home/velen/.openclaw/cron/jobs.json'))
jobs = d['jobs']
# Look at one recurring task-center linked job and one 'at' (deferred) one in full
import pprint
for j in jobs:
    if 'task_center#63' in (j.get('description','')+j.get('name','')) or '#63' in j.get('name',''):
        pprint.pprint(j); print('---'); break
for j in jobs:
    if j.get('schedule',{}).get('kind')=='cron' and 'task_center#92' in (j.get('name','')+j.get('description','')):
        pprint.pprint(j); print('---'); break

# 晚间收口 job full
for j in jobs:
    if '晚间收口' in j.get('name',''):
        pprint.pprint(j); print('---'); break

# Check state
s = json.load(open('/home/velen/.openclaw/cron/jobs-state.json'))
print('state keys:', list(s.keys())[:3] if isinstance(s,dict) else 'list')
if isinstance(s, dict):
    # sample
    first = next(iter(s.items()))
    print('state sample:'); pprint.pprint(first)
EOF`*

### Planner Response

# OpenClaw（cron + skill）× TaskCenter 周期性任务实现综合评估

## 一、现状盘点

### 1.1 三层架构（已经在跑的事实）

| 层 | 位置 | 角色 |
|----|------|------|
| **数据账本** | TaskCenter 后端（SQLite） | `tasks` / `task_recurrences` / `reminders` / `facts` / `customers` / `projects` / `customer_materials` |
| **触发器** | OpenClaw cron（`@/home/velen/.openclaw/cron/jobs.json`） | 39 条 job：18 条 `cron`（按表达式重复）+ 21 条 `at`（一次性，多为延期产物） |
| **行为契约** | OpenClaw skills（`@/home/velen/.openclaw/workspace/skills/`） | `task-center-reminder-sync` / `task-center-customer-knowledge` 等定义"何时该写 TC、何时该写 cron、何时该写 fact" |

### 1.2 周期触发实际怎么发生

抽样 jobs.json 里几条对照：

- **`提醒：每周一10点给江阴男生女生的费总同步RPA初级课程学习进度（task_center#63）`**
  - `schedule`: `{kind: cron, expr: "0 10 * * 1", tz: "Asia/Shanghai"}`
  - `payload.kind`: `systemEvent`（静态文本，不调 API）

- **`提醒：每月15号10:30发RPA数据复盘给华孚精密卢总（task_center#92）`**
  - `schedule`: `{kind: cron, expr: "30 10 15 * *"}` — **cron 表达式写死在 OpenClaw 侧**
  - payload 文本里硬编码 "task_center 任务 #92"

- **`任务晚间收口（每日22:00，智能版）`**
  - `schedule`: `{kind: cron, expr: "0 22 * * *"}`
  - `payload.kind`: `agentTurn`，prompt **直接内嵌**在 cron 配置里（与 `/Untitled-1` 内容几乎一致）
  - 跑起来后由 agent 调 `GET /api/dashboard/today` 拉数据

- **`提醒：#154 雷允上药业私有云部署申请流程（延期）`**
  - `schedule`: `{kind: at, deleteAfterRun: True}` — 一次性
  - 由 `task-center-reminder-sync` 在用户说"推迟到…" 时双写产生

### 1.3 关键事实：**周期"实质上"靠 cron 表达式，不靠 [TaskRecurrence](file:///home/velen/.openclaw/workspace/task_center/backend/models.py:318:0-338:74)**

`@/home/velen/.openclaw/workspace/task_center/backend/models.py:319-340` 那张 `task_recurrences` 表与 [compute_next_recurrence](file:///home/velen/.openclaw/workspace/task_center/backend/recurrence.py:79:0-147:32) 一整套逻辑，**在你这条工作流里几乎没派上用场**——所有的"每周一 10:00"、"每月 15 号"都是 OpenClaw cron 的 `expr` 字符串。两套调度器并存，但只有一套真正在跑。

---

## 二、客观评价

### 2.1 优点

1. **职责分明**：TC 做账本、cron 做触发、skill 做规则。重启某一层不影响另外两层。
2. **触发器是独立进程**：cron daemon 跟 TC 后端解耦，TC 服务挂了，触发依然发生（虽然 agent 这一侧会无法回写）。
3. **晚间收口 22:00 是闭环最干净的一条**：cron 触发 → agent 调 `/api/dashboard/today` → 按 TC **当时的**真实状态生成清单 → 引导用户回话 → 用户回话后再回写 TC。整条链路上没有重复存储，时间也不会 drift。
4. **延期 at-job + TC `deferred_to` 双写**有明确 skill 规范（`task-center-reminder-sync` §三）。
5. **客户知识链路（`facts` + `customer_materials` + 周日 20:00 脚本）几乎是教科书级**：周日脚本只搬运不加工，留给 NotebookLM；触发与生成分两个心跳。这块跟 recurrence 关系不大，但说明你这套"cron + 脚本 + TC"模式能很好地承载周期工作。

### 2.2 主要问题（按危害排序）

#### 🔴 P0：**重复提醒触发时不重读 TC 状态 — "幽灵提醒"**

最严重的一条。看 `task_center#63` 那个 job 的 payload：

```json
"payload": {"kind": "systemEvent",
            "text": "提醒：现在是每周一上午 10:00（北京时间），..."}
```

`systemEvent` 是**静态文本**，触发时不会查 TC。也就是说：

- 如果 #63 已经被 **canceled / done / 改了客户**，cron 下周一仍然按原文喊你"给费总同步进度"。
- 如果 #63 已经被改名换人，提醒里的人名也不会跟着变。
- 重复型 cron job 与 TC task 之间的引用是**单向、断开的快照**。

> 同样的问题：#92、#93、#94、#104、#112 等所有形如"每月 X 号给客户发 Y"的 cron job 都有这个隐患。

#### 🔴 P0：**[TaskRecurrence](file:///home/velen/.openclaw/workspace/task_center/backend/models.py:318:0-338:74) 与 cron `expr` 双轨，事实上 TC 那一轨是死代码**

- TC 后端有完整的 `frequency/interval/days_of_week/day_of_month/next_run_at` 体系 + `RECURRENCE_ADVANCED` 事件，但实际产生周期触发的是 jobs.json 里手写的 cron 表达式。
- 这造成两条隐患：
  1. **改时间要改两边**，靠 LLM 遵守 skill 里的"双向同步"——一旦没检索到 skill 就破。
  2. **`/api/dashboard/today` 之类的 TC 视图无法预测下一次重复任务**——因为它只看得到 `task_recurrences`，看不到 jobs.json。

#### 🟠 P1：**晚间收口完成动作后，原 cron job 仍按 expr 重复**

举例：#92 "每月 15 号发数据复盘"——
- 你 5/15 完成了 #92，TC 把 task #92 状态置为 `done`、`completed_at=...`。
- 6/15 10:30 cron 仍然按 `30 10 15 * *` 触发，发出 systemEvent，引用一个**已完成的 task id**。
- 实际上你希望的语义是：6/15 应该自动生成一个**新的** task（或把 #92 重置回 todo + 改 due_at）。
- 目前没有任何代码做这个动作。skill 里也没规定 cron 触发时 agent 要"开新 task"或"reopen old task"。

#### 🟠 P1：**延期 at-job 没有显式生命周期挂钩**

- 用户说"推迟到周二"→ skill 双写：PATCH TC + 新建一个 `at` cron job (`deleteAfterRun: True`)。
- 但是：
  - 用户后续又说"再推一天"→ skill 必须先找到上一条 at-job 删掉，再建新的。靠 LLM 记得做。
  - 用户直接通过 mobile_frontend UI 改 `deferred_to`，cron 端**完全感知不到**——TC 改了，cron 仍然在原时间触发。
- 没有 reconciler，没有"task-id ↔ cron-job-id"反向索引（TC 表里没存 cron job_id）。

#### 🟠 P1：**Prompt 配置存了两份**

- 晚间收口的 prompt 同时存在：
  - cron job 的 `payload.message` 里（1000+ 字符内嵌）
  - 用户 IDE 里打开的 `/Untitled-1`（应该是它的源文件）
  - skill `task-center-reminder-sync` §九"晚间收口规则"里也有简化复述
- 三处描述应当保持一致，但没有任何机制保证。

#### 🟡 P2：**两套时区配置**

`task_recurrences.timezone` 字段 + cron job 的 `schedule.tz` 字段——出差/换时区时要改两处。

#### 🟡 P2：**失败可观测性差**

cron 跑出来的 isolated agent turn 输出落在 `runs/`，但**没回写到 TC `task_events`**。事后看不出"昨晚 22:00 那次收口是发了空清单还是发漏了 3 条"。

#### 🟡 P2：**`reminders` 表与 cron 重叠**

TC 已经有 `reminders` 表，schema 上看像是要承担提醒。但实际触发完全靠 cron，`reminders` 表只是被前端读了一下做展示。**等于多了一张几乎不参与决策的表**。

---

## 三、综合判断

> **当前实现是"能跑、且产品语义清晰"的最小可用形态。但'周期性'这件事在你的系统里事实上被推到 OpenClaw cron 表达式里，TC 自己的 recurrence 子系统接近闲置；同时所有重复型 cron job 的 payload 都是静态快照——这两点合起来构成最大的脆弱面。**

最坏的失败模式：用户在 TC 里完成/取消/重命名一个 task，但 OpenClaw cron 不知道，于是按原文继续每周喊。**事实上这个场景今天已经在你的库里了**（#63、#92、#93、#94、#104、#112 都是这类"无终止条件的 systemEvent 重复 cron"）。

---

## 四、改进建议（按 ROI 排序）

| 优先级 | 改进 | 一句话理由 |
|--------|------|-----------|
| 🥇 **P0** | **重复型 cron job 全部改 `agentTurn` 形态**，触发时先 `GET /api/tasks/{id}`：若 `done/canceled` → `NO_REPLY` 并自动 disable 该 cron；若 `deferred` → 跳过本次；否则按 TC 最新内容发 | 一锤子敲掉"幽灵提醒"，几乎不用动 TC 后端 |
| 🥇 **P0** | **TC 增加一张 `task_external_schedules` 表**（或在 `task_recurrences` 上加 `cron_job_id` 列），把 OpenClaw cron job id 反向挂在 task 上 | 让 TC 改时间 / 完成 / 取消 时有据可查地去同步/删除 cron |
| 🥈 **P1** | **选一处当 source of truth**：要么 TC [TaskRecurrence](file:///home/velen/.openclaw/workspace/task_center/backend/models.py:318:0-338:74) 当真相、cron 端起一个轻量"tick"（每分钟）从 TC 拉 `next_run_at <= now` 推送；要么彻底删 [TaskRecurrence](file:///home/velen/.openclaw/workspace/task_center/backend/models.py:318:0-338:74) 表，承认 cron expr 才是真相，TC 只读 | 消除双轨账本 |
| 🥈 **P1** | **加一个夜间 reconciler 脚本**（00:30 跑）：扫所有 jobs.json 里引用 `task_center#XX` 的 job，对照 TC 状态报告偏差（job 启用但 task done / job 时间与 task.due_at 不符 / task 有 recurrence 但无对应 cron） | 不动旧逻辑，先把不一致**可见化**，可以暴露真实严重程度后再决定彻底重构方向 |
| 🥈 **P1** | **每月 15 号型 cron 的语义统一**：触发时不仅发提醒，还要 `POST /api/tasks` 新建一份当月实例（series/occurrence 模型），完成后写回 fact——把"周期任务"和"每次的具体任务"区分开 | 解决"完成后下个周期不会自动重新激活" |
| 🥉 **P2** | **晚间收口 prompt 提取成 skill 单一来源**：cron job 的 payload 改成"run skill: nightly-close"，prompt 由 agent 在运行时从 `task-center-reminder-sync` 的对应 section 加载 | 消除 prompt 三份维护 |
| 🥉 **P2** | **agent 每次 turn 完成后写 1 条 `task_events`**（即便是 system 级触发） | 给所有自动触发加可观测性，事后能查"昨晚 22:00 那次到底发没发" |
| 🪙 P3 | 长期：把 TC 的 `reminders` 表激活，做一个 minimal worker 直接消费它，逐步把 reminder 类触发从 cron 收归 TC；cron 只留"agentTurn 级 cron 任务"（如周日 20:00 客户材料生成、03:10 备份检查、03:30 记忆落盘） | 让 TC 真正做完整的"任务+提醒"主账本 |

## 五、一句话总结

**架构方向是对的，但当前形态下 TC 的 recurrence 是"装饰品"、cron 是"实际驱动者"、skill 是"维持一致性的人肉胶水"——把胶水固化成 P0 那两条最有杠杆的代码改动（cron 触发前 re-fetch + TC 反向挂 cron_job_id），系统就从"靠 LLM 遵守纪律"升级成"机制上不会跑偏"。**

### User Input

整体你说得对，TC 的 recurrence 确实没用起来，我觉得如果能用起来，或许能够解决一些复杂场景（比如每个月第一周的周二提醒我xxx，现有 OpenClaw 的 cron 应该很难支持）。但需要解决两个问题：

1. 需要 TaskCenter 能够（通过飞书，并且可能需要结合 agent 的能力做一定处理后）发出通知。目前我和 OpenClaw 调研了一个方案是通过命令行调用 OpenClaw 来发送，具体描述在 @[docs/OPENCLAW_FEISHU_MESSAGE_DELIVERY.md] 下
2. 由于历史架构已经设计成基于 cron 来提醒，上面1的方案有多稳定还未知，所以求稳起见我不希望一下子全改。我希望先把1的方案作为「当我去 TaskCenter 里修改了 task」这个场景下、现有机制下 OpenClaw 并不知道（cron 也无从同步修改，除非我跟他再说一遍）的一个很好地补充，这样对目前的主要场景没有改动，把补充场景做测试，如果稳定后，再考虑全面迁移靠 TaskCenter 这边触发提醒

---

一个修正：
1. 「P1：晚间收口完成动作后，原 cron job 仍按 expr 重复」- 「实际上你希望的语义是：6/15 应该自动生成一个新的 task」，实际上我并不这么希望，我不希望每个周期都创建一个新的 task，只要有办法（不管这个办法有多慢多麻烦，因为是极低频需求）能查到之前历史周期的信息即可。你看看现有设计是否满足的需求？

---
其他的改进建议先放一放，我们先重点讨论这个方案怎么来设计，以及我提到的修正你看一下

*Viewed [OPENCLAW_FEISHU_MESSAGE_DELIVERY.md](file:///home/velen/.openclaw/workspace/task_center/docs/OPENCLAW_FEISHU_MESSAGE_DELIVERY.md) *

*Found code context*

### Planner Response

我先把 OpenClaw 通知文档读完了，也回头核对了一下你修正的"历史周期"那条。先给两块结论，再问几个关键问题以便定 plan。

# 一、修正确认：现有设计能查到历史周期信息 ✅

你说的不希望每周期建新 task，只要能"翻得到"即可——**现有 `task_events` 表完全满足**，且你已经在写：

- `@/home/velen/.openclaw/workspace/task_center/backend/routers/tasks.py:196-206` 每次重复任务完成 `RECURRENCE_ADVANCED` 事件 payload 已记录：`completed_at` / `note` / `previous_due_at` / `next_run_at`。
- `COMPLETED` 事件单独存了一份 `completed_at` + `note`。
- `task_events` 不会随 task 推进被覆盖，是 append-only。
- `task_detail_response` 已经默认把 events 倒序挂回 `TaskDetail`。

**也就是：随时 `GET /api/tasks/{id}` 翻 events 就能完整重建"这条重复任务过去 N 次什么时候完成、备注是什么、上次 due 在什么时候"。** 不需要 series/occurrence 重构。

唯一两个小缺口（**可选**，不影响主结论）：
1. **没有专门列 events 的 endpoint**：要分析一批重复任务历史时只能 1:1 GET。低频确实够用；要省事可以加一个 `GET /api/tasks/{id}/events?type=recurrence_advanced` 的薄壳。
2. **"漏跑"是隐式的**：如果某次到点没做也没补打卡，下一次 advance 时 `previous_due_at` ≠ 上一次 advance 的 `next_run_at`，比对能算出"跳过了几次"，但没有显式 `RECURRENCE_SKIPPED` 事件。

我撤回上一轮关于"6/15 应该自动生成新 task"的措辞。

---

# 二、CLI 通知作为"TC → OpenClaw 补盲点"的方案骨架

## 2.1 问题场景界定

OpenClaw 完全感知不到、必须靠 TC 通知它的盲点：

| 用户动作 | 端点 | 现在 agent 知道吗 |
|---------|------|------------------|
| mobile UI 改 due_at / status | `PATCH /api/tasks/{id}` | ❌ |
| mobile UI 点完成 | `POST /api/tasks/{id}/complete` | ❌ |
| mobile UI 点取消 | `POST /api/tasks/{id}/cancel` | ❌ |
| mobile UI 点延期 | `POST /api/tasks/{id}/defer` | ❌ |
| mobile UI 新建任务 | `POST /api/tasks` | ❌（但通常不与既有 cron 冲突，可不通知） |
| 聊天里让 agent 干 | 同上 4 个端点 | ✅（agent 自己干的，本来就知道） |

所以"补盲点"的精确触发条件是：**修改类 endpoint + 请求来源不是 agent**。`Task.source` 字段（`@/home/velen/.openclaw/workspace/task_center/backend/models.py:257`，默认 `"web"`）正好可以用来区分；移动端/前端的请求把 source 标成 `web` / `mobile`，agent 调 API 时带上 `source: "agent"`。

## 2.2 推荐做法（与你"求稳、先做补充"的诉求对齐）

**TC 后端在符合条件的修改后，异步（fire-and-forget）调用 `openclaw message send` 发一条飞书给南哥，提示"#XX 在 TC 改了 X→Y，记得同步 cron"。**

为什么 `message send` 而不是 `agent --deliver`：
- 内容确定（差异已计算好），不需要 LLM 加工
- 链路短，失败可见
- 文档里也明确推荐对确定性提醒走 `message send`
- agent 看到这条飞书后再决定要不要去动 cron 是**人工节奏**——这正是"补充"而不是"接管"的姿态

## 2.3 关键设计点（先列出来，后面在 plan 里展开）

1. **触发条件**：PATCH/complete/cancel/defer + `Task.source != "agent"`（也可改为 header `X-Source`）。
2. **通知内容**：包含 `#id` + 标题 + 变更摘要（`due_at 5/16 09:00 → 5/18 10:00`），≤200 字。
3. **异步**：用 FastAPI `BackgroundTasks`，不阻塞 API 响应；CLI 失败不影响 API 成功。
4. **审计**：成功/失败都写一条 `task_event`（新增 `NOTIFICATION_SENT` / `NOTIFICATION_FAILED`），方便事后排障。
5. **配置 + 开关**：`OPENCLAW_NOTIFICATION_ENABLED`、`OPENCLAW_FEISHU_TARGET`、`OPENCLAW_CLI_PATH` 走 `.env`；提供 `dry_run` 模式（只写 event 不真发），第一周观察用。
6. **去重 / 抖动**：第一版**不做**；如观察到噪音再加 30s 抖动窗口。
7. **测试覆盖**：单元测试 mock subprocess；本地 E2E 用一个 fake CLI 验证参数串。

## 2.4 与 cron 的关系

- 这一阶段**不触碰** OpenClaw cron jobs.json，**不动** [TaskRecurrence](file:///home/velen/.openclaw/workspace/task_center/backend/models.py:318:0-338:74) 表，**不动** skill 流程。
- 我之前提的 P0 改进项（"重复 cron job 改 agentTurn 形态 + 触发前 re-fetch"、"TC 反向挂 cron_job_id"）全部按你要求**暂缓**。
- 等"补盲点通知"在你这边稳定跑 1-2 周后，再评估是否做"TC 主动触发周期任务提醒"这一更大的迁移。

---

# 三、写 plan 前需要确认 3 个关键点

*Asked user a question*

### Planner Response

我先把两种方案的本质分清，然后问一句具体的——这个问题选错了，plan 就走偏了。

## 这两个方案是**不同层级的事**

### 方案 1：TC 内置 ticker + CLI 直发（"TC 自己当触发器"）

```
mobile UI 改 task → TC 写库 → 不通知任何人
                                      ↓
                            TC 内 worker 进程每分钟扫一次
                            → due_at 到点 → subprocess(openclaw message send) → 飞书
```

- **本质**：让 TC 真正承担"触发"职责。OpenClaw cron 不再参与"task_center #XX"这类提醒。
- **优点**：
  - 单一事实源，**没有 TC ↔ cron 的同步问题**——根本就没两本账了
  - 复杂周期（"每月第一周的周二"）由 [TaskRecurrence](file:///home/velen/.openclaw/workspace/task_center/backend/models.py:318:0-338:74) 自己算，不被 cron 表达式约束
  - 用户 mobile 改完即改完，不需要通知任何人
- **缺点**：
  - 要在 TC 进程里跑常驻 worker（APScheduler 或裸 asyncio loop，~80 行代码）
  - 与现有 OpenClaw cron 体系**边界要画清**：哪些提醒走 TC、哪些继续走 cron？最简单的切法是"task 本身的到点提醒走 TC，跨任务/纯运维型 cron（晚间收口、周日 20:00 客户材料、备份监控）继续 OpenClaw cron"
  - 这其实**就是把 [TaskRecurrence](file:///home/velen/.openclaw/workspace/task_center/backend/models.py:318:0-338:74) 真用起来**——也是你最初提到"想用复杂周期"的那条路径

### 方案 2：TC 改完后 → 立刻通过 CLI 通知 OpenClaw 改 cron（"TC 写完顺手通知 cron 同步"）

```
mobile UI 改 task → TC 写库 → subprocess(openclaw 某命令) → OpenClaw cron 端被改
                                                                      ↓
                                                            到点了 OpenClaw cron 触发
```

- **本质**：保留 OpenClaw cron 当触发器，TC 只是**多发一次"嘿你也跟着改"**。
- 取决于 OpenClaw 那边给的能力，又分两个 sub-variant：

  - **2a**：调 `openclaw agent --deliver`，把变更告诉 main agent，让 main agent 用现有 `task-center-reminder-sync` skill 去改 cron
    - 0 改造成本，但依赖 LLM 准确性，每次改 task 都让 agent 跑一轮 turn，慢且贵
  - **2b**：调 `openclaw cron upsert/remove`（**目前文档里没有这个子命令**，需要 OpenClaw 那边扩 CLI）
    - 确定性最高，但需要扩 OpenClaw；同时仍然是双账本（TC 和 jobs.json 都存了一份提醒时间）

## 我的判断

考虑到你三个约束：
1. **求稳，先做补充**
2. **未来想支持复杂周期**（"每月第一周的周二"——这正好是 OpenClaw cron 的 5 字段表达式很难写的，需要 BYSETPOS）
3. **现有 cron 提醒先不动**

**我推荐方案 1，但范围限定在 mobile UI 改的那部分 task**：

- mobile 改完写库后，TC 的 worker 接管这条 task 的提醒；同时**自动 disable 这条 task 在 OpenClaw cron 里的对应 job**（如果有的话），避免双发。
- 现有"重复 cron job"（#63、#92 等）只要用户没在 mobile 上改过，就照常走 OpenClaw cron。
- 这等于"用户修改过的部分由 TC 接管，没改过的部分照旧"——风险范围被你自己的操作框住了。

为什么不推荐方案 2：
- **2a** 每改一次任务跑一轮 LLM turn，**反向放大了你最不想要的"靠 LLM 维持一致性"问题**（这正是我上一轮指出的最大脆弱面）；
- **2b** 需要 OpenClaw 扩 CLI 又仍然是双账本，付出和收益不匹配；
- 两者都没解决"复杂周期"。

不过这是我的判断，最终选谁要看你两个事：

*Asked user a question*

### User Input

在这个文档 @[docs/OPENCLAW_FEISHU_MESSAGE_DELIVERY.md]  里我把四种让 openclaw 通过飞书发送消息的方式进行了完善，你阅读一下，然后看看结论上有没有什么变化。

*Viewed [OPENCLAW_FEISHU_MESSAGE_DELIVERY.md](file:///home/velen/.openclaw/workspace/task_center/docs/OPENCLAW_FEISHU_MESSAGE_DELIVERY.md) *

### Planner Response

读完了。文档新增的 **2.3 节（`openclaw cron add` 已是原生 CLI）** 和 **2.4 节（`system-event` 不可靠）** 让结论发生了三个变化：

# 一、结论的三处变化

## 变化 1：方案 2b 的"OpenClaw 扩 CLI"前提**消失了**

之前我以为 `openclaw cron upsert/remove` 不存在。文档 2.3 / 8.4 / 8.5 明确：`openclaw cron add --name --cron/--at --session isolated --message ... --announce` 已经是公开 CLI。所以**方案 2b 的实施代价大幅下降**——TC 后端可以直接 subprocess 调 `openclaw cron add` 写入/创建 cron job，无须扩 OpenClaw。

> ⚠️ 但文档**没明确**提到 `openclaw cron remove / list / update`。如果这些不存在，旧 at-job 没法清理、`task_center#XX` cron 也无法 disable，**方案 2b 会被这一点卡住**。这是 plan 落地前必须先验证的硬条件。

## 变化 2：**你现有的 task_center#XX cron job 全部是文档明确"不推荐"的形态**

文档 1.1 表 + 2.4 + 4.3 + 5.4 + 7 的口径完全一致：

> `cron + session main + systemEvent` → `deliveryStatus` 经常 `not-requested`，**不适合作为 TaskCenter 普通到点提醒的主路径**。

而你 jobs.json 里 18 条 cron job 抽查（#63 / #92 / #93 / #94 / #104 / #112 / #154 顺延 at-job 等），**全部都是 `sessionTarget: main` + `payload.kind: systemEvent`**——也就是文档最不推荐的那一种。

也就是说：哪怕**不做**本次"补盲点"功能，把这一批迁到 `cron isolated agentTurn + announce`（文档 8.5 模板）或直接 `openclaw message send`（如果有"到点 message send"能力），本身就是一笔独立、ROI 不错的改进。

## 变化 3：对"补盲点"这个起步阶段，三个方案的最终对比变清晰了

| 方案 | TC 侧成本 | OpenClaw 侧成本 | 每条提醒成本 | 触发确定性 | 文档官方推荐度 |
|------|----------|----------------|--------------|-----------|----------------|
| **方案 1：TC 内 ticker + `message send`** | 新增 worker 进程，~80 行 | 0 | **0 token** | 最高 | ⭐⭐⭐（文档 6.1 + 4.1 明示"到点提醒"首选 message send） |
| **方案 2b：TC 调 `openclaw cron add` 同步 cron** | 0 进程新增，仅 subprocess | 0（CLI 已存在，但要验 remove/list） | 有 token（isolated agentTurn 即便 prompt 极短也要跑一轮 LLM） | 高（前提 prompt 守纪律） | ⭐⭐（不在 6.x 任何子节首选） |
| **方案 2a：TC 调 `agent --deliver` 让 LLM 维护 cron** | 0 | 0 | 双倍 token（main agent 上下文较重） | 中（依赖 LLM 准确性） | ⭐ |

**关键反差**：
- 文档明确推荐 **"内容确定 → message send"**，但 OpenClaw cron 本身**没有提供"到点 message send"**这种调度形式（cron 只能调度 agentTurn 或 systemEvent）。
- 想要"到点 0-token 确定性提醒"，**就必须 TC 自己跑 ticker**——这条路 OpenClaw 帮不上忙。
- 方案 2b 即便 prompt 极简（"请只输出以下文案：${text}"），每次到点仍要跑一轮 LLM。一天 10 条提醒 ≈ 10 次 LLM 调用，长期是固定成本。

## 我修正后的推荐

**两步走，第一步可以脱钩做**：

1. **独立项**（建议放在补盲点**前面**做，1-2 小时）：把现有 18 条 task_center#XX 重复 cron 从 `system-event main` 形态批量迁到 `isolated agentTurn + announce` 形态。文案 prompt 可极简："请按以下文案原样发给南哥：${text}"。**这一步解决了你现有提醒一直没保障投递的根本可靠性问题**——不依赖任何新功能。

2. **补盲点本身**：再二选一——
   - **2A. 方案 1（推荐）**：TC 内置一个轻量 worker，到点直接 `openclaw message send`。mobile 改的 task 提醒由 TC 接管，**同时 disable OpenClaw 那边对应 cron job**（需要 `openclaw cron remove`）。这一条路是文档官方推荐的"到点提醒"最佳实践，长期 0 token 成本。
   - **2B. 方案 2b**：TC 调 `openclaw cron add` 自动维护 cron。零 worker，但有持续 token 成本，且需要 `openclaw cron remove` 来管理生命周期。

