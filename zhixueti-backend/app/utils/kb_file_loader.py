"""Load and chunk files from a local knowledge-base directory."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from app.utils.document_extractor import DocumentExtractError, extract_document

# 纯文本类课程语料（教材 rst、RFC sgml、代码源文件）按文本直接索引
PLAIN_TEXT_EXT = {".md", ".txt", ".rst", ".sgml", ".html", ".htm",
                  ".java", ".py", ".c", ".cpp", ".h", ".cs", ".js", ".ts", ".sql"}
DEFAULT_INCLUDE_EXT = PLAIN_TEXT_EXT | {".pdf", ".docx", ".pptx"}
DEFAULT_EXCLUDE_DIR = {
    ".git",
    ".claude",
    "__pycache__",
    "node_modules",
    ".venv",
    "venv",
}
DEFAULT_EXCLUDE_FILE_NAMES = {
    "Solution.cs",
    "Solution.py",
    "Solution.java",
    "Solution.js",
    "Solution.ts",
    "Solution.go",
    "Solution.rs",
    "Solution.kt",
    "Solution.swift",
    "Solution.php",
    "Solution.rb",
    "Solution.scala",
    "Solution.cpp",
    "Solution.c",
}
CHUNK_SIZE = 900
CHUNK_OVERLAP = 150
MAX_FILE_BYTES = 8 * 1024 * 1024


@dataclass
class KBFileChunk:
    chunk_id: str
    rel_path: str
    source_path: str
    filename: str
    chunk_index: int
    text: str
    file_hash: str
    mtime: float


def _file_signature(path: Path) -> str:
    stat = path.stat()
    raw = f"{path.resolve()}|{stat.st_mtime}|{stat.st_size}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _split_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    text = re.sub(r"\n{3,}", "\n\n", text.strip())
    if not text:
        return []
    if len(text) <= chunk_size:
        return [text]
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(len(text), start + chunk_size)
        piece = text[start:end].strip()
        if piece:
            chunks.append(piece)
        if end >= len(text):
            break
        start = max(end - overlap, start + 1)
    return chunks


def _read_text_file(path: Path) -> str:
    for enc in ("utf-8", "utf-8-sig", "gb18030", "gbk"):
        try:
            return path.read_text(encoding=enc)
        except UnicodeDecodeError:
            continue
    return path.read_text(encoding="utf-8", errors="ignore")


def extract_local_file(path: Path) -> str:
    ext = path.suffix.lower()
    if ext in PLAIN_TEXT_EXT:
        return _read_text_file(path)
    if ext in {".pdf", ".docx", ".pptx"}:
        data = path.read_bytes()
        if len(data) > MAX_FILE_BYTES:
            raise DocumentExtractError(f"文件过大: {path.name}")
        parsed = extract_document(path.name, data)
        return parsed["full_text"]
    raise DocumentExtractError(f"不支持的格式: {ext}")


def should_index_file(
    path: Path,
    *,
    include_ext: set[str] | None = None,
    exclude_dir_names: set[str] | None = None,
    exclude_file_names: set[str] | None = None,
) -> bool:
    include_ext = include_ext or DEFAULT_INCLUDE_EXT
    exclude_dir_names = exclude_dir_names or DEFAULT_EXCLUDE_DIR
    exclude_file_names = exclude_file_names or DEFAULT_EXCLUDE_FILE_NAMES
    if path.suffix.lower() not in include_ext:
        return False
    if path.name in exclude_file_names:
        return False
    for part in path.parts:
        if part in exclude_dir_names:
            return False
    return True


def iter_kb_files(
    root: Path,
    *,
    include_dirs: list[str] | None = None,
    include_ext: set[str] | None = None,
) -> list[Path]:
    if not root.is_dir():
        return []
    roots = [root]
    if include_dirs:
        roots = [root / d for d in include_dirs if (root / d).is_dir()]
    files: list[Path] = []
    for base in roots:
        for path in base.rglob("*"):
            if not path.is_file():
                continue
            if should_index_file(path, include_ext=include_ext):
                files.append(path)
    return sorted(files, key=lambda p: str(p).lower())


def file_to_chunks(path: Path, root: Path) -> list[KBFileChunk]:
    try:
        text = extract_local_file(path)
    except (DocumentExtractError, OSError):
        return []
    text = text.strip()
    if len(text) < 40:
        return []
    rel = str(path.relative_to(root)).replace("\\", "/")
    sig = _file_signature(path)
    stat = path.stat()
    chunks: list[KBFileChunk] = []
    for idx, piece in enumerate(_split_text(text)):
        chunk_id = hashlib.sha256(f"{rel}|{idx}|{sig}".encode()).hexdigest()
        chunks.append(
            KBFileChunk(
                chunk_id=chunk_id,
                rel_path=rel,
                source_path=str(path.resolve()),
                filename=path.name,
                chunk_index=idx,
                text=piece,
                file_hash=sig,
                mtime=stat.st_mtime,
            )
        )
    return chunks
