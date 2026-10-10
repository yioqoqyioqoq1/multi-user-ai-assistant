"""密码哈希与 JWT 令牌工具。"""
from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.core import config

# PasswordHash.recommended() 默认使用 argon2
_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """对明文密码做 argon2 哈希。"""
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """校验明文密码与哈希是否匹配。"""
    return _password_hash.verify(password, password_hash)


def create_access_token(subject: str) -> str:
    """签发一个以 user_id 为 subject 的 JWT。"""
    expire = datetime.now(timezone.utc) + timedelta(minutes=config.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": subject, "exp": expire}
    return jwt.encode(payload, config.JWT_SECRET, algorithm=config.JWT_ALGORITHM)


def decode_token(token: str) -> str:
    """解析 JWT 并返回 subject(user_id)；无效或过期时抛出 jwt.PyJWTError。"""
    payload = jwt.decode(token, config.JWT_SECRET, algorithms=[config.JWT_ALGORITHM])
    return payload["sub"]