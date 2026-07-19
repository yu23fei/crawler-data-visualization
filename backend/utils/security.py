"""安全工具模块

提供密码加密（bcrypt）、JWT 令牌的生成与验证功能。
所有用户密码和安全答案均经过 bcrypt 哈希处理，JWT 用于无状态身份认证。
"""

import datetime
import secrets
import time
from threading import Lock

import bcrypt
import jwt
import pymysql

from backend.core.config import Config


def hash_password(password):
    """对密码进行 bcrypt 哈希处理"""
    password_bytes = password.encode('utf-8')
    salt = bcrypt.gensalt(rounds=Config.BCRYPT_LOG_ROUNDS)
    hashed = bcrypt.hashpw(password_bytes, salt)
    return hashed.decode('utf-8')


def verify_password(password, password_hash):
    """验证明文密码是否与数据库中存储的哈希值匹配"""
    password_bytes = password.encode('utf-8')
    hash_bytes = password_hash.encode('utf-8')
    return bcrypt.checkpw(password_bytes, hash_bytes)


def generate_token(user_id, username, role):
    """生成 JWT 访问令牌

    令牌中包含用户ID、用户名、角色，用于后续请求的身份识别。
    令牌有效期由 Config.JWT_EXPIRATION 决定（默认24小时）。
    """
    payload = {
        'user_id': user_id,
        'username': username,
        'role': role,
        'jti': secrets.token_urlsafe(16),
        'exp': datetime.datetime.utcnow() + datetime.timedelta(seconds=Config.JWT_EXPIRATION),
        'iat': datetime.datetime.utcnow()
    }
    token = jwt.encode(payload, Config.JWT_SECRET, algorithm='HS256')
    return token


def verify_token(token):
    """验证 JWT 令牌的有效性"""
    try:
        if is_token_blacklisted(token):
            return None
        payload = jwt.decode(token, Config.JWT_SECRET, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None


_token_blacklist = {}
_blacklist_lock = Lock()
_BLACKLIST_CLEANUP_INTERVAL = 300
_last_cleanup_time = time.time()


def _cleanup_blacklist():
    """清理已过期的黑名单条目，防止内存泄漏"""
    global _last_cleanup_time
    now = time.time()
    if now - _last_cleanup_time < _BLACKLIST_CLEANUP_INTERVAL:
        return
    with _blacklist_lock:
        expired = [jti for jti, exp in _token_blacklist.items() if exp <= now]
        for jti in expired:
            del _token_blacklist[jti]
        _last_cleanup_time = now


def add_to_blacklist(token):
    """将指定 JWT 令牌加入黑名单（使其立即失效）"""
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        jti = payload.get('jti') or payload.get('exp', 0)
        exp = payload.get('exp', 0)
        if exp > time.time():
            with _blacklist_lock:
                _token_blacklist[str(jti)] = exp
            _cleanup_blacklist()
            return True
    except Exception:
        pass
    return False


def is_token_blacklisted(token):
    """检查令牌是否已被加入黑名单"""
    _cleanup_blacklist()
    try:
        payload = jwt.decode(token, options={"verify_signature": False})
        jti = payload.get('jti') or payload.get('exp', 0)
        with _blacklist_lock:
            return str(jti) in _token_blacklist
    except Exception:
        return False


def audit_log(user_id, action, details=None, ip_address=None):
    """写入操作审计日志到 user_logs 表

    所有管理员关键操作（增删改用户、修改权限、数据库操作等）都应调用此函数。
    审计日志写入失败不应影响正常业务流程，静默处理。
    """
    try:
        conn = pymysql.connect(
            host=Config.DB_HOST, port=Config.DB_PORT,
            user=Config.DB_USER, password=Config.DB_PASSWORD,
            database=Config.DB_NAME, charset='utf8mb4'
        )
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO user_logs (user_id, action, details, ip_address) VALUES (%s, %s, %s, %s)",
            (user_id, action, details, ip_address)
        )
        conn.commit()
        conn.close()
    except Exception:
        pass
