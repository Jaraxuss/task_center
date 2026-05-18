# TaskCenter Feishu Card SDKs

TaskCenter 的飞书卡片 SDK 统一放在这里。V1 / V2 使用相同的工程骨架，方便后续接 dispatcher、reminder delivery、运维 smoke 和测试。

```text
backend/scripts/sdk/
├── README.md
├── feishu-card-v1/
│   ├── README.md
│   ├── send_card_v1.py
│   ├── examples/sample-card-v1.json
│   └── feishu_card_v1/
│       ├── __init__.py
│       ├── card.py
│       └── client.py
└── feishu-card-v2/
    ├── README.md
    ├── send_card_v2.py
    ├── examples/sample-card-v2.json
    └── feishu_card_v2/
        ├── __init__.py
        ├── card.py
        └── client.py
```

## 共同能力

- 文本 → 飞书卡片
- Markdown → 飞书卡片
- 原始卡片 JSON 直接发送
- 复用 TaskCenter 飞书凭证配置
- `tenant_access_token` 进程内缓存，提前刷新
- 发送前 30KB 大小校验
- 直接调用飞书开放平台 `im/v1/messages`，不依赖 `openclaw message send`

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

## Smoke 命令

```bash
# Card JSON 1.0
python backend/scripts/sdk/feishu-card-v1/send_card_v1.py --text "提醒：测试 V1" --dry-run

# Card JSON 2.0
python backend/scripts/sdk/feishu-card-v2/send_card_v2.py --text "提醒：测试 V2" --dry-run
```

## 兼容入口

为了不破坏已有调用，以下旧入口仍可用：

- `backend/scripts/send_feishu_card.py`：转发到 `feishu-card-v2/send_card_v2.py`
- `services.feishu_card`：re-export `feishu_card_v2`，保留原 Python import 路径

新代码建议优先显式选择版本：

- Card V1：`feishu_card_v1`
- Card V2：`feishu_card_v2`
