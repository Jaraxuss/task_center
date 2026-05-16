# OpenClaw 命令行发送飞书消息方式说明

> 适用对象：TaskCenter 维护脚本、定时任务、告警脚本，以及接手本项目但不了解 OpenClaw/飞书链路的 AI Agent。
>
> 目标：明确什么时候用 `openclaw message send` 直发飞书，什么时候用 `openclaw agent --deliver` 让 Agent 加工后再投递。

---

## 1. 总体结论

### 1.1 确定性通知：优先用 `openclaw message send`

适合：

- TaskCenter 到点提醒
- 备份失败告警
- 服务异常告警
- 脚本执行失败通知
- 简短状态变更通知

推荐原因：

- 链路短，不依赖模型生成；
- 不会被 Agent 判断成“无需打扰”而静默；
- 不依赖主会话是否空闲；
- 更适合生产型、确定性告警。

一句话判断：

> 如果消息内容已经确定，只是要通知用户，用 `openclaw message send`。

### 1.2 需要总结 / 改写 / 判断：用 `openclaw agent --deliver`

适合：

- 把长日志压缩成简短中文提醒；
- 读取文件/目录后总结结果；
- 需要模型判断“是否值得通知”；
- 需要生成更自然、结构化的中文消息；
- 周报、晚间收口、维护纪要等需要 Agent 加工的内容。

注意：

- `--deliver` 只表示“把 Agent 的最终回复投递出去”；
- 它不负责选择 Agent 会话；
- 必须额外用 `--agent` 或 `--session-id` 指定这次 Agent turn 在哪里运行。

一句话判断：

> 如果发出前还需要模型理解、压缩、总结或判断，用 `openclaw agent --deliver`。

---

## 2. 方式一：飞书直发 `openclaw message send`

### 2.1 基本命令

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

### 2.2 当前南哥 DM 的常用目标

南哥的 Feishu open_id：

```text
ou_8ca37a28527b51fdad39a83998c37625
```

直发示例：

```bash
openclaw message send \
  --channel feishu \
  --target user:ou_8ca37a28527b51fdad39a83998c37625 \
  --message "测试：OpenClaw 能否通过飞书直接发送"
```

### 2.3 在脚本中安全调用

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
    # 记录 stderr/stdout，避免假装已送达
    raise RuntimeError(
        f"openclaw message send failed: returncode={result.returncode}, "
        f"stdout={result.stdout}, stderr={result.stderr}"
    )
```

### 2.4 TaskCenter 到点提醒推荐格式

```text
提醒：现在是 2026-05-18 09:00（北京时间）

task_center #156：让朱老师填写《私有云部署前信息问卷》。

关键备注：
雷允上药业私有云部署申请已提交；下一步需要引导客户朱老师填写部署前信息问卷。
问卷链接：https://...
```

建议：

- 必带 `task_center #任务ID`；
- 必带任务标题；
- 有业务上下文时保留 1-3 句关键备注；
- 长日志、长 Markdown 不要整段塞进飞书消息；
- 长内容只发摘要 + 本地文件路径 / manifest 路径 / task id。

---

## 3. 方式二：Agent 加工后投递 `openclaw agent --deliver`

### 3.1 三组参数要分清

`openclaw agent --deliver` 至少涉及三件事：

| 参数 | 作用 | 说明 |
|---|---|---|
| `--message` | 给 Agent 的任务内容 | 例如“请总结这份日志并发给南哥” |
| `--agent` / `--session-id` | 选择 Agent 在哪个会话里运行 | 必须提供其一，否则 Agent 不知道在哪里跑 |
| `--reply-channel` / `--reply-to` | 选择最终投递到哪里 | 这里只负责投递目标，不负责选择会话 |

关键规则：

> `--reply-channel` 和 `--reply-to` 不能替代 `--agent` / `--session-id`。
>
> `--deliver` 只负责把 Agent 的最终回复发出去，不负责选择 Agent 会话入口。

### 3.2 正确写法：指定 `--agent main`

适合一次性维护命令，直接使用 main agent：

```bash
openclaw agent \
  --agent main \
  --message "Feishu 授权链路维护纪要：doc=/home/velen/.openclaw/workspace/docs/reports，请用简洁中文总结发给南哥" \
  --deliver \
  --reply-channel feishu \
  --reply-to user:ou_8ca37a28527b51fdad39a83998c37625
```

说明：

- `--agent main`：指定这次 Agent turn 在 main agent 下运行；
- `--deliver`：要求把 Agent 最终回复投递出去；
- `--reply-channel feishu`：最终投递渠道是飞书；
- `--reply-to user:ou_...`：最终投递给指定飞书用户。

### 3.3 正确写法：指定固定 `--session-id`

适合脚本 / 周期任务，让同一类自动任务稳定落在一个固定 session：

```bash
openclaw agent \
  --session-id taskcenter-maintenance-report \
  --message "请读取 /path/to/report 并总结成简洁中文发给南哥" \
  --deliver \
  --reply-channel feishu \
  --reply-to user:ou_8ca37a28527b51fdad39a83998c37625
```

适用场景：

- 周报；
- 晚间收口；
- 维护纪要；
- 需要保留同类自动任务上下文的脚本。

### 3.4 在脚本中安全调用 Agent deliver

```python
import subprocess

prompt = "请把以下错误日志总结成简洁中文提醒南哥：\n" + log_text

result = subprocess.run(
    [
        "openclaw", "agent",
        "--agent", "main",
        "--message", prompt,
        "--deliver",
        "--reply-channel", "feishu",
        "--reply-to", "user:ou_8ca37a28527b51fdad39a83998c37625",
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

## 4. 常见错误

### 4.1 只写 `--reply-channel` / `--reply-to`，没有指定会话入口

错误示例：

```bash
openclaw agent \
  --message "请总结这份报告发给南哥" \
  --deliver \
  --reply-channel feishu \
  --reply-to user:ou_8ca37a28527b51fdad39a83998c37625
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
  --message "请总结这份报告发给南哥" \
  --deliver \
  --reply-channel feishu \
  --reply-to user:ou_8ca37a28527b51fdad39a83998c37625
```

### 4.2 把 Feishu open_id 填到 `--to`

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

### 4.3 误以为 `--deliver` 一定会发飞书

`--deliver` 会把 Agent 的最终回复投递到指定目标，但前提是：

1. Agent turn 成功执行；
2. 指定了合法的会话入口；
3. 指定了合法的投递渠道和目标；
4. 飞书插件/Gateway/OpenClaw 本身可用。

因此脚本里仍然要检查 CLI 退出码，不能假设调用了就一定送达。

---

## 5. 为什么不建议用 `openclaw system event` 做确定性飞书告警

`openclaw system event` 的机制不是“直接发送飞书消息”。

它做的是：

1. 把一段 `System:` 事件塞进 OpenClaw 会话队列；
2. 唤醒 heartbeat / agent 处理；
3. 最终是否发飞书，取决于 Agent 是否输出用户可见回复。

风险：

- Agent 可能判断“无需打扰”，输出 `HEARTBEAT_OK`；
- 这样飞书不会收到消息；
- 它更像“唤醒/注入上下文”，不是可靠通知通道。

因此：

| 需求 | 推荐方式 |
|---|---|
| 确定性告警 / 到点提醒 | `openclaw message send` |
| 需要模型总结后再通知 | `openclaw agent --deliver` |
| 只是唤醒主会话或注入系统事件 | `openclaw system event` |

---

## 6. TaskCenter 场景推荐

### 6.1 到点提醒

推荐：`openclaw message send`

原因：

- 提醒内容已经确定；
- 不需要模型判断；
- 应尽量保证直接送达。

### 6.2 晚间收口

推荐：`openclaw agent --deliver`

原因：

- 需要读取 TaskCenter 当天任务；
- 需要分组、整理、生成自然语言；
- 需要遵守晚间收口规则。

### 6.3 周报 / 客户材料生成结果

推荐：`openclaw agent --deliver`

原因：

- 需要汇总结构化数据；
- 需要把脚本输出转成人类可读格式；
- 可能需要判断 warning 是否值得突出提醒。

### 6.4 备份失败 / 服务异常

推荐：`openclaw message send`

原因：

- 属于确定性告警；
- 不应被模型过滤；
- 链路越短越可靠。

---

## 7. 快速决策表

| 场景 | 推荐命令 | 原因 |
|---|---|---|
| TaskCenter 到点提醒 | `openclaw message send` | 确定性通知，链路短 |
| 备份失败告警 | `openclaw message send` | 不需要模型判断 |
| 脚本执行失败 | `openclaw message send` | 直接告警更可靠 |
| 长日志总结后通知 | `openclaw agent --deliver` | 需要模型压缩 |
| 晚间收口 | `openclaw agent --deliver` | 需要读取数据并结构化输出 |
| 周报 / 维护纪要 | `openclaw agent --deliver` | 需要生成自然语言总结 |
| 只想唤醒主会话 | `openclaw system event` | 不保证飞书直发 |

---

## 8. 可复制模板

### 8.1 飞书直发模板

```bash
text="提醒：这里写要发送的内容"

openclaw message send \
  --channel feishu \
  --target user:ou_8ca37a28527b51fdad39a83998c37625 \
  --message "$text"
```

### 8.2 Agent 加工后投递模板：main agent

```bash
prompt="请把以下内容总结成简洁中文提醒南哥：..."

openclaw agent \
  --agent main \
  --message "$prompt" \
  --deliver \
  --reply-channel feishu \
  --reply-to user:ou_8ca37a28527b51fdad39a83998c37625
```

### 8.3 Agent 加工后投递模板：固定 session

```bash
prompt="请读取 TaskCenter 今日数据并生成晚间收口消息。"

openclaw agent \
  --session-id taskcenter-nightly-review \
  --message "$prompt" \
  --deliver \
  --reply-channel feishu \
  --reply-to user:ou_8ca37a28527b51fdad39a83998c37625
```

---

## 9. 实施注意事项

1. 单条飞书消息尽量控制在几百字以内。
2. 长日志不要直接发全文，改发摘要 + 文件路径。
3. Python/Node/脚本中调用 CLI 时优先使用参数数组，不要 shell 拼接。
4. 必须检查 CLI 退出码。
5. 失败重试要有限次数，避免异常时刷屏。
6. 如果消息需要保证送达，不要用 `openclaw system event`。
7. 如果用 `openclaw agent --deliver`，必须指定 `--agent` 或 `--session-id`。
