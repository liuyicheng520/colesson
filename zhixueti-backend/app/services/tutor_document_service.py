"""Tutor document upload — 按 user_id + session_no 隔离。"""

from __future__ import annotations

import json
from pathlib import Path

from app.core.exceptions import NotFoundException, ValidationException
from app.utils.document_extractor import DocumentExtractError, extract_document


class TutorDocumentService:
    def __init__(self) -> None:
        from app.core.config import get_settings

        self.settings = get_settings()
        self.base_dir = Path(self.settings.upload_dir) / "tutor_docs"

    def _user_dir(self, user_id: int) -> Path:
        d = self.base_dir / str(user_id)
        d.mkdir(parents=True, exist_ok=True)
        return d

    def _doc_path(self, user_id: int, doc_id: str) -> Path:
        return self._user_dir(user_id) / f"{doc_id}.json"

    def upload(self, user_id: int, session_no: str, filename: str, data: bytes) -> dict:
        if not session_no:
            raise ValidationException("必须指定会话后再上传文档")
        try:
            parsed = extract_document(filename, data, session_no=session_no)
        except DocumentExtractError as e:
            raise ValidationException(str(e)) from e
        except Exception as e:
            raise ValidationException(f"文档解析失败：{e}") from e

        doc_id = parsed["doc_id"]
        record = {
            "doc_id": doc_id,
            "user_id": user_id,
            "session_no": session_no,
            "filename": parsed["filename"],
            "page_count": parsed["page_count"],
            "pages": parsed["pages"],
            "full_text": parsed["full_text"],
            "truncated": parsed.get("truncated", False),
            "uploaded_at": __import__("datetime").datetime.now().isoformat(timespec="seconds"),
        }
        try:
            from app.db.session import SessionLocal
            from app.services.config_service import ConfigService

            with SessionLocal() as db:
                cfg = ConfigService(db)
                record["audit_status"] = 0 if cfg.document_audit_enabled() else 1
        except Exception:
            record["audit_status"] = 1
        self._doc_path(user_id, doc_id).write_text(
            json.dumps(record, ensure_ascii=False), encoding="utf-8"
        )
        return {
            "doc_id": doc_id,
            "filename": record["filename"],
            "page_count": record["page_count"],
            "truncated": record["truncated"],
            "preview": record["full_text"][:300],
            "session_no": session_no,
        }

    def get(self, user_id: int, doc_id: str, session_no: str | None = None) -> dict:
        path = self._doc_path(user_id, doc_id)
        if not path.exists():
            raise NotFoundException(message="文档不存在或无权访问")
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("user_id") != user_id:
            raise NotFoundException(message="文档不存在或无权访问")
        if session_no and record.get("session_no") != session_no:
            raise NotFoundException(message="文档不属于当前会话")
        return record

    def list_session_docs(self, user_id: int, session_no: str, doc_ids: list[str] | None = None) -> list[dict]:
        """仅返回当前会话绑定的文档列表。"""
        if not doc_ids:
            return []
        items: list[dict] = []
        for doc_id in doc_ids:
            try:
                rec = self.get(user_id, doc_id, session_no)
                items.append(
                    {
                        "doc_id": rec["doc_id"],
                        "filename": rec["filename"],
                        "page_count": rec["page_count"],
                        "preview": rec["full_text"][:120],
                        "session_no": rec.get("session_no"),
                    }
                )
            except NotFoundException:
                continue
        return items

    def delete(self, user_id: int, session_no: str, doc_id: str) -> None:
        self.get(user_id, doc_id, session_no)
        path = self._doc_path(user_id, doc_id)
        if path.exists():
            path.unlink()

    def build_rag_context(self, user_id: int, session_no: str, doc_ids: list[str], query: str) -> tuple[str, list[dict]]:
        if not doc_ids:
            return "", []
        citations: list[dict] = []
        chunks: list[str] = []
        query_terms = [t for t in query.replace("，", " ").split() if len(t) >= 2][:8]

        for doc_id in doc_ids[:5]:
            try:
                doc = self.get(user_id, doc_id, session_no)
            except NotFoundException:
                continue
            if doc.get("audit_status", 1) != 1:
                continue
            for page in doc.get("pages") or []:
                text = page.get("text") or ""
                if not text.strip():
                    continue
                score = sum(1 for t in query_terms if t in text)
                if score > 0 or not query_terms:
                    citations.append(
                        {
                            "doc_id": doc_id,
                            "filename": doc["filename"],
                            "page": page.get("page", 1),
                            "snippet": text[:200],
                        }
                    )
                    chunks.append(f"[{doc['filename']} 第{page.get('page', 1)}页]\n{text[:1500]}")
                if len(chunks) >= 6:
                    break

        if not chunks and doc_ids:
            try:
                doc = self.get(user_id, doc_ids[0], session_no)
                chunks.append(doc["full_text"][:4000])
                citations.append(
                    {
                        "doc_id": doc_ids[0],
                        "filename": doc["filename"],
                        "page": 1,
                        "snippet": doc["full_text"][:200],
                    }
                )
            except NotFoundException:
                pass

        return "\n\n---\n\n".join(chunks)[:12000], citations
