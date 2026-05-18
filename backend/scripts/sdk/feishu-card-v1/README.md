# TaskCenter Feishu Card JSON 1.0 SDK

> 来源：`/home/velen/velen/feishu-bot10` 的飞书卡片 1.0 文档与脚本。现在沉淀为 TaskCenter 内部 SDK，与 `feishu-card-v2` 同级，用于兼容需要 Card JSON 1.0 的发送场景。

## 目录结构

```text
backend/scripts/sdk/feishu-card-v1/
├── README.md
├── send_card_v1.py              # CLI smoke/运维脚本
├── examples/
│   └── sample-card-v1.json
└── feishu_card_v1/
    ├── __init__.py
    ├── card.py                  # Card JSON 1.0 builder / Markdown 转卡片 / 30KB 校验
    └── client.py                # token 缓存 + im/v1/messages 发送
```

## 能力

- 文本 → Card JSON 1.0
- Markdown → Card JSON 1.0
- 原始 Card JSON 1.0 直接发送
- `tenant_access_token` 进程内缓存，提前 300 秒刷新
- 发送前 30KB 卡片大小校验
- 使用 TaskCenter 现有飞书凭证配置，不写死密钥
- 直接调用飞书开放平台 `im/v1/messages`，`msg_type=interactive`

## 凭证配置

优先使用 TaskCenter 命名：

```bash
TASK_CENTER_FEISHU_APP_ID=cli_xxx
TASK_CENTER_FEISHU_APP_SECRET=xxx
TASK_CENTER_FEISHU_DEFAULT_RECEIVE_ID=ou_xxx
TASK_CENTER_FEISHU_DEFAULT_RECEIVE_ID_TYPE=open_id
```

兼容已有脚本变量：

```bash
FEISHU_APP_ID=cli_xxx
FEISHU_APP_SECRET=xxx
```

> 不要把真实 `app_secret` 写入仓库。

## Python 调用

```python
from config import get_settings
from feishu_card_v1 import FeishuCardV1Client, FeishuTarget, text_to_card_v1

settings = get_settings()
client = FeishuCardV1Client.from_settings(settings)
target = FeishuTarget.from_settings(settings)

card = text_to_card_v1("提醒：测试 Card JSON 1.0", title="TaskCenter 提醒")
client.send_card(
    receive_id=target.receive_id,
    receive_id_type=target.receive_id_type,
    card=card,
)
```

## CLI smoke

```bash
# 纯文本 → Card V1，仅预览
python backend/scripts/sdk/feishu-card-v1/send_card_v1.py --text "提醒：测试" --dry-run

# Markdown → Card V1 → 发送给默认接收者
python backend/scripts/sdk/feishu-card-v1/send_card_v1.py --markdown report.md --template green --split

# 已有 Card JSON 1.0 → 指定群聊发送
python backend/scripts/sdk/feishu-card-v1/send_card_v1.py --card card-v1.json --to oc_xxx --type chat_id
```

## Card JSON 1.0 结构要点

- 不需要、也不应包含 `schema: "2.0"`
- 主体组件直接在根节点 `elements` 中
- 标题直接在根节点 `header` 中
- 支持 V1 的 `note`、`action` 等组件
- 发送 API 与 V2 一样：`im/v1/messages` + `msg_type=interactive` + 字符串化的 `content`

## 与 Card V2 SDK 的分工

默认新提醒优先使用 Card V2；Card V1 SDK 主要用于：

- 需要复用已有 Card JSON 1.0 模板的场景
- 客户端兼容性或组件能力必须走 V1 的场景
- 对比/回归飞书卡片表现时的兼容发送路径
