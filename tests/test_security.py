"""单元测试：密码哈希与 JWT 令牌（无 I/O，无外部依赖）。"""
import jwt
import pytest

from app.core import config, security


def test_hash_and_verify():
    hashed = security.hash_password("secret123")
    assert hashed != "secret123"
    assert security.verify_password("secret123", hashed)
    assert not security.verify_password("wrong-password", hashed)


def test_hash_is_salted():
    # 相同明文两次哈希结果不同（argon2 随机盐）
    assert security.hash_password("secret123") != security.hash_password("secret123")


def test_token_roundtrip():
    token = security.create_access_token("user-123")
    assert security.decode_token(token) == "user-123"


def test_decode_garbage_raises():
    with pytest.raises(jwt.PyJWTError):
        security.decode_token("not.a.jwt")


def test_decode_wrong_signature_raises():
    # 用另一把密钥签发的 token，解码应失败
    forged = jwt.encode(
        {"sub": "user-123"}, "another-secret-key-longer-than-32-bytes", algorithm=config.JWT_ALGORITHM
    )
    with pytest.raises(jwt.PyJWTError):
        security.decode_token(forged)