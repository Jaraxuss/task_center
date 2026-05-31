# OpenClaw 命令行发送飞书消息方式说明

> 适用对象：TaskCenter 维护脚本、定时任务、告警脚本，以及接手本项目但不了解 OpenClaw/飞书链路的 AI Agent。
>
> 目标：让新的 AI 或脚本维护者看完后能判断：什么时候直接发飞书，什么时候让 Agent 处理后再发，什么时候创建定时 Agent 任务，什么时候只唤醒主会话。
>
> 相关文档：cron CLI 的增删改查、调试与 TaskCenter 集成细节见 [`OPENCLAW_CRON_CLI.md`](./OPENCLAW_CRON_CLI.md)。

---

## 1. 总体结论：先按“是否需要模型处理”和“是否定时”分流

OpenClaw 里常见的飞书通知/提醒链路有 4 类：

| 方案 | 定义 | 典型命令 | 是否经过 Agent/模型 | 是否定时 | 是否确定性投递 | 成本 |
|---|---|---|---|---|---|---|
| 原文确定发送 | 把已有文本原样发到飞书 | `openclaw message send` | 否 | 否 | 高 | 约 0 token |
| 立即让 Agent 处理后发送 | 现在跑一次 Agent，把最终回复投递到飞书 | `openclaw agent --message ... --deliver` | 是 | 否 | 中，取决于 Agent 输出和投递配置 | 有 token 消耗；用新 `--session-id` 更干净 |
| 定时让 Agent 处理后发送 | 到点新开隔离 Agent 任务，执行 prompt 后投递 | `openclaw cron add --session isolated --message ... --announce` | 是 | 是 | 中高，配置明确时可追踪 delivery | 有 token 消耗，较可控 |
| 定时唤醒主会话 | 到点向主会话注入一条系统事件 | `openclaw cron add --session main --system-event ...` | 是，进入主会话处理 | 是 | 低，不等于飞书送达 | 有 token 消耗，最不稳定 |

一句话判断：

- **消息已经确定，只要发出去** → 用 `openclaw message send`。
- **现在需要 AI 总结/改写/判断后发** → 用 `openclaw agent --deliver`；如果希望上下文干净，给它一个新的 `--session-id`。
- **到点需要 AI 查数据/读文件/总结后发** → 用 `openclaw cron add --session isolated --message ... --announce`。
- **只是要把一条事件塞回主会话，让主助手基于当前上下文处理** → 用 `openclaw cron add --session main --system-event ...`。

TaskCenter 默认建议：

1. **普通到点提醒**：优先 `openclaw message send`，因为提醒文案通常已经确定。
2. **晚间收口 / 周报 / 备份健康检查**：优先 `cron isolated agentTurn`，因为需要查数据、判断、整理。
3. **需要立即 AI 处理并发送**：用 `openclaw agent --deliver`。
4. **不要把 `system-event` 当作确定性飞书通知**；它是唤醒主会话，不是消息发送器。

---

## 2. 四种方案详解

### 2.1 原文确定发送：`openclaw message send`

#### 定义

`openclaw message send` 是 OpenClaw 后端 / channel 插件直接发消息到指定渠道。

它不经过 Agent，不调用模型，不改写内容，基本可以理解为：

> 把这段已经确定的文本，原样发到飞书目标。

#### 适合场景

- TaskCenter 到点提醒；
- 备份失败告警；
- 服务异常告警；
- 脚本执行失败通知；
- 简短状态变更通知；
- 任何“文案已经准备好，只差发送”的场景。

#### 成本、可靠性与格式限制

- 模型 token：约 0；
- 链路：最短；
- 确定性：最高；
- 风险：主要是飞书插件、目标 ID、网络或权限问题；不会被 Agent 输出 `NO_REPLY` 或静默策略影响；
- 格式：按纯文本使用，支持换行和简单项目符号即可；不要依赖 Markdown/富文本渲染，复杂卡片、表格、按钮、状态色应改走 Feishu 原生卡片、文档链接或 Agent/脚本生成的专门消息格式。

#### 基本命令

发给飞书用户：

```bash
openclaw message send \
  --channel feishu \
  --target user:ou_xxx \
  --message "消息内容"
```

发给飞书群 / 会话：

```bash
openclaw message send \
  --channel feishu \
  --target chat:oc_xxx \
  --message "消息内容"
```

#### 当前task owner DM 的常用目标

task owner的 Feishu open_id：

```text
ou_example_user
```

直发示例：

```bash
openclaw message send \
  --channel feishu \
  --target user:ou_example_user \
  --message "测试：OpenClaw 能否通过飞书直接发送"
```

#### Python 脚本安全调用

不要通过 shell 拼接长字符串，尤其不要这样：

```python
# 不推荐：容易被引号、换行、反斜杠影响
subprocess.run(f'openclaw message send --channel feishu --target user:ou_xxx --message "{text}"', shell=True)
```

推荐使用参数数组：

```python
import subprocess

subprocess.run(
    [
        "openclaw", "message", "send",
        "--channel", "feishu",
        "--target", "user:ou_xxx",
        "--message", text,
    ],
    check=True,
)
```

如果需要记录失败原因：

```python
import subprocess

result = subprocess.run(
    [
        "openclaw", "message", "send",
        "--channel", "feishu",
        "--target", "user:ou_xxx",
        "--message", text,
    ],
    text=True,
    capture_output=True,
)

if result.returncode != 0:
    raise RuntimeError(
        f"openclaw message send failed: returncode={result.returncode}, "
        f"stdout={result.stdout}, stderr={result.stderr}"
    )
```

#### TaskCenter 到点提醒推荐格式

```text
提醒：现在是 2026-05-18 09:00（北京时间）

task_center #156：让朱老师填写《私有云部署前信息问卷》。

关键备注：
Acme Corp私有云部署申请已提交；下一步需要引导客户朱老师填写部署前信息问卷。
问卷链接：https://...
```

建议：

- 必带 `task_center #任务ID`；
- 必带任务标题；
- 有业务上下文时保留 1-3 句关键备注；
- 长日志、长 Markdown 不要整段塞进飞书消息；
- 长内容只发摘要 + 本地文件路径 / manifest 路径 / task id。

---

### 2.2 立即让 Agent 处理后发送：`openclaw agent --deliver`

#### 定义

`openclaw agent --message ... --deliver` 是立即运行一次 Agent turn，让模型按 prompt 处理内容，并把 Agent 的最终回复投递到飞书。

它适合“现在就让 AI 做一次加工，然后发出去”。

#### 适合场景

- 把长日志压缩成简短中文提醒；
- 读取文件/目录后总结结果；
- 需要模型判断“是否值得通知”；
- 需要生成更自然、结构化的中文消息；
- 维护纪要、临时报告、一次性总结。

#### 成本、上下文与可靠性

- 模型 token：有消耗；
- 消耗大小取决于所选 Agent/session 的上下文、prompt 长度、工具调用结果和最终输出；
- `--agent main` 表示使用 main agent 的配置、工具、工作区和默认/主 session；**不要把它理解成自动获取当前飞书 DM 会话的完整上下文**；
- 如果需要当前聊天上下文，必须显式路由到对应 session；脚本里通常不建议依赖当前聊天上下文，因为不可控且 token 成本高；
- 如果希望上下文干净，用新的 `--session-id`；如果希望同类自动任务保留自己的连续上下文，用固定 `--session-id`；
- 如果 Agent 输出 `NO_REPLY` 或没有用户可见最终回复，可能不会投递期望消息；
- `--deliver` 只负责投递 Agent 最终回复，不代表一定有可投递内容。

#### 三组参数要分清

| 参数 | 作用 | 说明 |
|---|---|---|
| `--message` | 给 Agent 的任务内容 | 例如“请总结这份日志并发给task owner” |
| `--agent` / `--session-id` | 选择 Agent 在哪个会话里运行 | 必须提供其一，否则 Agent 不知道在哪里跑 |
| `--reply-channel` / `--reply-to` | 选择最终投递到哪里 | 这里只负责投递目标，不负责选择会话 |

关键规则：

> `--reply-channel` 和 `--reply-to` 不能替代 `--agent` / `--session-id`。
>
> `--deliver` 只负责把 Agent 的最终回复发出去，不负责选择 Agent 会话入口。

#### 写法 A：指定 `--agent main`，使用 main agent 默认/主 session

```bash
openclaw agent \
  --agent main \
  --message "Feishu 授权链路维护纪要：doc=/home/velen/.openclaw/workspace/docs/reports，请用简洁中文总结发给task owner" \
  --deliver \
  --reply-channel feishu \
  --reply-to user:ou_example_user
```

说明：

- `--agent main`：使用 main agent 的配置、工具、工作区和默认/主 session；
- 这不等于自动使用当前飞书 DM 会话上下文；
- `--deliver`：要求把 Agent 最终回复投递出去；
- `--reply-channel feishu`：最终投递渠道是飞书；
- `--reply-to user:ou_...`：最终投递给指定飞书用户。

适合：临时让 main agent 处理一次任务，且不强求上下文干净。

#### 写法 B：指定新的 `--session-id`，立即运行一个干净上下文任务

如果要“立即版 isolated agentTurn”，给这次命令一个新的 session id：

```bash
sid="oneoff-feishu-report-$(date +%Y%m%d%H%M%S)"

openclaw agent \
  --agent main \
  --session-id "$sid" \
  --message "请读取 /path/to/report 并总结成简洁中文发给task owner。" \
  --deliver \
  --reply-channel feishu \
  --reply-to user:ou_example_user
```

说明：

- 仍然使用 `main` agent 的能力、工具和工作区；
- 由于 `--session-id` 是新的，不会直接混入当前飞书 DM 会话上下文；
- 适合一次性维护报告、临时日志总结、脚本触发的干净任务；
- 如果未来重复使用同一个 session id，它会积累该自动任务自己的上下文。

#### 写法 C：指定固定 `--session-id`，让同类自动任务保留自己的上下文

适合脚本 / 周期任务，让同一类自动任务稳定落在一个固定 session：

```bash
openclaw agent \
  --agent main \
  --session-id taskcenter-maintenance-report \
  --message "请读取 /path/to/report 并总结成简洁中文发给task owner" \
  --deliver \
  --reply-channel feishu \
  --reply-to user:ou_example_user
```

说明：

- 固定 `--session-id` 会让这类自动任务形成自己的连续上下文；
- 适合维护报告、固定巡检、固定类别的脚本总结；
- 不适合必须每次完全干净的任务。每次干净请用新的 session id。

#### Python 脚本安全调用

```python
import subprocess
from datetime import datetime

prompt = "请把以下错误日志总结成简洁中文提醒task owner：\n" + log_text
session_id = "oneoff-error-summary-" + datetime.now().strftime("%Y%m%d%H%M%S")

result = subprocess.run(
    [
        "openclaw", "agent",
        "--agent", "main",
        "--session-id", session_id,  # 新 session id：避免混入当前飞书 DM 上下文
        "--message", prompt,
        "--deliver",
        "--reply-channel", "feishu",
        "--reply-to", "user:ou_example_user",
    ],
    text=True,
    capture_output=True,
)

if result.returncode != 0:
    raise RuntimeError(
        f"openclaw agent --deliver failed: returncode={result.returncode}, "
        f"stdout={result.stdout}, stderr={result.stderr}"
    )
```

---

### 2.3 定时让 Agent 处理后发送：`openclaw cron add --session isolated --message ... --announce`

> 更完整的 cron 命令行管理说明见 [`OPENCLAW_CRON_CLI.md`](./OPENCLAW_CRON_CLI.md)。

#### 定义

这是 Gateway cron 到点后新开一个隔离 Agent 任务，执行 `--message` 中的 prompt，并通过 `--announce` 把最终回复投递到飞书。

Dashboard 中通常对应：

> **运行助手任务（隔离）** / **助手任务提示**

底层概念通常是：

```json
{
  "sessionTarget": "isolated",
  "payload": {
    "kind": "agentTurn",
    "message": "你是 OpenClaw 数据备份健康检查助手..."
  },
  "delivery": {
    "mode": "announce",
    "channel": "feishu",
    "to": "user:ou_xxx"
  }
}
```

#### 适合场景

- 每晚 22:00 读取 TaskCenter 今日任务并生成晚间收口；
- 每天 03:10 检查备份状态，异常才提醒；
- 每周生成客户跟进总结；
- 到点读取某个文件/目录/API，整理后发飞书；
- 需要明确角色、步骤、输出规则的定时任务。

#### 成本与可靠性

- 模型 token：有消耗；
- 相比 main session，isolated 会话上下文更干净，成本更可控；
- 主要 token 来自：系统基础提示、任务 prompt、工具输出、最终回复；
- 配置 `--announce --channel feishu --to ...` 后，投递链路明确，dashboard 可看 `deliveryStatus`；
- 如果 Agent 正常输出 `NO_REPLY`，可能被视为无需投递，适合“正常不打扰，异常才提醒”的任务。

#### 基本命令

```bash
openclaw cron add \
  --name "命令行触发cron测试" \
  --at "2026-05-16T21:20:00+08:00" \
  --session isolated \
  --message "请只发送一句：提醒：命令行触发cron测试" \
  --announce \
  --channel feishu \
  --to user:ou_example_user \
  --delete-after-run
```

#### 周期任务示例：每日备份检查

```bash
openclaw cron add \
  --name "OpenClaw 数据备份失败监控（每日03:10）" \
  --cron "10 3 * * *" \
  --tz "Asia/Shanghai" \
  --session isolated \
  --message "你是 OpenClaw 数据备份健康检查助手。请检查最新备份 manifest；如果全部正常，只输出 NO_REPLY；如果异常，输出简洁中文告警。" \
  --announce \
  --channel feishu \
  --to user:ou_example_user \
  --timeout-seconds 180
```

#### 关键注意点

- `--message` 是助手任务提示，可以写完整 prompt、角色、步骤、输出规则；
- `--announce` 是 runner fallback delivery，表示把最终回复投递到指定渠道；
- `--channel feishu --to user:ou_xxx` 明确飞书目标；
- 定时任务如果需要查文件/API，建议写清楚“正常输出 NO_REPLY，异常才提醒”的规则，避免刷屏。

---

### 2.4 定时唤醒主会话：`openclaw cron add --session main --system-event ...`

#### 定义

`system-event` 是把一段文本作为系统事件注入主会话，让主助手在当前主时间线里看到并处理。

Dashboard 中通常对应：

> **发布消息到主时间线** / **主时间线消息**

底层概念通常是：

```json
{
  "sessionTarget": "main",
  "payload": {
    "kind": "systemEvent",
    "text": "提醒：..."
  }
}
```

它更像：

```text
系统在主时间线里对助手说：
“现在到时间了，你该处理这件事了。”
```

而不是：

```text
直接给飞书用户发一条消息。
```

#### `system-event` 和 prompt 的关系

`system-event` 不是专门的“助手任务 prompt”，但它的内容可以写成指令。

例如可以写：

```text
提醒：现在检查备份状态。请读取 xxx 并判断是否需要提醒task owner。
```

但语义仍然是：

> 这是一条进入主会话的系统事件，由主助手结合当前主会话上下文和规则处理。

它不同于 isolated agentTurn 的 `--message`：

- `system-event`：给主助手的一条事件 / 消息；
- `agentTurn --message`：给隔离助手的一次任务 prompt。

#### 适合场景

- 到点提醒主助手回到当前主会话上下文继续处理；
- 需要利用主会话历史、近期对话、用户偏好来判断下一步；
- 重启后继续某个主会话任务；
- 内部唤醒、heartbeat、需要主助手自主判断是否打扰用户的事件。

#### 不适合场景

- 生产告警；
- TaskCenter 普通到点提醒；
- 需要保证飞书一定收到的通知；
- 高频提醒。

原因：`system-event` 的执行成功不等于飞书送达。常见 dashboard/run 结果可能是：

```text
status: ok
deliveryStatus: not-requested
summary: 提醒：命令行触发cron测试
```

含义是：

> cron job 成功把 system event 注入主会话，Agent 处理也没有报错，但这个任务没有请求外部飞书投递。

#### 基本命令

```bash
openclaw cron add \
  --name "主会话唤醒测试" \
  --at "2026-05-16T20:59:00+08:00" \
  --session main \
  --system-event "提醒：命令行触发cron测试" \
  --wake now \
  --delete-after-run
```

#### 成本与可靠性

- 模型 token：有消耗，而且可能不低；
- 因为进入 main session，可能加载较多主会话历史和上下文；
- 是否最终发飞书取决于主助手输出和运行状态；
- 不建议用于高频、确定性提醒。

---

## 3. Dashboard 字段与 CLI 对照

| Dashboard 执行内容 | Dashboard 文案字段 | 底层 payload | CLI 对应 | 用途 |
|---|---|---|---|---|
| 发布消息到主时间线 | 主时间线消息 | `systemEvent.text` | `--session main --system-event "..."` | 唤醒主会话 / 注入系统事件 |
| 运行助手任务（隔离） | 助手任务提示 | `agentTurn.message` | `--session isolated --message "..."` | 到点运行独立 Agent 任务 |

注意：

- “发布消息到主时间线”不是“确定性发飞书消息”；
- “运行助手任务（隔离）”如果想发飞书，必须配置 delivery，例如 CLI 里加 `--announce --channel feishu --to user:ou_xxx`；
- dashboard / runs 里要区分：
  - `status: ok`：任务执行成功；
  - `deliveryStatus: delivered`：已投递；
  - `deliveryStatus: not-requested`：没有请求外部投递。

---

## 4. 成本对比与选型建议

### 4.1 Token 消耗从低到高

```text
openclaw message send
≈ 0 token

< isolated agentTurn
有 token，但上下文干净、较可控

< openclaw agent --agent main --session-id <new-id> --deliver
有 token，但上下文相对干净

< openclaw agent --agent main --deliver / system-event main
可能较高，取决于默认/主 session 或主会话上下文
```

### 4.2 成本表

| 方式 | 模型调用 | 主要 token 来源 | 成本稳定性 | 备注 |
|---|---|---|---|---|
| `openclaw message send` | 无 | 无 | 最稳定 | 适合确定性提醒和告警 |
| `cron isolated agentTurn` | 有 | 系统提示 + 任务 prompt + 工具输出 + 最终回复 | 较可控 | 定时 AI 任务首选 |
| `openclaw agent --agent main --session-id <new-id> --deliver` | 有 | 系统提示 + prompt + 工具输出 + 最终回复 | 较可控 | 适合立即执行的干净上下文 AI 任务 |
| `openclaw agent --agent main --deliver` | 有 | main agent 默认/主 session 上下文 + prompt + 工具输出 | 中等到较高 | 适合立即 AI 加工后发送；不等于当前飞书 DM 上下文 |
| `cron main system-event` | 有 | 主会话上下文 + system event + 工具输出 | 最不可控 | 适合主会话唤醒，不适合确定性投递 |

### 4.3 可靠性表

| 方式 | 是否保证进入飞书投递链路 | 典型失败/不达预期原因 |
|---|---|---|
| `openclaw message send` | 是 | 飞书目标错误、权限/网络/插件异常 |
| `openclaw agent --deliver` | 是，前提是 Agent 有最终可投递回复 | 缺会话入口、误以为 `--agent main` 等于当前 DM 上下文、Agent 输出 `NO_REPLY`、飞书投递失败 |
| `cron isolated agentTurn + --announce` | 是，前提是配置了 delivery | 缺 `--announce`/`--to`、Agent 输出 `NO_REPLY`、任务超时 |
| `cron main system-event` | 否 | 只是注入主会话，`deliveryStatus` 常为 `not-requested` |

---

## 5. 常见错误与排查

### 5.1 只写 `--reply-channel` / `--reply-to`，没有指定会话入口

错误示例：

```bash
openclaw agent \
  --message "请总结这份报告发给task owner" \
  --deliver \
  --reply-channel feishu \
  --reply-to user:ou_example_user
```

典型报错：

```text
Pass --to <E.164>, --session-id, or --agent to choose a session
```

含义：

- 这不是飞书授权失败；
- 这是 `openclaw agent` 不知道该在哪个 Agent/session 中运行；
- 补上 `--agent main` 或 `--session-id xxx` 即可。

正确示例：

```bash
openclaw agent \
  --agent main \
  --message "请总结这份报告发给task owner" \
  --deliver \
  --reply-channel feishu \
  --reply-to user:ou_example_user
```

### 5.2 把 Feishu open_id 填到 `openclaw agent --to`

`openclaw agent --to` 主要用于 E.164 电话号这类入口，不建议把飞书 open_id 填进去。

飞书投递目标应放在：

```bash
--reply-channel feishu \
--reply-to user:ou_xxx
```

Agent 会话入口用：

```bash
--agent main
```

或：

```bash
--session-id some-fixed-session
```

### 5.3 误以为 `--agent main` 等于当前飞书 DM 完整上下文

`--agent main` 只表示使用 main agent 的配置和默认/主 session。

它不等于：

- 自动拿到当前飞书 DM 的完整历史；
- 自动继承当前用户消息所在 session；
- 自动使用当前对话的所有上下文。

如果脚本需要稳定、低成本、可复现的行为，优先把必要上下文写进 `--message`，并用新的或固定的 `--session-id` 控制上下文范围。

### 5.4 误以为 `--deliver` 一定会发飞书

`--deliver` 会把 Agent 的最终回复投递到指定目标，但前提是：

1. Agent turn 成功执行；
2. 指定了合法的会话入口；
3. 指定了合法的投递渠道和目标；
4. Agent 产生了可投递的最终回复；
5. 飞书插件/Gateway/OpenClaw 本身可用。

因此脚本里仍然要检查 CLI 退出码，不能假设调用了就一定送达。

### 5.5 误以为 `system-event` 是飞书消息

`system-event` 的机制不是“直接发送飞书消息”。

它做的是：

1. 把一段 `System:` 事件塞进 OpenClaw 主会话队列；
2. 唤醒 heartbeat / agent 处理；
3. 最终是否发飞书，取决于 Agent 是否输出用户可见回复，以及是否存在投递请求。

风险：

- Agent 可能判断“无需打扰”，输出 `HEARTBEAT_OK` / `NO_REPLY`；
- dashboard 可能显示任务 `status: ok`，但 `deliveryStatus: not-requested`；
- 它更像“唤醒/注入上下文”，不是可靠通知通道。

---

## 6. TaskCenter 场景推荐

### 6.1 到点提醒

推荐：`openclaw message send`

原因：

- 提醒内容已经确定；
- 不需要模型判断；
- 应尽量保证直接送达；
- token 成本约为 0。

### 6.2 晚间收口

推荐：`openclaw cron add --session isolated --message ... --announce ...`

原因：

- 需要读取 TaskCenter 当天任务；
- 需要分组、整理、生成自然语言；
- 需要遵守晚间收口规则；
- 隔离任务上下文更干净、成本更可控。

### 6.3 周报 / 客户材料生成结果

推荐：`openclaw cron add --session isolated --message ... --announce ...` 或 `openclaw agent --deliver`

选择方式：

- 定时执行 → cron isolated agentTurn；
- 现在立即处理 → agent deliver；若希望上下文干净，使用新的 `--session-id`。

原因：

- 需要汇总结构化数据；
- 需要把脚本输出转成人类可读格式；
- 可能需要判断 warning 是否值得突出提醒。

### 6.4 备份失败 / 服务异常

推荐：

- 如果脚本已经确定失败并写好了告警文案 → `openclaw message send`；
- 如果需要 Agent 读取 manifest / systemd 状态判断是否异常 → `cron isolated agentTurn`，正常输出 `NO_REPLY`，异常再发。

### 6.5 继续主会话里的未完成讨论

推荐：`cron main system-event`

原因：

- 任务依赖当前主会话上下文；
- 目标是唤醒主助手，而不是保证飞书收到一条固定文本；
- 不适合作为 TaskCenter 普通提醒的主路径。

---

## 7. 快速决策表

| 场景 | 推荐命令 | 原因 |
|---|---|---|
| TaskCenter 到点提醒 | `openclaw message send` | 确定性通知，链路短，0 token |
| 备份失败告警，脚本已确定失败 | `openclaw message send` | 不需要模型判断 |
| 脚本执行失败 | `openclaw message send` | 直接告警更可靠 |
| 长日志立即总结后通知 | `openclaw agent --agent main --session-id <new-id> --deliver` | 需要模型压缩，立即执行，且上下文干净 |
| 临时维护纪要立即发送 | `openclaw agent --agent main --session-id <new-id> --deliver` | 需要自然语言整理，不依赖当前聊天上下文 |
| 需要复用某类自动任务上下文 | `openclaw agent --agent main --session-id <固定id> --deliver` | 同类任务独立积累上下文 |
| 晚间收口定时任务 | `cron isolated agentTurn + announce` | 需要读取数据并结构化输出 |
| 周报 / 客户跟进总结定时任务 | `cron isolated agentTurn + announce` | 定时 AI 任务，成本可控 |
| 只想唤醒主会话 | `cron main system-event` | 注入主会话，不保证飞书直发 |
| 验证飞书送达 | `openclaw message send` 或 `cron isolated + announce` | 看 `deliveryStatus: delivered` |

---

## 8. 可复制模板

### 8.1 原文确定发送：飞书直发模板

```bash
text="提醒：这里写要发送的内容"

openclaw message send \
  --channel feishu \
  --target user:ou_example_user \
  --message "$text"
```

### 8.2 立即让 Agent 处理后发送：main agent 默认/主 session 模板

```bash
prompt="请把以下内容总结成简洁中文提醒task owner：..."

openclaw agent \
  --agent main \
  --message "$prompt" \
  --deliver \
  --reply-channel feishu \
  --reply-to user:ou_example_user
```

注意：这个模板使用 main agent 默认/主 session，不等于当前飞书 DM 完整上下文。

### 8.3 立即让 Agent 处理后发送：一次性干净 session 模板

```bash
prompt="请读取 /path/to/report 并总结成简洁中文提醒task owner：..."
sid="oneoff-agent-report-$(date +%Y%m%d%H%M%S)"

openclaw agent \
  --agent main \
  --session-id "$sid" \
  --message "$prompt" \
  --deliver \
  --reply-channel feishu \
  --reply-to user:ou_example_user
```

### 8.4 立即让 Agent 处理后发送：固定 session 模板

```bash
prompt="请读取 TaskCenter 今日数据并生成晚间收口消息。"

openclaw agent \
  --agent main \
  --session-id taskcenter-nightly-review \
  --message "$prompt" \
  --deliver \
  --reply-channel feishu \
  --reply-to user:ou_example_user
```

### 8.5 定时让 Agent 处理后发送：一次性任务模板

```bash
openclaw cron add \
  --name "一次性 Agent 定时提醒" \
  --at "2026-05-18T09:00:00+08:00" \
  --session isolated \
  --message "请读取 TaskCenter #156 的最新信息，生成一条简洁中文提醒发给task owner。" \
  --announce \
  --channel feishu \
  --to user:ou_example_user \
  --delete-after-run
```

### 8.6 定时让 Agent 处理后发送：周期任务模板

```bash
openclaw cron add \
  --name "每日任务晚间收口" \
  --cron "0 22 * * *" \
  --tz "Asia/Shanghai" \
  --session isolated \
  --message "你是任务晚间收口助手。请读取 task_center 今日任务，按已完成、待确认/未完成、已延期/已取消分组，发给task owner。" \
  --announce \
  --channel feishu \
  --to user:ou_example_user \
  --timeout-seconds 180
```

### 8.7 定时唤醒主会话：system-event 模板

```bash
openclaw cron add \
  --name "主会话唤醒" \
  --at "2026-05-18T09:00:00+08:00" \
  --session main \
  --system-event "提醒：回到刚才主会话讨论的事项，结合当前上下文继续处理。" \
  --wake now \
  --delete-after-run
```

注意：这个模板不适合验证飞书送达；它适合唤醒主助手。

---

## 9. 实施注意事项

1. 单条飞书消息尽量控制在几百字以内。
2. `openclaw message send --message` 按纯文本通道使用；换行和简单列表可以用，但不要强依赖 Markdown 加粗、表格、代码块等复杂渲染。
3. 长日志不要直接发全文，改发摘要 + 文件路径。
4. Python/Node/脚本中调用 CLI 时优先使用参数数组，不要 shell 拼接。
5. 必须检查 CLI 退出码。
6. 失败重试要有限次数，避免异常时刷屏。
7. 如果消息需要保证送达，不要用 `openclaw system event` / `cron main system-event`。
8. 如果用 `openclaw agent --deliver`，必须指定 `--agent` 或 `--session-id`。
9. 如果用 `cron isolated agentTurn` 并希望飞书收到，必须显式配置 `--announce --channel feishu --to ...`。
10. 如果 dashboard 显示 `status: ok` 但用户没收到，继续看 `deliveryStatus`：
   - `delivered`：已进入并完成投递；
   - `not-requested`：没有请求外部投递，常见于 `system-event`；
   - `not-delivered` / error：投递失败，需要查 channel/target/权限。
11. TaskCenter 的普通提醒文案应尽量在 TaskCenter 侧组装完整，然后使用 `openclaw message send` 发送；只有需要模型处理时才让 Agent 参与。
12. 脚本里如果要立即运行 Agent，默认优先用新的或固定的 `--session-id` 控制上下文；不要默认依赖 `--agent main` 的上下文，也不要假设它就是当前飞书 DM 会话。
