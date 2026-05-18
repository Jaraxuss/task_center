"""Feishu Card JSON 1.0 builders for TaskCenter.

Card JSON 1.0 has no ``schema`` field.  Elements live directly at the root
``elements`` array, unlike Card JSON 2.0 where elements are nested under
``body.elements``.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any, Literal

HeaderTemplate = Literal[
    "blue",
    "wathet",
    "turquoise",
    "green",
    "yellow",
    "orange",
    "red",
    "carmine",
    "violet",
    "purple",
    "indigo",
    "grey",
    "default",
]
WidthMode = Literal["default", "compact", "fill"]

CARD_SIZE_LIMIT_BYTES = 30 * 1024
_HEADER_TEMPLATES = {
    "blue",
    "wathet",
    "turquoise",
    "green",
    "yellow",
    "orange",
    "red",
    "carmine",
    "violet",
    "purple",
    "indigo",
    "grey",
    "default",
}
_WIDTH_MODES = {"default", "compact", "fill"}


class FeishuCardV1Error(ValueError):
    """Base error for invalid Card JSON 1.0 payloads."""


class FeishuCardV1PayloadTooLarge(FeishuCardV1Error):
    """Raised when serialized card JSON exceeds Feishu's 30KB limit."""


@dataclass(frozen=True)
class CardSize:
    bytes: int
    limit_bytes: int = CARD_SIZE_LIMIT_BYTES

    @property
    def within_limit(self) -> bool:
        return self.bytes <= self.limit_bytes


def split_markdown_by_hr(text: str) -> list[str]:
    """Split Markdown by horizontal rules while preserving fenced code blocks."""

    lines = text.split("\n")
    blocks: list[str] = []
    in_code = False
    buf: list[str] = []

    for line in lines:
        if line.strip().startswith("```"):
            in_code = not in_code
            buf.append(line)
            continue
        if not in_code and re.match(r"^[ ]{0,3}(?:[-*_]){3,}\s*$", line.strip()):
            block = "\n".join(buf).strip()
            if block:
                blocks.append(block)
            buf = []
            continue
        buf.append(line)

    tail = "\n".join(buf).strip()
    if tail:
        blocks.append(tail)
    return blocks


def extract_first_heading(text: str) -> tuple[str | None, str]:
    """Extract first H1/H2 as card title and return remaining Markdown."""

    lines = text.strip().split("\n")
    title: str | None = None
    body: list[str] = []
    in_code = False

    for line in lines:
        if line.strip().startswith("```"):
            in_code = not in_code
        if title is None and not in_code and line.startswith("# "):
            title = line[2:].strip()
            continue
        if title is None and not in_code and line.startswith("## "):
            title = line[3:].strip()
            continue
        body.append(line)

    return title, "\n".join(body).strip()


def markdown_elements(text: str, *, split: bool = False) -> list[dict[str, Any]]:
    """Convert Markdown text into Card JSON 1.0 root elements."""

    cleaned = text.strip()
    if not cleaned:
        return [{"tag": "markdown", "content": " "}]

    if not split:
        return [{"tag": "markdown", "content": cleaned}]

    elements: list[dict[str, Any]] = []
    blocks = split_markdown_by_hr(cleaned)
    for index, block in enumerate(blocks):
        if index > 0:
            elements.append({"tag": "hr"})
        elements.append({"tag": "markdown", "content": block})
    return elements or markdown_elements(cleaned, split=False)


def build_card_v1(
    *,
    title: str | None = None,
    subtitle: str | None = None,
    elements: list[dict[str, Any]] | None = None,
    markdown: str | None = None,
    template: HeaderTemplate = "blue",
    width_mode: WidthMode = "default",
    enable_forward: bool = True,
    update_multi: bool = False,
    no_header: bool = False,
) -> dict[str, Any]:
    """Build a Feishu Card JSON 1.0 dict."""

    if template not in _HEADER_TEMPLATES:
        raise FeishuCardV1Error(f"Unsupported Feishu header template: {template}")
    if width_mode not in _WIDTH_MODES:
        raise FeishuCardV1Error(f"Unsupported Feishu width mode: {width_mode}")

    card: dict[str, Any] = {
        "config": {
            "enable_forward": enable_forward,
            "update_multi": update_multi,
            "width_mode": width_mode,
        },
        "elements": elements if elements is not None else markdown_elements(markdown or ""),
    }

    if not no_header and title:
        header: dict[str, Any] = {
            "title": {"tag": "plain_text", "content": title},
            "template": template,
        }
        if subtitle:
            header["subtitle"] = {"tag": "plain_text", "content": subtitle}
        card["header"] = header

    ensure_card_within_size_limit(card)
    return card


def markdown_to_card_v1(
    text: str,
    *,
    title: str | None = None,
    subtitle: str | None = None,
    template: HeaderTemplate = "blue",
    width_mode: WidthMode = "default",
    split: bool = False,
    no_header: bool = False,
) -> dict[str, Any]:
    """Convert Markdown text to a Feishu Card JSON 1.0 dict."""

    if not text.strip():
        raise FeishuCardV1Error("Markdown input is empty")

    body_text = text.strip()
    resolved_title = title
    if resolved_title is None and not no_header:
        resolved_title, body_text = extract_first_heading(body_text)

    return build_card_v1(
        title=resolved_title,
        subtitle=subtitle,
        elements=markdown_elements(body_text, split=split),
        template=template,
        width_mode=width_mode,
        no_header=no_header,
    )


def text_to_card_v1(
    text: str,
    *,
    title: str = "TaskCenter 提醒",
    subtitle: str | None = None,
    template: HeaderTemplate = "blue",
    width_mode: WidthMode = "default",
) -> dict[str, Any]:
    """Build a simple Card JSON 1.0 reminder card from plain text."""

    if not text.strip():
        raise FeishuCardV1Error("Text input is empty")
    return build_card_v1(
        title=title,
        subtitle=subtitle,
        markdown=text.strip(),
        template=template,
        width_mode=width_mode,
    )


def serialized_card_size(card: dict[str, Any]) -> CardSize:
    payload = json.dumps(card, ensure_ascii=False, separators=(",", ":"))
    return CardSize(bytes=len(payload.encode("utf-8")))


def ensure_card_within_size_limit(card: dict[str, Any]) -> None:
    size = serialized_card_size(card)
    if not size.within_limit:
        raise FeishuCardV1PayloadTooLarge(
            f"Feishu card payload is {size.bytes} bytes, exceeds {size.limit_bytes} bytes"
        )
