"""LLM 流式通道标记：reasoning / content 分片前缀。

openai_compat.stream_chat 会在 delta 前附加：
  \\x01T\\x01 — thinking/reasoning
  \\x01C\\x01 — 正文 content

答疑侧会拆分；画像等不展示思考过程的通路必须剥离，否则前端会渲染成 □。
"""

from __future__ import annotations

import re

THINK_MARK = "\x01T\x01"
CONTENT_MARK = "\x01C\x01"

_MARK_RE = re.compile(r"\x01[TC]\x01")


def peel_stream_chunk(chunk: str) -> tuple[str, str | None]:
    """返回 (kind, text)。kind 为 'think' | 'content' | None（无标记原文）。"""
    if not chunk:
        return "content", ""
    if chunk.startswith(THINK_MARK):
        return "think", chunk[len(THINK_MARK) :]
    if chunk.startswith(CONTENT_MARK):
        return "content", chunk[len(CONTENT_MARK) :]
    return "content", chunk


def strip_stream_markers(text: str) -> str:
    """去掉通道标记与残留 SOH，供入库/历史回放。"""
    if not text:
        return ""
    cleaned = _MARK_RE.sub("", text)
    return cleaned.replace("\x01", "")
