# security.py - 安全工具模块
# 提供密码加密（bcrypt）、JWT令牌的生成与验证功能
# 所有用户密码和安全答案均经过bcrypt哈希处理，JWT用于无状态身份认证

import bcrypt
import jwt
import datetime
import time
import secrets
import pymysql
from threading import Lock
from backend.core.config import Config


def hash_password(password):
    """
    对密码进行bcrypt哈希处理
    使用配置文件中的BCRYPT_LOG_ROUNDS（默认12轮）作为加密强度
    返回哈希后的字符串，可直接存入数据库
    """
    # 将明文密码转为字节串
    password_bytes = password.encode('utf-8')
    # 生成随机盐值，rounds控制加密强度（值越大越安全但越慢）
    salt = bcrypt.gensalt(rounds=Config.BCRYPT_LOG_ROUNDS)
    # 盐值 + 密码 → 哈希值
    hashed = bcrypt.hashpw(password_bytes, salt)
    # 返回字符串形式，方便存储和传输
    return hashed.decode('utf-8')


def verify_password(password, password_hash):
    """
    验证明文密码是否与数据库中存储的哈希值匹配
    返回 True（匹配）或 False（不匹配）
    """
    password_bytes = password.encode('utf-8')
    hash_bytes = password_hash.encode('utf-8')
    # bcrypt.checkpw 内部从hash_bytes中提取盐值，对password_bytes重新哈希后比对
    return bcrypt.checkpw(password_bytes, hash_bytes)


def generate_token(user_id, username, role):
    """
    生成JWT（JSON Web Token）访问令牌
    令牌中包含用户ID、用户名、角色，用于后续请求的身份识别
    令牌有效期由 Config.JWT_EXPIRATION 决定（默认24小时）
    """
    payload = {
        'user_id': user_id,       # 用户唯一标识
        'username': username,     # 用户名
        'role': role,             # 用户角色（guest/vip/admin）
        'jti': secrets.token_urlsafe(16),  # JWT唯一ID，用于令牌撤销黑名单
        'exp': datetime.datetime.utcnow() + datetime.timedelta(seconds=Config.JWT_EXPIRATION),  # 过期时间
        'iat': datetime.datetime.utcnow()  # 签发时间
    }
    # 使用HS256算法签名，防止令牌被篡改
    token = jwt.encode(payload, Config.JWT_SECRET, algorithm='HS256')
    return token


def verify_token(token):
    """
    验证JWT令牌的有效性
    成功时返回解码后的payload字典，包含 user_id、username、role 等字段
    失败（过期、无效或已撤销）时返回 None
    """
    try:
        # 先检查令牌是否已被撤销（加入黑名单）
        if is_token_blacklisted(token):
            return None

        payload = jwt.decode(token, Config.JWT_SECRET, algorithms=['HS256'])
        return payload
    except jwt.ExpiredSignatureError:
        # 令牌已超过有效期
        return None
    except jwt.InvalidTokenError:
        # 令牌签名无效或格式错误
        return None


# ==================== JWT令牌黑名单机制 ====================
# 用于实现令牌撤销（如修改密码、强制登出时使旧令牌失效）
# 生产环境建议替换为 Redis 方案
# 存储结构：{ jti: expiry_timestamp }
_token_blacklist = {}
_blacklist_lock = Lock()
# 定期清理间隔（秒）
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
    """将指定JWT令牌加入黑名单（使其立即失效）"""
    try:
        # 不验证签名地解码获取 jti 和过期时间
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


# ==================== 审计日志工具 ====================

def audit_log(user_id, action, details=None, ip_address=None):
    """
    写入操作审计日志到 user_logs 表
    参数:
        user_id: 操作用户ID
        action: 操作类型（如 'create_user', 'delete_user'）
        details: 操作详情（可选）
        ip_address: 客户端IP（可选）
    所有管理员关键操作（增删改用户、修改权限、数据库操作等）都应调用此函数
    """
    try:
        conn = pymysql.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            charset='utf8mb4'
        )
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO user_logs (user_id, action, details, ip_address) VALUES (%s, %s, %s, %s)",
            (user_id, action, details, ip_address)
        )
        conn.commit()
        conn.close()
    except Exception:
        # 审计日志写入失败不应影响正常业务流程，静默处理
        pass
