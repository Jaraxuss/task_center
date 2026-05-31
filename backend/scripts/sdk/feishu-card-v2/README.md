# TaskCenter 飞书卡片 V2 SDK

> 目标：让 TaskCenter 直接通过飞书开放平台发送 Card JSON 2.0 卡片消息。普通文本提醒也统一包装为简洁卡片发送，不再依赖 `openclaw message send` 作为主通道。

## 定位

该 SDK 由 `/home/velen/velen/feishu-bot` 测试项目沉淀而来，但在 TaskCenter 中的定位不同：

- `feishu-bot`：验证飞书卡片 V2、Markdown 转卡片、发送 API。
- `TaskCenter Feishu Card SDK`：作为 TaskCenter 的正式投递适配器，用于后续 dispatcher / reminder delivery / 晚间收口卡片。

当前代码位置：

```text
backend/scripts/sdk/feishu-card-v2/
├── README.md
├── send_card_v2.py
├── examples/sample-card-v2.json
└── feishu_card_v2/
    ├── __init__.py
    ├── card.py      # Card JSON 2.0 builder / Markdown 转卡片 / 大小校验
    └── client.py    # tenant_access_token 缓存 + im/v1/messages 发送

backend/scripts/send_feishu_card.py  # 兼容入口，内部转发到 send_card_v2.py
backend/services/feishu_card/        # 兼容 import 层，内部 re-export feishu_card_v2
```

## 凭证配置

凭证跟随 TaskCenter 后端环境变量配置，优先使用 `TASK_CENTER_*` 命名：

```bash
TASK_CENTER_FEISHU_APP_ID=cli_xxx
TASK_CENTER_FEISHU_APP_SECRET=xxx
TASK_CENTER_FEISHU_DEFAULT_RECEIVE_ID=ou_xxx
TASK_CENTER_FEISHU_DEFAULT_RECEIVE_ID_TYPE=open_id
```

兼容已有脚本环境变量：

```bash
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
```

注意：

- 不要把真实 `app_secret` 写进仓库。
- `.env.example` 只保留占位符。
- `tenant_access_token` 有效期 2 小时，SDK 会在进程内缓存并提前 5 分钟刷新。

## 基本用法

### 发送简单文本卡片

```python
from config import get_settings
from feishu_card_v2 import FeishuCardClient, FeishuTarget, text_to_card_v2

settings = get_settings()
client = FeishuCardClient.from_settings(settings)
target = FeishuTarget.from_settings(settings)

card = text_to_card_v2(
    "提醒：晚上 7:30 走Example Customer续费 + 增购合同报价清单流程。",
    title="TaskCenter 提醒",
    template="blue",
)

client.send_card(
    receive_id=target.receive_id,
    receive_id_type=target.receive_id_type,
    card=card,
)
```

### Markdown 转卡片

```python
from feishu_card_v2 import markdown_to_card_v2

markdown = """# 晚间收口\n\n- 已完成：...\n- 待确认：...\n"""
card = markdown_to_card_v2(markdown, template="green", split=True)
```

### 自定义接收者

```python
client.send_card(
    receive_id="oc_xxx",
    receive_id_type="chat_id",
    card=card,
)
```

### 命令行 smoke / 运维脚本

```bash
# 纯文本 → 简单卡片，仅预览不发送
python backend/scripts/sdk/feishu-card-v2/send_card_v2.py --text "提醒：测试" --dry-run

# Markdown → Card V2 → 发送给默认接收者
python backend/scripts/sdk/feishu-card-v2/send_card_v2.py --markdown report.md --template green --split

# 已有 Card JSON → 发送给指定群
python backend/scripts/sdk/feishu-card-v2/send_card_v2.py --card card.json --to oc_xxx --type chat_id
```

支持的 `receive_id_type`：

- `open_id`
- `user_id`
- `union_id`
- `email`
- `chat_id`

## 与 OpenClaw 链路的关系

更新后的分层建议：

| 场景 | 推荐链路 |
|---|---|
| 普通 TaskCenter 到点提醒 | TaskCenter dispatcher → Feishu Card SDK |
| 简单文本提醒 | `text_to_card_v2()` → Feishu Card SDK |
| 客户/合同/报价提醒 | 结构化 Markdown → `markdown_to_card_v2()` → Feishu Card SDK |
| 晚间收口 / 周报 / 巡检 | OpenClaw/Agent 生成内容 → Feishu Card SDK 发送 |
| 需要 AI 到点判断 | OpenClaw cron isolated agentTurn 负责判断，最终可调用/产出卡片投递 |
| 主会话唤醒 | OpenClaw `systemEvent`，不作为确定性通知主路径 |

也就是说：

- TaskCenter 负责：提醒事实、调度状态、投递状态。
- Feishu Card SDK 负责：最终飞书卡片呈现与发送。
- OpenClaw 负责：需要 AI 的内容生成、判断、上下文补充。

## 限制与校验

飞书卡片限制：

- `msg_type = interactive`
- `content` 为 card JSON 字符串
- Card V2 必须包含：`schema: "2.0"`
- 卡片消息体 ≤ 30KB
- V2 组件最多 200 个
- V2 客户端最低版本建议 >= 7.20

SDK 当前已做：

- Card JSON 2.0 构建
- Markdown 按 `---` 拆成多个 markdown 元素
- 自动提取首个 H1/H2 作为标题
- 30KB 发送前校验
- `receive_id_type` 白名单校验
- Feishu API 非 0 code 抛出异常

## 后续接入 dispatcher 时建议

建议后续新增独立 delivery 层，而不是把投递实现塞进 `tasks` 表：

```text
tasks
  业务任务本体

reminders
  用户语义上的提醒时间与提醒备注

reminder_deliveries / reminder_triggers
  记录投递方式、目标、状态、message_id、失败原因等
```

普通提醒默认：

```text
provider = feishu_card_v2
```

只有需要 AI 判断或定时总结时，再使用 OpenClaw cron / agent。
