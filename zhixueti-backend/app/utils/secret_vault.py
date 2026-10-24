"""Encrypt/decrypt sensitive sys_config values (Fernet derived from app secret)."""

from __future__ import annotations

import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken

from app.core.config import get_settings


def _fernet() -> Fernet:
    raw = get_settings().jwt_secret_key.encode("utf-8")
    key = base64.urlsafe_b64encode(hashlib.sha256(raw).digest())
    return Fernet(key)


def encrypt_secret(plain: str) -> str:
    if not plain:
        return ""
    return _fernet().encrypt(plain.encode("utf-8")).decode("ascii")


def decrypt_secret(cipher: str) -> str:
    if not cipher:
        return ""
    try:
        return _fernet().decrypt(cipher.encode("ascii")).decode("utf-8")
    except InvalidToken:
        return ""
