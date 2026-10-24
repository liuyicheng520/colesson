"""Avatar image processing — center crop, square, resize."""

from __future__ import annotations

import io
from typing import Literal

from PIL import Image, UnidentifiedImageError

AVATAR_SIZE = 256
MAX_SOURCE_BYTES = 2 * 1024 * 1024


def detect_image_format(data: bytes, filename: str = "", content_type: str | None = None) -> Literal["jpeg", "png"] | None:
    if len(data) >= 8 and data[:8] == b"\x89PNG\r\n\x1a\n":
        return "png"
    if len(data) >= 2 and data[:2] == b"\xff\xd8":
        return "jpeg"
    name = (filename or "").lower()
    if name.endswith(".png"):
        return "png"
    if name.endswith((".jpg", ".jpeg")):
        return "jpeg"
    if content_type in ("image/png",):
        return "png"
    if content_type in ("image/jpeg", "image/jpg"):
        return "jpeg"
    return None


def process_avatar(data: bytes, fmt: Literal["jpeg", "png"]) -> bytes:
    """Center-crop to square and resize to AVATAR_SIZE."""
    try:
        img = Image.open(io.BytesIO(data))
    except UnidentifiedImageError as exc:
        raise ValueError("无法识别的图片格式") from exc

    img = img.convert("RGBA") if fmt == "png" else img.convert("RGB")
    w, h = img.size
    side = min(w, h)
    left = (w - side) // 2
    top = (h - side) // 2
    img = img.crop((left, top, left + side, top + side))
    img = img.resize((AVATAR_SIZE, AVATAR_SIZE), Image.Resampling.LANCZOS)

    out = io.BytesIO()
    if fmt == "png":
        img.save(out, format="PNG", optimize=True)
    else:
        if img.mode == "RGBA":
            img = img.convert("RGB")
        img.save(out, format="JPEG", quality=88, optimize=True)
    return out.getvalue()
