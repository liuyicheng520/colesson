"""Apply sys_user profile field migration."""

from sqlalchemy import text

from app.db.session import engine

STATEMENTS = [
    "ALTER TABLE sys_user ADD COLUMN real_name VARCHAR(32) NULL AFTER nickname",
    "ALTER TABLE sys_user ADD COLUMN student_no VARCHAR(32) NULL AFTER phone",
    "ALTER TABLE sys_user ADD COLUMN bio VARCHAR(50) NULL AFTER major",
    "ALTER TABLE sys_user ADD UNIQUE KEY uk_sys_user_student_no (student_no)",
]


def main() -> None:
    with engine.connect() as conn:
        for sql in STATEMENTS:
            try:
                conn.execute(text(sql))
                conn.commit()
                print(f"OK: {sql}")
            except Exception as exc:
                msg = str(exc)
                if "1060" in msg or "Duplicate column" in msg or "1061" in msg or "Duplicate key" in msg:
                    print(f"SKIP: {sql[:60]}...")
                else:
                    raise


if __name__ == "__main__":
    main()
