"""Tutor 上下文裁剪 — 防止 prompt 过长导致 LLM 超时。"""

from __future__ import annotations


def trim_text(text: str, max_len: int) -> str:
    if not text or len(text) <= max_len:
        return text or ""
    return text[:max_len] + "\n…(内容已精简)"


def trim_messages(messages: list[dict[str, str]], max_total: int = 14000) -> list[dict[str, str]]:
    """保留 system + 最近对话，总字符数不超过 max_total。"""
    if not messages:
        return messages
    system_msgs = [m for m in messages if m.get("role") == "system"]
    rest = [m for m in messages if m.get("role") != "system"]
    total = sum(len(m.get("content") or "") for m in messages)
    if total <= max_total:
        return messages
    # 先压缩 system
    out_system: list[dict[str, str]] = []
    for m in system_msgs:
        content = m.get("content") or ""
        if len(content) > 6000:
            content = trim_text(content, 6000)
        out_system.append({**m, "content": content})
    trimmed_rest = rest[-8:]
    while trimmed_rest:
        combined = out_system + trimmed_rest
        size = sum(len(m.get("content") or "") for m in combined)
        if size <= max_total:
            return combined
        if len(trimmed_rest) > 2:
            trimmed_rest = trimmed_rest[1:]
        else:
            last = trimmed_rest[-1]
            trimmed_rest = [{**last, "content": trim_text(last.get("content") or "", 2000)}]
            break
    return out_system + trimmed_rest
