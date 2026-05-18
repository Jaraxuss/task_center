# TaskCenter 飞书卡片 V1 SDK

> 目标：把 `/home/velen/velen/feishu-bot10` 中验证过的 Card JSON 1.0 文档和脚本，沉淀为 TaskCenter 内部可复用 SDK。它与 Card V2 SDK 同级，作为兼容路径存在。

## 代码位置

```text
backend/scripts/sdk/feishu-card-v1/
├── README.md
├── send_card_v1.py
├── examples/sample-card-v1.json
└── feishu_card_v1/
    ├── __init__.py
    ├── card.py
    └── client.py
```

## 支持能力

- `text_to_card_v1()`：纯文本包装成简单 Card JSON 1.0
- `markdown_to_card_v1()`：Markdown 转 Card JSON 1.0
- `build_card_v1()`：传入自定义 V1 elements 构建卡片
- `FeishuCardV1Client.send_card()`：通过飞书开放平台发送 interactive 消息
- token 进程内缓存，提前 300 秒刷新
- 发送前校验卡片 JSON 序列化后不超过 30KB
- `receive_id_type` 白名单校验：`open_id` / `user_id` / `union_id` / `email` / `chat_id`

## 凭证配置

沿用 TaskCenter 当前配置方式，优先使用：

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

## 基本用法

由于该 SDK 放在 `backend/scripts/sdk/feishu-card-v1` 下，直接在业务代码里使用时，需要确保该目录在 `PYTHONPATH` 中；CLI 已自动处理路径。

```python
from config import get_settings
from feishu_card_v1 import FeishuCardV1Client, FeishuTarget, markdown_to_card_v1

settings = get_settings()
client = FeishuCardV1Client.from_settings(settings)
target = FeishuTarget.from_settings(settings)

card = markdown_to_card_v1("# 晚间收口\n\n- 已完成：A\n---\n- 待确认：B", split=True)
client.send_card(
    receive_id=target.receive_id,
    receive_id_type=target.receive_id_type,
    card=card,
)
```

## CLI smoke / 运维脚本

```bash
# 纯文本 → Card V1，仅打印 JSON
python backend/scripts/sdk/feishu-card-v1/send_card_v1.py --text "提醒：测试" --dry-run

# Markdown → Card V1，仅打印 JSON
python backend/scripts/sdk/feishu-card-v1/send_card_v1.py --markdown report.md --template green --split --dry-run

# 已有 Card V1 JSON → 发送给指定接收者
python backend/scripts/sdk/feishu-card-v1/send_card_v1.py --card card-v1.json --to ou_xxx --type open_id
```

## V1 与 V2 的关键差异

| 项目 | Card JSON 1.0 | Card JSON 2.0 |
|---|---|---|
| schema | 无 `schema` 字段 | 必须 `schema: "2.0"` |
| 主体元素 | 根节点 `elements` | `body.elements` |
| 标题 | 根节点 `header` | 根节点 `header`，样式能力更强 |
| 默认共享更新 | `update_multi=false` | 通常 `update_multi=true` |
| 兼容组件 | 支持 `note` / V1 `action` 等 | V2 组件体系 |

## 使用建议

- TaskCenter 新提醒默认优先 Card V2。
- Card V1 SDK 作为兼容/迁移/历史模板复用路径。
- 不要在仓库中保存真实飞书 `app_secret` 或示例凭证。
