#!/usr/bin/env python3
"""Send Feishu Card JSON 1.0 through TaskCenter credentials.

Examples:
  python backend/scripts/sdk/feishu-card-v1/send_card_v1.py --text "提醒：测试" --dry-run
  python backend/scripts/sdk/feishu-card-v1/send_card_v1.py --markdown report.md --template green --split
  python backend/scripts/sdk/feishu-card-v1/send_card_v1.py --card card-v1.json --to oc_xxx --type chat_id
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SDK_DIR = Path(__file__).resolve().parent
BACKEND_DIR = SDK_DIR.parents[2]
for path in (SDK_DIR, BACKEND_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from config import get_settings  # noqa: E402
from feishu_card_v1 import (  # noqa: E402
    FeishuCardV1Client,
    FeishuTarget,
    markdown_to_card_v1,
    text_to_card_v1,
    validate_receive_id_type,
)


def _load_card(args: argparse.Namespace) -> dict:
    if args.card:
        return json.loads(Path(args.card).read_text(encoding="utf-8"))
    if args.markdown:
        markdown = Path(args.markdown).read_text(encoding="utf-8")
        return markdown_to_card_v1(
            markdown,
            title=args.title,
            subtitle=args.subtitle,
            template=args.template,
            width_mode=args.width,
            split=args.split,
            no_header=args.no_header,
        )
    if args.text:
        return text_to_card_v1(
            args.text,
            title=args.title or "TaskCenter 提醒",
            subtitle=args.subtitle,
            template=args.template,
            width_mode=args.width,
        )
    markdown = sys.stdin.read()
    if markdown.strip():
        return markdown_to_card_v1(
            markdown,
            title=args.title,
            subtitle=args.subtitle,
            template=args.template,
            width_mode=args.width,
            split=args.split,
            no_header=args.no_header,
        )
    raise SystemExit("No input. Use --text, --markdown, --card, or pipe Markdown via stdin.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Send Feishu Card JSON 1.0 via TaskCenter SDK")
    source = parser.add_mutually_exclusive_group()
    source.add_argument("--text", help="Plain text to wrap as a simple Card V1")
    source.add_argument("--markdown", help="Markdown file to convert to Card V1")
    source.add_argument("--card", help="Existing Card JSON 1.0 file")
    parser.add_argument("--to", help="Receive ID. Defaults to TASK_CENTER_FEISHU_DEFAULT_RECEIVE_ID")
    parser.add_argument(
        "--type",
        dest="receive_id_type",
        default=None,
        choices=["open_id", "user_id", "union_id", "email", "chat_id"],
        help="Receive ID type. Defaults to TASK_CENTER_FEISHU_DEFAULT_RECEIVE_ID_TYPE or open_id",
    )
    parser.add_argument("--title", help="Card title")
    parser.add_argument("--subtitle", help="Card subtitle")
    parser.add_argument(
        "--template",
        default="blue",
        choices=["blue", "wathet", "turquoise", "green", "yellow", "orange", "red", "carmine", "violet", "purple", "indigo", "grey", "default"],
        help="Header color template",
    )
    parser.add_argument("--width", default="default", choices=["default", "compact", "fill"], help="Card width mode")
    parser.add_argument("--split", action="store_true", help="Split Markdown on horizontal rules")
    parser.add_argument("--no-header", action="store_true", help="Do not generate a card header")
    parser.add_argument("--uuid", help="Feishu one-hour de-duplication UUID")
    parser.add_argument("--dry-run", action="store_true", help="Print card JSON without sending")
    args = parser.parse_args()

    card = _load_card(args)
    if args.dry_run:
        print(json.dumps(card, ensure_ascii=False, indent=2))
        return

    settings = get_settings()
    if args.to:
        receive_id = args.to
        receive_id_type = validate_receive_id_type(args.receive_id_type or settings.feishu_default_receive_id_type)
    else:
        target = FeishuTarget.from_settings(settings)
        receive_id = target.receive_id
        receive_id_type = args.receive_id_type or target.receive_id_type

    client = FeishuCardV1Client.from_settings(settings)
    result = client.send_card(receive_id=receive_id, receive_id_type=receive_id_type, card=card, uuid=args.uuid)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
