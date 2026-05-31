# OpenClaw Cron CLI 使用说明

> 适用对象：TaskCenter 后端、维护脚本、定时任务脚本，以及接手本项目但不了解 OpenClaw cron 的 AI Agent。
>
> 目标：说明如何通过 `openclaw cron` 命令管理 Gateway 内置定时任务；本文件只覆盖 CLI 用法，不假设存在稳定公开的 HTTP API。

---

## 1. 总体结论

OpenClaw cron 是 Gateway 内置调度器，适合做：

- 到点提醒；
- 周期任务；
- 定时运行隔离 Agent 任务；
- 定时唤醒主会话；
- 查看任务执行历史与投递状态。

常用命令：

```bash
openclaw cron status
openclaw cron list
openclaw cron show <job-id>
openclaw cron add
openclaw cron edit <job-id>
openclaw cron enable <job-id>
openclaw cron disable <job-id>
openclaw cron rm <job-id>
openclaw cron run <job-id>
openclaw cron runs <job-id>
```

对 TaskCenter 的默认建议：

1. **普通确定性提醒**：TaskCenter 到点后直接用 `openclaw message send` 更稳；cron 只在需要 OpenClaw 代为调度时使用。
2. **定时 AI 任务**：用 `openclaw cron add --session isolated --message ... --announce ...`。
3. **只唤醒主会话**：用 `openclaw cron add --session main --system-event ...`，但不要把它当作确定性飞书投递。
4. **脚本集成**：优先通过 CLI 参数数组调用，不要 shell 拼接。

---

## 2. 基础查看命令

### 2.1 查看调度器状态

```bash
openclaw cron status
```

用于确认 Gateway cron scheduler 是否运行、是否有任务待执行。

### 2.2 列出任务

```bash
# 只列出启用任务
openclaw cron list

# 包含 disabled 任务
openclaw cron list --all

# JSON 输出，适合脚本处理
openclaw cron list --json
```

脚本处理时优先用 `--json`，不要解析人类可读表格。

### 2.3 查看单个任务详情

```bash
openclaw cron show <job-id>
```

重点看：

- `schedule`：什么时候执行；
- `sessionTarget`：主会话还是隔离任务；
- `payload.kind`：`systemEvent` 还是 `agentTurn`；
- `delivery`：是否配置投递；
- `state.nextRunAtMs`：下次执行时间；
- `state.lastRunStatus`：上次执行状态；
- `state.lastDeliveryStatus`：上次投递状态。

### 2.4 查看执行历史

```bash
openclaw cron runs <job-id>
```

排查“dashboard 显示成功但用户没收到”时，重点看：

```text
status: ok
summary: ...
deliveryStatus: delivered | not-requested | not-delivered
```

含义：

- `status: ok`：cron job 执行成功；
- `deliveryStatus: delivered`：已完成外部投递；
- `deliveryStatus: not-requested`：任务没有请求外部投递，常见于 `systemEvent`；
- `deliveryStatus: not-delivered` / error：请求了投递但失败，需要查 channel、target、权限或网络。

---

## 3. 三种 schedule

### 3.1 一次性任务：`--at`

```bash
openclaw cron add \
  --name "一次性提醒" \
  --at "2026-05-18T09:00:00+08:00" \
  --session isolated \
  --message "请只发送一句：提醒：测试" \
  --announce \
  --channel feishu \
  --to user:ou_xxx \
  --delete-after-run
```

说明：

- `--at` 支持 ISO 时间；
- 带 `+08:00` 时按明确时区解释；
- 不带时区的时间容易被当作 UTC，建议始终写时区或使用 `--tz`；
- 一次性任务建议加 `--delete-after-run`，执行成功后自动清理。

### 3.2 固定间隔：`--every`

```bash
openclaw cron add \
  --name "每10分钟检查一次" \
  --every "10m" \
  --session isolated \
  --message "检查指定状态；正常输出 NO_REPLY，异常输出告警。" \
  --announce \
  --channel feishu \
  --to user:ou_xxx
```

适合简单轮询，但不要滥用高频检查。高频任务更容易消耗 token、刷屏或制造负载。

### 3.3 Cron 表达式：`--cron` + `--tz`

```bash
openclaw cron add \
  --name "每日22点晚间收口" \
  --cron "0 22 * * *" \
  --tz "Asia/Shanghai" \
  --session isolated \
  --message "你是任务晚间收口助手。请读取 task_center 今日任务并分组输出。" \
  --announce \
  --channel feishu \
  --to user:ou_xxx \
  --timeout-seconds 180
```

说明：

- `--cron "0 22 * * *"` 表示每天 22:00；
- `--tz "Asia/Shanghai"` 表示按北京时间解释；
- 周期任务必须明确是否需要投递；需要飞书收到就配置 `--announce --channel feishu --to ...`。

---

## 4. 两种执行内容：`systemEvent` vs `agentTurn`

### 4.1 发布消息到主时间线：`--session main --system-event`

对应 Dashboard：

> 发布消息到主时间线 / 主时间线消息

示例：

```bash
openclaw cron add \
  --name "主会话唤醒" \
  --at "2026-05-18T09:00:00+08:00" \
  --session main \
  --system-event "提醒：回到刚才主会话讨论的事项，结合当前上下文继续处理。" \
  --wake now \
  --delete-after-run
```

含义：

- 到点向主会话注入一条系统事件；
- 主助手会在当前主会话上下文里处理；
- 适合唤醒主会话、继续上下文相关任务；
- **不等于直接发飞书消息**；常见投递状态是 `deliveryStatus: not-requested`。

不适合：

- 生产告警；
- TaskCenter 普通到点提醒；
- 必须保证用户收到的通知。

### 4.2 运行助手任务（隔离）：`--session isolated --message`

对应 Dashboard：

> 运行助手任务（隔离） / 助手任务提示

示例：

```bash
openclaw cron add \
  --name "备份健康检查" \
  --cron "10 3 * * *" \
  --tz "Asia/Shanghai" \
  --session isolated \
  --message "你是 OpenClaw 数据备份健康检查助手。检查最新备份 manifest；正常输出 NO_REPLY，异常输出简洁中文告警。" \
  --announce \
  --channel feishu \
  --to user:ou_xxx \
  --timeout-seconds 180
```

含义：

- 到点新开隔离 Agent 任务；
- `--message` 是本次助手任务 prompt；
- 可让 Agent 查文件、查 API、总结、判断；
- 加 `--announce --channel feishu --to ...` 后，最终回复会投递到飞书。

适合：

- 晚间收口；
- 周报；
- 健康检查；
- 异常才提醒的巡检任务；
- 需要角色、步骤、输出规则的定时任务。

---

## 5. Delivery 投递参数

如果 cron 任务需要把最终结果发到飞书，通常需要：

```bash
--announce \
--channel feishu \
--to user:ou_xxx
```

说明：

- `--announce`：让 cron runner fallback-deliver Agent 最终回复；
- `--channel feishu`：投递渠道为飞书；
- `--to user:ou_xxx`：投递给飞书用户；
- `--to chat:oc_xxx`：投递给飞书群 / 会话。

注意：

- `--deliver` 是旧 alias，优先写 `--announce`；
- `--no-deliver` 表示不做 runner fallback delivery；
- `systemEvent` 默认不请求 delivery，不要靠它验证飞书送达；
- 判断是否真的投递，看 run history 里的 `deliveryStatus`。

当前task owner DM 常用目标：

```text
user:ou_example_user
```

---

## 6. 修改、启停、删除、调试

### 6.1 修改任务

改一次性时间：

```bash
openclaw cron edit <job-id> \
  --at "2026-05-18T10:00:00+08:00"
```

改周期表达式：

```bash
openclaw cron edit <job-id> \
  --cron "0 21 * * *" \
  --tz "Asia/Shanghai"
```

改隔离助手 prompt：

```bash
openclaw cron edit <job-id> \
  --message "新的助手任务提示..."
```

改主时间线消息：

```bash
openclaw cron edit <job-id> \
  --system-event "新的主时间线消息..."
```

改投递目标：

```bash
openclaw cron edit <job-id> \
  --announce \
  --channel feishu \
  --to user:ou_xxx
```

### 6.2 禁用 / 启用

```bash
openclaw cron disable <job-id>
openclaw cron enable <job-id>
```

适合临时暂停周期任务。相比删除，禁用更容易恢复。

### 6.3 删除

```bash
openclaw cron rm <job-id>
```

适合彻底取消任务。删除前确认 job id，避免误删。

### 6.4 立即运行调试

```bash
openclaw cron run <job-id>
```

用于验证 prompt、工具权限、投递配置是否正确。调试后用：

```bash
openclaw cron runs <job-id>
```

检查执行结果和 `deliveryStatus`。

---

## 7. TaskCenter 推荐用法

### 7.1 普通到点提醒

如果 TaskCenter 自己已经知道到点了，并且文案已经组装好，优先不用 cron，直接发：

```bash
openclaw message send \
  --channel feishu \
  --target user:ou_xxx \
  --message "提醒：现在是 2026-05-18 09:00（北京时间）\n\ntask_center #156：让朱老师填写《私有云部署前信息问卷》。"
```

原因：

- 不经过模型；
- 0 token；
- 链路短；
- 最接近确定性通知。

### 7.2 由 OpenClaw 负责调度普通提醒

如果 TaskCenter 只负责创建任务，希望 OpenClaw cron 到点触发提醒，可使用隔离 Agent 任务并明确投递：

```bash
openclaw cron add \
  --name "提醒：task_center#156 填写部署问卷" \
  --at "2026-05-18T09:00:00+08:00" \
  --session isolated \
  --message "请只发送以下提醒文本，不要扩写：提醒：现在是 2026-05-18 09:00（北京时间）\n\ntask_center #156：让朱老师填写《私有云部署前信息问卷》。" \
  --announce \
  --channel feishu \
  --to user:ou_xxx \
  --delete-after-run
```

如果完全不需要 Agent 加工，长期更理想的方式是 TaskCenter 内置 dispatcher 到点调用 `openclaw message send`。

### 7.3 晚间收口 / 周报 / 巡检

这类任务需要 Agent 查数据和整理，推荐 cron isolated agentTurn：

```bash
openclaw cron add \
  --name "任务晚间收口（每日22:00）" \
  --cron "0 22 * * *" \
  --tz "Asia/Shanghai" \
  --session isolated \
  --message "你是任务晚间收口助手。请读取 task_center 今日任务，分组整理后发给task owner。" \
  --announce \
  --channel feishu \
  --to user:ou_xxx \
  --timeout-seconds 180
```

---

## 8. 脚本集成建议

Python 中调用 cron CLI 时使用参数数组：

```python
import subprocess

subprocess.run(
    [
        "openclaw", "cron", "add",
        "--name", "提醒：task_center#156",
        "--at", "2026-05-18T09:00:00+08:00",
        "--session", "isolated",
        "--message", "请只发送一句：提醒：task_center #156 ...",
        "--announce",
        "--channel", "feishu",
        "--to", "user:ou_xxx",
        "--delete-after-run",
    ],
    check=True,
)
```

不要用 shell 拼接：

```python
# 不推荐
subprocess.run(f'openclaw cron add --name "{name}" --message "{message}"', shell=True)
```

原因：

- 文案可能包含换行、引号、反斜杠；
- shell 拼接容易出现转义问题；
- 参数数组更安全、更容易记录错误。

如需排错，使用：

```python
result = subprocess.run(args, text=True, capture_output=True)
if result.returncode != 0:
    raise RuntimeError(
        f"openclaw cron command failed: returncode={result.returncode}, "
        f"stdout={result.stdout}, stderr={result.stderr}"
    )
```

---

## 9. 注意事项

1. `openclaw cron` 是 CLI 管理入口；不要假设有稳定公开的 HTTP API 可直接依赖。
2. 时间默认优先写明确时区，例如 `2026-05-18T09:00:00+08:00` 或 `--tz Asia/Shanghai`。
3. 需要飞书投递时，优先用 `--announce --channel feishu --to user:ou_xxx` 明确目标。
4. `status: ok` 只表示 cron 执行成功；是否投递看 `deliveryStatus`。
5. `systemEvent` 适合唤醒主会话，不适合确定性飞书通知。
6. `isolated agentTurn` 适合定时 AI 任务，成本比 main session 更可控。
7. 高频周期任务要谨慎，避免 token 消耗和重复打扰。
8. 一次性任务建议加 `--delete-after-run`，避免堆积无用 job。
9. 修改/取消 TaskCenter 任务时，如果已有对应 cron job，必须同步 `edit` / `disable` / `rm`，避免两本账不一致。
