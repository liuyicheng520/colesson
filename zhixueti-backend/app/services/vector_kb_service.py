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
        # 词法检索索引（bigram BM25），惰性构建，reindex 后置空
        self._bm25: dict[str, Any] | None = None
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
            # 检索策略展示：便于管理端与评审确认当前生效的融合方式
            "retrieval": {
                "mode": "hybrid",
                "vector": "cosine (ChromaDB)",
                "lexical": "bigram BM25" if self._bm25 is not None else "bigram BM25 (lazy)",
                "fusion": "RRF (k=60)",
                "quality_weighted": True,
                "quality_tiers": ["官方标准 100", "官方参考 95", "内核文档 90", "学术开放教材 85", "许可声明 30（不参与召回）"],
            },
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
        # 语料变化后词法索引必须重建
        self._bm25 = None
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
        # 候选池按 k 的 4 倍取，为融合与重排留出空间
        pool = max(k * 4, 20)
        try:
            qvec = await self.embedder.embed_query(query)
            result = col.query(query_embeddings=[qvec], n_results=min(pool, max(col.count(), 1)))
        except Exception as exc:
            logger.warning("vector kb search failed: %s", exc)
            return "", []

        docs = (result.get("documents") or [[]])[0]
        metas = (result.get("metadatas") or [[]])[0]
        dists = (result.get("distances") or [[]])[0]
        ids = (result.get("ids") or [[]])[0]

        # 阈值自适应：语义模型分高、hash 兜底分低，用过低的阈值避免误过滤
        min_score = float(self.settings.kb_min_score or 0.05)

        # ── 候选合并：向量召回 + 词法召回，各自记录排名后做 RRF 融合 ──
        cand: dict[str, dict[str, Any]] = {}
        for rank, (doc, meta, dist, cid) in enumerate(zip(docs, metas, dists, ids)):
            if not doc or not meta:
                continue
            vscore = 1.0 - float(dist)
            if vscore < min_score:
                continue
            cand[cid] = {"doc": doc, "meta": meta, "vscore": vscore, "vrank": rank, "lscore": 0.0, "lrank": None}

        lexical = self._bm25_top(query, limit=max(pool, 30))
        for rank, (cid, lscore, doc, meta) in enumerate(lexical):
            if cid in cand:
                cand[cid]["lscore"] = lscore
                cand[cid]["lrank"] = rank
            elif doc and meta:
                cand[cid] = {"doc": doc, "meta": meta, "vscore": None, "vrank": None, "lscore": lscore, "lrank": rank}

        if not cand:
            return "", []

        # ── 加权 RRF 融合 + 来源质量加权 ──
        # 词法贡献按其相对强度缩放（强匹配才主导），避免弱向量在等权融合下抢位；
        # 词法权重 1.6 略高于向量，因 BM25 在术语精确匹配上更可靠。
        rrf_k = 60.0
        max_lex = max((i["lscore"] or 0.0 for i in cand.values()), default=0.0) or 1.0
        for item in cand.values():
            fused = 0.0
            if item["vrank"] is not None:
                fused += 1.0 / (rrf_k + item["vrank"] + 1)
            if item["lrank"] is not None:
                strength = (item["lscore"] or 0.0) / max_lex
                fused += 1.6 * strength * (1.0 / (rrf_k + item["lrank"] + 1))
            quality, tier = self._quality_of(item["meta"])
            item["quality"] = quality
            item["tier"] = tier
            item["fused"] = fused * (0.85 + 0.3 * quality / 100.0)

        # 许可声明等非教学语料（质量 < 40）不进入召回结果
        recallable = [c for c in cand.values() if c["quality"] >= 40]
        ranked = sorted(recallable, key=lambda x: x["fused"], reverse=True)[:k]
        top_fused = ranked[0]["fused"] if ranked else 1.0

        chunks: list[str] = []
        citations: list[dict] = []
        for item in ranked:
            rel = item["meta"].get("rel_path") or item["meta"].get("filename") or "未知来源"
            doc = item["doc"]
            chunks.append(f"[{rel}]\n{doc[:1800]}")
            citations.append(
                {
                    "doc_id": rel,
                    "filename": item["meta"].get("filename") or rel,
                    "page": int(item["meta"].get("chunk_index") or 0) + 1,
                    "snippet": doc[:220],
                    "score": round(item["fused"] / top_fused, 3) if top_fused else 0.0,
                    "vector_score": round(item["vscore"], 3) if item["vscore"] is not None else None,
                    "lexical_score": round(item["lscore"], 3) if item["lscore"] else None,
                    "source_quality": item["quality"],
                    "quality_tier": item["tier"],
                    "source": "vector_kb",
                }
            )

        ctx = "\n\n---\n\n".join(chunks)[:12000]
        return ctx, citations

    # ── 来源质量分级 ───────────────────────────────────────
    @staticmethod
    def _quality_of(meta: dict[str, Any]) -> tuple[int, str]:
        """按语料来源判定质量分：官方标准 100 / 官方参考实现 95 / 内核文档 90 /
        学术开放教材 85 / 许可声明 30（低于召回下限，不参与内容召回）。
        权重只做温和修正（0.85~1.15），不覆盖语义排序。"""
        rel = str(meta.get("rel_path") or meta.get("filename") or "").lower()
        name = rel.rsplit("/", 1)[-1]
        # 许可声明优先判定：避免 openjdk-gpl-2.0-license 被误判为官方参考实现
        if rel.startswith("licenses/") or "license" in name or "copying" in name:
            return 30, "许可声明"
        if "rfc" in name:
            return 100, "官方标准"
        if name.startswith("openjdk-") or name.startswith("postgresql-"):
            return 95, "官方参考"
        if rel.startswith("operating_system/") or "linux-" in name:
            return 90, "内核文档"
        if "opendsa" in name:
            return 85, "学术开放教材"
        return 70, "其他来源"

    # 跨语言术语扩展：语料含大量英文标准文档，中文提问需补英文同义术语才能召回。
    # 仅覆盖本知识库实际收录的学科方向，避免引入噪声。
    TERM_EXPANSION = {
        "虚拟内存": "virtual memory",
        "页表": "page table",
        "内存分配": "memory allocation",
        "内存管理": "memory management",
        "进程调度": "scheduler scheduling",
        "调度器": "scheduler",
        "文件系统": "filesystem vfs",
        "索引": "index",
        "事务": "transaction",
        "隔离级别": "isolation level",
        "并发控制": "concurrency mvcc",
        "查询优化": "query optimization",
        "二叉树": "binary tree",
        "二叉搜索树": "binary search tree",
        "哈希": "hash",
        "散列": "hash",
        "栈": "stack",
        "队列": "queue",
        "链表": "list linked",
        "图": "graph",
        "三次握手": "three-way handshake",
        "四次挥手": "connection termination",
        "拥塞控制": "congestion control",
        "流量控制": "flow control",
        "重传": "retransmission",
        "连接建立": "connection establishment",
        "线程": "thread",
        "互斥锁": "mutex lock",
        "死锁": "deadlock",
        "缓存": "cache",
        "抽象类": "abstract class",
        "接口": "interface",
        "集合": "collection",
    }

    @classmethod
    def _expand_keywords(cls, text: str) -> str:
        """把命中的中文术语追加英文等价词，提升中英混合语料的召回。"""
        extra: list[str] = []
        for zh, en in cls.TERM_EXPANSION.items():
            if zh in text:
                extra.append(en)
        return f"{text} {' '.join(extra)}" if extra else text

    # ── 词法索引（bigram BM25，纯 Python，无额外依赖）────────
    @staticmethod
    def _tokenize(text: str) -> list[str]:
        """中文按二元组切分、英文按小写词切分，兼顾中文召回与术语匹配。"""
        import re

        tokens: list[str] = []
        for seg in re.findall(r"[\u4e00-\u9fff]+|[A-Za-z][A-Za-z0-9_.\-]*", text or ""):
            if seg[0].isascii():
                tokens.append(seg.lower())
            elif len(seg) == 1:
                tokens.append(seg)
            else:
                tokens.extend(seg[i : i + 2] for i in range(len(seg) - 1))
        return tokens

    def _build_bm25(self) -> None:
        """惰性构建全库 BM25 索引；reindex 后置空以重建。"""
        col = self._ensure_client()
        got = col.get(include=["documents", "metadatas"])
        ids = got.get("ids") or []
        docs = got.get("documents") or []
        metas = got.get("metadatas") or []

        from collections import Counter

        postings: list[Counter] = []
        lengths: list[int] = []
        df: Counter = Counter()
        store: list[tuple[str, str, dict]] = []
        for cid, doc, meta in zip(ids, docs, metas):
            tokens = self._tokenize(doc or "")
            lengths.append(len(tokens))
            tf = Counter(tokens)
            postings.append(tf)
            for term in tf:
                df[term] += 1
            store.append((cid, doc or "", meta or {}))

        n = len(store)
        avgdl = (sum(lengths) / n) if n else 0.0
        import math

        idf = {t: math.log((n - c + 0.5) / (c + 0.5) + 1.0) for t, c in df.items()}
        self._bm25 = {"store": store, "tf": postings, "len": lengths, "avgdl": avgdl, "idf": idf, "n": n}
        logger.info("bm25 index built: %d chunks", n)

    def _bm25_top(self, query: str, *, limit: int) -> list[tuple[str, float, str, dict]]:
        """返回 [(chunk_id, score, doc, meta)]，按分数降序。索引不可用时返回空。"""
        try:
            if getattr(self, "_bm25", None) is None:
                self._build_bm25()
            idx = self._bm25
            if not idx or not idx["n"]:
                return []
            q_terms = [t for t in self._tokenize(self._expand_keywords(query)) if t in idx["idf"]]
            if not q_terms:
                return []
            k1, b = 1.2, 0.75
            avgdl = idx["avgdl"] or 1.0
            scored: list[tuple[float, int]] = []
            for i, tf in enumerate(idx["tf"]):
                dl = idx["len"][i]
                s = 0.0
                for t in q_terms:
                    f = tf.get(t)
                    if not f:
                        continue
                    s += idx["idf"][t] * (f * (k1 + 1)) / (f + k1 * (1 - b + b * dl / avgdl))
                if s > 0:
                    scored.append((s, i))
            scored.sort(reverse=True)
            out = []
            for s, i in scored[:limit]:
                cid, doc, meta = idx["store"][i]
                out.append((cid, s, doc, meta))
            return out
        except Exception as exc:
            logger.warning("bm25 search skipped: %s", exc)
            return []

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
