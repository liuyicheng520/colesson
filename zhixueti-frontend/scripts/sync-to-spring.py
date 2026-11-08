#!/usr/bin/env python3
"""Sync SPA dist into Spring Boot static dirs (src + target/classes).

Replaces scripts/sync-to-spring.mjs which crashes node (exit 127) during
recursive copy on this machine. Wired into package.json build script.
"""
import json
import shutil
import sys
from pathlib import Path

root = Path(__file__).resolve().parent.parent
dist = root / "dist"
if not (dist / "index.html").exists():
    print("[sync-spa] dist/index.html missing - run vite build first", file=sys.stderr)
    sys.exit(1)

index_html = (dist / "index.html").read_text(encoding="utf-8")
targets = [root.parent / "src/main/resources/static", root.parent / "target/classes/static"]

for dest in targets:
    dest.mkdir(parents=True, exist_ok=True)
    assets_dest = dest / "assets"
    if assets_dest.exists():
        shutil.rmtree(assets_dest)
    shutil.copytree(dist / "assets", assets_dest)
    (dest / "index.html").write_text(index_html, encoding="utf-8", newline="\n")
    (dest / "zhixueti-spa.html").write_text(index_html, encoding="utf-8", newline="\n")
    print("[sync-spa] synced ->", dest)

print("[sync-spa] done")
