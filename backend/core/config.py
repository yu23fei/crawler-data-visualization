# config.py - 应用配置模块
# 集中管理所有环境变量和系统常量，遵循12-factor应用原则
# 所有敏感配置均通过环境变量注入，生产环境必须设置，不存在默认值
# 启动时自动加载项目根目录下的 .env 文件

import os
import secrets


def _load_dotenv():
    """
    从项目根目录的 .env 文件加载环境变量（仅加载尚未设置的变量）
    避免引入 python-dotenv 依赖，使用内置方法解析
    文件位置：从本文件向上查找两级到项目根目录
    """
    # 项目根目录 = config.py 的上两级目录
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    env_path = os.path.join(project_root, '.env')

    if not os.path.isfile(env_path):
        return

    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # 跳过空行和注释行
            if not line or line.startswith('#'):
                continue
            # 解析 KEY=VALUE 格式（忽略引号包裹的值）
            if '=' not in line:
                continue
            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            # 仅在环境变量未设置时使用 .env 中的值
            if key and key not in os.environ:
                os.environ[key] = value


# 模块导入时自动加载 .env 文件
_load_dotenv()


class Config:
    """
    应用全局配置类
    所有敏感配置项必须通过同名环境变量设置，不提供默认值防止因遗忘配置导致安全事故
    """

    # ==================== 数据库配置 ====================
    # MySQL服务器地址，默认本机
    DB_HOST = os.getenv('DB_HOST', '127.0.0.1')
    # MySQL服务端口，默认3306
    DB_PORT = int(os.getenv('DB_PORT', 3306))
    # 数据库用户名
    DB_USER = os.getenv('DB_USER', 'root')
    # 数据库密码 —— 必须通过环境变量设置，不提供默认值
    DB_PASSWORD = os.getenv('DB_PASSWORD')
    # 数据库名称
    DB_NAME = os.getenv('DB_NAME', 'yingjie_spider')

    # ==================== JWT配置 ====================
    # JWT签名密钥 —— 必须通过环境变量设置，若无则启动时随机生成（重启后所有令牌失效）
    JWT_SECRET = os.getenv('JWT_SECRET')
    # JWT令牌有效期，单位秒（86400 = 24小时）
    JWT_EXPIRATION = 86400

    # ==================== Flask密钥 ====================
    # Flask应用签名密钥（用于session、flash消息等内置功能）
    SECRET_KEY = os.getenv('SECRET_KEY', os.urandom(24).hex())

    # ==================== 安全配置 ====================
    # bcrypt加密轮数（12轮约需0.3秒，平衡安全性与用户体验）
    BCRYPT_LOG_ROUNDS = 12

    # ==================== 限流配置 ====================
    # 登录接口限流 —— 每个IP每分钟最大请求数
    LOGIN_RATE_LIMIT = int(os.getenv('LOGIN_RATE_LIMIT', '5'))
    # 密码重置接口限流 —— 每个IP每分钟最大请求数
    RESET_RATE_LIMIT = int(os.getenv('RESET_RATE_LIMIT', '3'))

    @classmethod
    def validate(cls):
        """
        验证关键配置项是否已设置
        在应用启动时调用，如缺少必要配置则立即终止，防止以不安全状态运行
        返回错误信息列表，空列表表示所有配置正常
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
