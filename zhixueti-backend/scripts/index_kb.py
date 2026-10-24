"""CLI: build vector index for local knowledge base."""

from __future__ import annotations

import asyncio
import sys


async def main() -> int:
    from app.services.vector_kb_service import get_vector_kb_service

    force = "--force" in sys.argv
    svc = get_vector_kb_service()
    print("KB status:", svc.status())
    result = await svc.reindex(force=force)
    print("Reindex done:", result.get("reindex"))
    print("Final status:", {k: result[k] for k in ("chunk_count", "indexed_files", "last_indexed_at") if k in result})
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
