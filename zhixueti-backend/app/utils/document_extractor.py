"""Lightweight document text extraction for tutor RAG (PDF/DOCX/PPTX)."""

from __future__ import annotations

import re
import uuid
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.etree import ElementTree

try:
    from pypdf import PdfReader
    from pypdf.errors import PdfReadError
except ImportError:  # pragma: no cover
    PdfReader = None  # type: ignore
    PdfReadError = Exception  # type: ignore


MAX_DOC_CHARS = 120_000
MAX_FILE_BYTES = 100 * 1024 * 1024  # 100MB
ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".pptx", ".ppt"}


class DocumentExtractError(ValueError):
    """用户可读的文档解析错误。"""


def _clean_text(text: str) -> str:
    text = re.sub(r"\s+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def _extract_docx(data: bytes) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    try:
        with zipfile.ZipFile(BytesIO(data)) as zf:
            xml = zf.read("word/document.xml")
    except (zipfile.BadZipFile, KeyError) as e:
        raise DocumentExtractError("Word 文件格式无效或已损坏") from e
    root = ElementTree.fromstring(xml)
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    paragraphs: list[str] = []
    for p in root.findall(".//w:p", ns):
        texts = [t.text for t in p.findall(".//w:t", ns) if t.text]
        if texts:
            paragraphs.append("".join(texts))
    full = "\n".join(paragraphs)
    chunk_size = 3000
    for i in range(0, max(len(full), 1), chunk_size):
        pages.append({"page": len(pages) + 1, "text": full[i : i + chunk_size]})
    if not pages:
        pages.append({"page": 1, "text": ""})
    return pages


def _extract_pptx(data: bytes) -> list[dict[str, Any]]:
    pages: list[dict[str, Any]] = []
    try:
        with zipfile.ZipFile(BytesIO(data)) as zf:
            slide_files = sorted(
                [n for n in zf.namelist() if n.startswith("ppt/slides/slide") and n.endswith(".xml")],
                key=lambda x: int(re.search(r"slide(\d+)", x).group(1)) if re.search(r"slide(\d+)", x) else 0,
            )
            ns = {"a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
            for idx, name in enumerate(slide_files, start=1):
                root = ElementTree.fromstring(zf.read(name))
                texts = [t.text for t in root.findall(".//a:t", ns) if t.text]
                pages.append({"page": idx, "text": "\n".join(texts)})
    except (zipfile.BadZipFile, KeyError) as e:
        raise DocumentExtractError("PPT 文件格式无效或已损坏") from e
    if not pages:
        pages.append({"page": 1, "text": ""})
    return pages


def _extract_pdf(data: bytes) -> list[dict[str, Any]]:
    if PdfReader is None:
        raise DocumentExtractError("PDF 解析依赖未安装，请联系管理员")
    try:
        reader = PdfReader(BytesIO(data))
        if reader.is_encrypted:
            try:
                reader.decrypt("")
            except Exception as e:
                raise DocumentExtractError("暂不支持加密 PDF，请上传未加密或已解密的 PDF") from e
        pages: list[dict[str, Any]] = []
        for i, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            pages.append({"page": i, "text": text})
    except PdfReadError as e:
        raise DocumentExtractError(f"PDF 文件无法读取：{e}") from e
    except DocumentExtractError:
        raise
    except Exception as e:
        raise DocumentExtractError(f"PDF 解析失败：{e}") from e

    if not pages:
        pages.append({"page": 1, "text": ""})

    total_chars = sum(len(p.get("text") or "") for p in pages)
    if total_chars < 30:
        raise DocumentExtractError(
            "暂不支持纯图片 PDF，请上传可复制文本的 PDF（或先将扫描件 OCR 后再上传）"
        )
    return pages


def extract_document(filename: str, data: bytes, session_no: str | None = None) -> dict[str, Any]:
    ext = Path(filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise DocumentExtractError("仅支持 PDF、Word(.docx/.doc)、PPT(.pptx/.ppt) 格式")
    if len(data) > MAX_FILE_BYTES:
        raise DocumentExtractError("单文件不能超过 100MB")

    if ext == ".pdf":
        pages = _extract_pdf(data)
    elif ext in (".docx", ".doc"):
        if ext == ".doc":
            raise DocumentExtractError("旧版 .doc 请另存为 .docx 后上传")
        pages = _extract_docx(data)
    else:
        pages = _extract_pptx(data)

    full_text = _clean_text("\n\n".join(f"【第{p['page']}页】\n{p['text']}" for p in pages))
    if len(full_text) > MAX_DOC_CHARS:
        full_text = full_text[:MAX_DOC_CHARS] + "\n…(内容已截断)"

    return {
        "doc_id": str(uuid.uuid4()),
        "filename": filename,
        "page_count": len(pages),
        "pages": pages,
        "full_text": full_text,
        "truncated": len(full_text) >= MAX_DOC_CHARS,
        "session_no": session_no,
    }
