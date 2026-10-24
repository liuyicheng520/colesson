"""System config repository."""

from sqlalchemy.orm import Session

from app.models.sys import SysConfig


class ConfigRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get(self, key: str) -> SysConfig | None:
        return self.db.query(SysConfig).filter(SysConfig.config_key == key).first()

    def list_all(self) -> list[SysConfig]:
        return self.db.query(SysConfig).order_by(SysConfig.config_key).all()

    def upsert(
        self,
        key: str,
        value: str,
        *,
        config_type: str = "string",
        description: str | None = None,
        is_encrypted: bool = False,
    ) -> SysConfig:
        row = self.get(key)
        if row:
            row.config_value = value
            if description is not None:
                row.description = description
            row.config_type = config_type
            row.is_encrypted = 1 if is_encrypted else 0
        else:
            row = SysConfig(
                config_key=key,
                config_value=value,
                config_type=config_type,
                description=description,
                is_encrypted=1 if is_encrypted else 0,
            )
            self.db.add(row)
        self.db.commit()
        self.db.refresh(row)
        return row
