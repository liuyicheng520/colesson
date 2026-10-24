"""Repair orphan document resources missing res_document rows."""
from __future__ import annotations

import json

from sqlalchemy import text
from app.db.session import SessionLocal
from app.models.resource import ResDocument, ResResource


def extract_content_md(output_data) -> str:
    if not output_data:
        return ""
    if isinstance(output_data, str):
        try:
            output_data = json.loads(output_data)
        except json.JSONDecodeError:
            return output_data if len(output_data) > 50 else ""
    if isinstance(output_data, dict):
        md = output_data.get("content_md")
        if isinstance(md, str) and md.strip():
            return md
    return ""


def main() -> None:
    db = SessionLocal()
    orphans = db.execute(
        text(
            "select rr.id, rr.agent_task_id, rr.title "
            "from res_resource rr "
            "left join res_document rd on rd.resource_id=rr.id "
            "where rr.type_id=1 and rd.id is null and rr.deleted_at is null"
        )
    ).fetchall()
    print(f"orphans: {len(orphans)}")
    for rid, task_id, title in orphans:
        content = ""
        if task_id:
            rows = db.execute(
                text(
                    "select r.output_data from agt_agent_run r "
                    "join agt_agent_definition d on d.id=r.agent_id "
                    "where r.task_id=:tid and d.agent_code='document' "
                    "order by r.id desc limit 1"
                ),
                {"tid": task_id},
            ).fetchall()
            if rows:
                content = extract_content_md(rows[0][0])
        if not content:
            snap = db.execute(
                text(
                    "select content_snapshot from sec_content_audit "
                    "where target_type='resource' and target_id=:rid "
                    "order by id desc limit 1"
                ),
                {"rid": rid},
            ).fetchone()
            if snap and snap[0]:
                content = snap[0]
        if not content:
            res = db.query(ResResource).filter(ResResource.id == rid).first()
            content = (res.summary if res else "") or ""
        if not content.strip():
            print(f"skip {rid}: no content")
            continue
        chapters = content.count("\n## ")
        db.add(
            ResDocument(
                resource_id=rid,
                content_md=content,
                word_count=len(content),
                chapter_count=chapters,
            )
        )
        res = db.query(ResResource).filter(ResResource.id == rid).first()
        if res and res.status == 1:
            res.status = 2
        db.commit()
        print(f"repaired {rid} ({title}): {len(content)} chars, chapters={chapters}")
    db.close()


if __name__ == "__main__":
    main()
