"""Feishu Card JSON 2.0 builders used by TaskCenter.

This module is intentionally dependency-free.  It produces plain dicts that can
be passed to :mod:`services.feishu_card.client` or tested directly.
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


class FeishuCardError(ValueError):
    """Base error for invalid card payloads."""


class FeishuCardPayloadTooLarge(FeishuCardError):
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
    """Extract first H1/H2 heading as title and return remaining Markdown."""

    match = re.match(r"^#{1,2}\s+(.+?)(?:\n|$)", text.strip())
    if not match:
        return None, text
    title = match.group(1).strip()
    body = text.strip()[match.end() :].strip()
    return title, body


def markdown_elements(text: str, *, split: bool = False, start_id: int = 0) -> list[dict[str, Any]]:
    """Convert Markdown text into Feishu Card V2 body elements."""

    cleaned = text.strip()
    if not cleaned:
        return [{"tag": "markdown", "content": " ", "element_id": f"md_{start_id}", "margin": "0px"}]

    if not split:
        return [
            {
                "tag": "markdown",
                "content": cleaned,
                "text_align": "left",
                "element_id": f"md_{start_id}",
                "margin": "0px 0px 0px 0px",
            }
        ]

    elements: list[dict[str, Any]] = []
    for index, block in enumerate(split_markdown_by_hr(cleaned)):
        if index > 0:
            elements.append({"tag": "hr", "margin": "2px 0px 2px 0px"})
        elements.append(
            {
                "tag": "markdown",
                "content": block,
                "text_align": "left",
                "element_id": f"md_{start_id + index}",
                "margin": "4px 0px 4px 0px",
            }
        )
    return elements or markdown_elements(cleaned, split=False, start_id=start_id)


def build_card_v2(
    *,
    title: str | None = None,
    subtitle: str | None = None,
    elements: list[dict[str, Any]] | None = None,
    markdown: str | None = None,
    template: HeaderTemplate = "blue",
    width_mode: WidthMode = "fill",
    summary: str | None = None,
    enable_forward: bool = True,
    no_header: bool = False,
) -> dict[str, Any]:
    """Build a Feishu Card JSON 2.0 dict.

    Either ``elements`` or ``markdown`` can be supplied.  If both are omitted,
    an empty markdown element is generated so Feishu receives a valid card.
    """

    if template not in _HEADER_TEMPLATES:
        raise FeishuCardError(f"Unsupported Feishu header template: {template}")
    if width_mode not in _WIDTH_MODES:
        raise FeishuCardError(f"Unsupported Feishu width mode: {width_mode}")

    body_elements = elements if elements is not None else markdown_elements(markdown or "")
    config: dict[str, Any] = {
        "update_multi": True,
        "width_mode": width_mode,
        "enable_forward": enable_forward,
    }
    if summary:
        config["summary"] = {"content": summary}

    card: dict[str, Any] = {
        "schema": "2.0",
        "config": config,
        "body": {
            "direction": "vertical",
            "padding": "12px 12px 12px 12px",
            "horizontal_spacing": "8px",
            "vertical_spacing": "4px",
            "elements": body_elements,
        },
    }

    if not no_header and title:
        header: dict[str, Any] = {
            "title": {"tag": "plain_text", "content": title},
            "template": template,
            "padding": "12px 12px 12px 12px",
        }
        if subtitle:
            header["subtitle"] = {"tag": "plain_text", "content": subtitle}
        card["header"] = header

    ensure_card_within_size_limit(card)
    return card


def markdown_to_card_v2(
    text: str,
    *,
    title: str | None = None,
    subtitle: str | None = None,
    template: HeaderTemplate = "blue",
    width_mode: WidthMode = "fill",
    split: bool = False,
    no_header: bool = False,
    summary: str | None = None,
) -> dict[str, Any]:
    """Convert Markdown text to a Feishu Card JSON 2.0 dict."""

    if not text.strip():
        raise FeishuCardError("Markdown input is empty")

    body_text = text.strip()
    resolved_title = title
    if resolved_title is None and not no_header:
        resolved_title, body_text = extract_first_heading(body_text)

    return build_card_v2(
        title=resolved_title,
        subtitle=subtitle,
        elements=markdown_elements(body_text, split=split),
        template=template,
        width_mode=width_mode,
        summary=summary,
        no_header=no_header,
    )


def text_to_card_v2(
    text: str,
    *,
    title: str = "提醒",
    subtitle: str | None = None,
    template: HeaderTemplate = "blue",
    width_mode: WidthMode = "fill",
    summary: str | None = None,
) -> dict[str, Any]:
    """Build a simple text reminder card from plain text."""

    return build_card_v2(
        title=title,
        subtitle=subtitle,
        markdown=text,
        template=template,
        width_mode=width_mode,
        summary=summary or text[:80],
    )


def serialized_card_size(card: dict[str, Any]) -> CardSize:
    payload = json.dumps(card, ensure_ascii=False, separators=(",", ":"))
    return CardSize(bytes=len(payload.encode("utf-8")))


def ensure_card_within_size_limit(card: dict[str, Any]) -> None:
    size = serialized_card_size(card)
    if not size.within_limit:
        raise FeishuCardPayloadTooLarge(
            f"Feishu card payload is {size.bytes} bytes, exceeds {size.limit_bytes} bytes"
        )
