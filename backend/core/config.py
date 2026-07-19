"""应用配置模块

集中管理所有环境变量和系统常量，遵循 12-factor 应用原则。
所有敏感配置均通过环境变量注入，生产环境必须设置，不存在默认值。
启动时自动加载项目根目录下的 .env 文件。
"""

import os
import secrets


def _load_dotenv():
    """从项目根目录的 .env 文件加载环境变量（仅加载尚未设置的变量）

    避免引入 python-dotenv 依赖，使用内置方法解析。
    文件位置：从本文件向上查找两级到项目根目录。
    """
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    env_path = os.path.join(project_root, '.env')

    if not os.path.isfile(env_path):
        return

    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


_load_dotenv()


class Config:
    """应用全局配置类

    所有敏感配置项必须通过同名环境变量设置，不提供默认值，
    防止因遗忘配置导致安全事故。
    """

    DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
    DB_PORT = int(os.getenv('DB_PORT', 3306))
    DB_USER = os.getenv('DB_USER', 'root')
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    DB_NAME = os.getenv('DB_NAME', 'yingjie_spider')

    JWT_SECRET = os.getenv('JWT_SECRET')
    JWT_EXPIRATION = 86400

    SECRET_KEY = os.getenv('SECRET_KEY', os.urandom(24).hex())

    BCRYPT_LOG_ROUNDS = 12

    LOGIN_RATE_LIMIT = int(os.getenv('LOGIN_RATE_LIMIT', '5'))
    RESET_RATE_LIMIT = int(os.getenv('RESET_RATE_LIMIT', '3'))

    @classmethod
    def validate(cls):
        """验证关键配置项是否已设置

        在应用启动时调用，如缺少必要配置则立即终止，
        防止以不安全状态运行。
        """
        errors = []
        if not cls.DB_PASSWORD:
            errors.append('环境变量 DB_PASSWORD 未设置 —— 数据库密码为必填项')
        if not cls.JWT_SECRET:
            errors.append('环境变量 JWT_SECRET 未设置 —— JWT签名密钥为必填项')
        if cls.DB_PASSWORD and len(cls.DB_PASSWORD) < 8:
            errors.append('DB_PASSWORD 长度不足8位，请使用强密码')
        if cls.JWT_SECRET and len(cls.JWT_SECRET) < 32:
            errors.append('JWT_SECRET 长度不足32位，请使用强随机密钥')
        return errors
