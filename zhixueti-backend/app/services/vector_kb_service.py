"""Vector knowledge-base service — ChromaDB + local/API embeddings."""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.services.embedding_service import get_embedding_service
from app.utils.kb_file_loader import file_to_chunks, iter_kb_files

logger = logging.getLogger(__name__)

COLLECTION_NAME = "cs_knowledge_base"


class VectorKBService:
    def __init__(self) -> None:
        from app.core.config import get_settings

        self.settings = get_settings()
        self.embedder = get_embedding_service()
        self._client = None
        self._collection = None
        self.db_path = Path(self.settings.vector_db_path)
        self.manifest_path = self.db_path / "manifest.json"

    @property
    def enabled(self) -> bool:
        return bool(self.settings.kb_enabled and self.settings.local_kb_dir)

    def _kb_root(self) -> Path:
        return Path(self.settings.local_kb_dir).expanduser()

    def _include_dirs(self) -> list[str] | None:
        raw = (self.settings.kb_include_dirs or "").strip()
        if not raw:
            return None
        return [d.strip() for d in raw.split(",") if d.strip()]

    def _ensure_client(self):
        if self._client is not None:
            return self._collection
        import chromadb

        self.db_path.mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=str(self.db_path / "chroma"))
        self._collection = self._client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
        return self._collection

    def _load_manifest(self) -> dict[str, Any]:
        if not self.manifest_path.exists():
            return {"files": {}, "stats": {}, "updated_at": None}
        try:
            return json.loads(self.manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return {"files": {}, "stats": {}, "updated_at": None}

    def _save_manifest(self, manifest: dict[str, Any]) -> None:
        self.db_path.mkdir(parents=True, exist_ok=True)
        manifest["updated_at"] = datetime.now(timezone.utc).isoformat()
        self.manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    def status(self) -> dict[str, Any]:
        root = self._kb_root()
        manifest = self._load_manifest()
        count = 0
        if self.enabled:
            try:
                col = self._ensure_client()
                count = col.count()
            except Exception as exc:
                logger.warning("vector kb status error: %s", exc)
        return {
            "enabled": self.enabled,
            "kb_dir": str(root) if root.exists() else self.settings.local_kb_dir,
            "kb_dir_exists": root.exists(),
            "include_dirs": self._include_dirs() or ["(全部子目录)"],
            "vector_db_path": str(self.db_path),
            "chunk_count": count,
            "indexed_files": len(manifest.get("files") or {}),
            "last_indexed_at": manifest.get("updated_at"),
            "stats": manifest.get("stats") or {},
        }

    async def reindex(self, *, force: bool = False) -> dict[str, Any]:
        if not self.enabled:
            raise ValueError("知识库未启用，请配置 LOCAL_KB_DIR 与 KB_ENABLED=true")

        root = self._kb_root()
        if not root.is_dir():
            raise FileNotFoundError(f"知识库目录不存在: {root}")

        col = self._ensure_client()
        manifest = self._load_manifest()
        file_map: dict[str, str] = dict(manifest.get("files") or {})

        all_files = iter_kb_files(root, include_dirs=self._include_dirs())
        max_files = int(self.settings.kb_max_files or 0)
        full_scan = max_files <= 0
        if max_files > 0:
            all_files = all_files[:max_files]

        to_index: list[Path] = []
        stale_relpaths: set[str] = set(file_map.keys()) if full_scan else set()
        for path in all_files:
            rel = str(path.relative_to(root)).replace("\\", "/")
            if full_scan:
                stale_relpaths.discard(rel)
            sig = self._file_signature(path)
            if force or file_map.get(rel) != sig:
                to_index.append(path)

        if force:
            # ChromaDB >=1.x 不再接受 delete(where={})：改为按主键清空，兼容新旧版本
            try:
                existing = col.get(include=[])
                ids = existing.get("ids") or []
                if ids:
                    col.delete(ids=ids)
            except Exception:
                # 极端情况下回退为重建集合
                self._client.delete_collection(COLLECTION_NAME)
                col = self._ensure_client()
            file_map = {}
            stale_relpaths = set()

        # 仅在全量扫描时清理已删除文件，避免分批索引误删
        if full_scan:
            for rel in stale_relpaths:
                col.delete(where={"rel_path": rel})
                file_map.pop(rel, None)

        indexed_files = 0
        indexed_chunks = 0
        skipped_files = len(all_files) - len(to_index)
        batch_size = 32

        for path in to_index:
            rel = str(path.relative_to(root)).replace("\\", "/")
            chunks = file_to_chunks(path, root)
            if not chunks:
                continue

            col.delete(where={"rel_path": rel})
            ids = [c.chunk_id for c in chunks]
            docs = [c.text for c in chunks]
            metas = [
                {
                    "rel_path": c.rel_path,
                    "filename": c.filename,
                    "chunk_index": c.chunk_index,
                    "source_path": c.source_path,
                }
                for c in chunks
            ]

            for i in range(0, len(docs), batch_size):
                part_docs = docs[i : i + batch_size]
                part_ids = ids[i : i + batch_size]
                part_metas = metas[i : i + batch_size]
                vectors = await self.embedder.embed_texts(part_docs)
                col.add(ids=part_ids, documents=part_docs, metadatas=part_metas, embeddings=vectors)

            file_map[rel] = self._file_signature(path)
            indexed_files += 1
            indexed_chunks += len(chunks)
            if indexed_files % 50 == 0:
                manifest["files"] = file_map
                manifest["stats"] = {
                    "total_files_scanned": len(all_files),
                    "indexed_files": indexed_files,
                    "indexed_chunks": indexed_chunks,
                    "skipped_unchanged_files": skipped_files,
                    "removed_files": len(stale_relpaths),
                    "in_progress": True,
                }
                self._save_manifest(manifest)
                logger.info("KB index progress: %d files, %d chunks", indexed_files, indexed_chunks)

        stats = {
            "total_files_scanned": len(all_files),
            "indexed_files": indexed_files,
            "indexed_chunks": indexed_chunks,
            "skipped_unchanged_files": skipped_files,
            "removed_files": len(stale_relpaths),
        }
        manifest["files"] = file_map
        manifest["stats"] = stats
        self._save_manifest(manifest)
        return {**self.status(), "reindex": stats}

    @staticmethod
    def _file_signature(path: Path) -> str:
        stat = path.stat()
        return f"{stat.st_mtime:.0f}:{stat.st_size}"

    async def search(self, query: str, *, top_k: int | None = None) -> tuple[str, list[dict]]:
        if not self.enabled or not query.strip():
            return "", []

        try:
            col = self._ensure_client()
            if col.count() == 0:
                return "", []
        except Exception as exc:
            logger.warning("vector kb search init failed: %s", exc)
            return "", []

        k = top_k or int(self.settings.kb_top_k or 6)
        try:
            qvec = await self.embedder.embed_query(query)
            result = col.query(query_embeddings=[qvec], n_results=min(k, max(col.count(), 1)))
        except Exception as exc:
            logger.warning("vector kb search failed: %s", exc)
            return "", []

        docs = (result.get("documents") or [[]])[0]
        metas = (result.get("metadatas") or [[]])[0]
        dists = (result.get("distances") or [[]])[0]

        chunks: list[str] = []
        citations: list[dict] = []
        # 语义模型（bge/qwen）分数分布较高，hash 兜底向量整体偏低；
        # 阈值自适应，避免把正确命中全部过滤成"检索不到"。
        configured = float(self.settings.kb_min_score or 0.05)
        min_score = configured

        for doc, meta, dist in zip(docs, metas, dists):
            if not doc or not meta:
                continue
            score = 1.0 - float(dist)
            if score < min_score:
                continue
            rel = meta.get("rel_path") or meta.get("filename") or "未知来源"
            label = f"[{rel}]"
            chunks.append(f"{label}\n{doc[:1800]}")
            citations.append(
                {
                    "doc_id": rel,
                    "filename": meta.get("filename") or rel,
                    "page": int(meta.get("chunk_index") or 0) + 1,
                    "snippet": doc[:220],
                    "score": round(score, 3),
                    "source": "vector_kb",
                }
            )

        ctx = "\n\n---\n\n".join(chunks)[:12000]
        return ctx, citations

    def search_sync(self, query: str, *, top_k: int | None = None) -> tuple[str, list[dict]]:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(self.search(query, top_k=top_k))
        if loop.is_running():
            import concurrent.futures

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                future = pool.submit(asyncio.run, self.search(query, top_k=top_k))
                return future.result()
        return loop.run_until_complete(self.search(query, top_k=top_k))


_kb_singleton: VectorKBService | None = None


def get_vector_kb_service() -> VectorKBService:
    global _kb_singleton
    if _kb_singleton is None:
        _kb_singleton = VectorKBService()
    return _kb_singleton
