# ============================================================
# 配置 - 低频 + 反检测 + 稳定性优先方案
# ============================================================

# --- 存储方式 ---
import os
from pathlib import Path
from dotenv import load_dotenv

# 自动加载 .env 文件（项目根目录）
dotenv_path = Path(__file__).resolve().parents[3] / '.env'
if dotenv_path.exists():
    load_dotenv(dotenv_path)

# --- 浏览器 ---
HEADLESS = False  # 必须为False，否则无法看到验证码
TIMEOUT = 60000
PAGES_PER_BROWSER = 50  # 提高，减少重启频率

# --- 验证码处理 ---
# 遇到验证码时暂停并等待人工验证
CAPTCHA_PAUSE_ENABLED = True  # 启用验证码暂停
CAPTCHA_PAUSE_TIMEOUT = 300   # 最长等待时间（秒），0=无限等待
CAPTCHA_KEYWORDS = [          # 验证码检测关键词
    "验证码",
    "captcha",
    "验证",
    "人机验证",
    "安全验证",
    "滑动验证",
    "请完成验证",
    "verify"
]

# --- 任务队列 ---
WORKERS = 5  # 提高到5个进程，加快速度
RANGE_START = 168000000
RANGE_END = 169000000
# --- 重试 ---
MAX_RETRY = 3

# --- 延迟 ---
MIN_DELAY = 3  # 降低到3秒
MAX_DELAY = 8  # 降低到8秒

# --- 代理池配置 ---
# 关闭本地IP轮换（本地IP不能作为HTTP代理）
USE_LOCAL_IP_POOL = False
USE_PROXY = False  # 关闭外部代理池

# --- Redis + proxy_pool 配置 ---
# proxy_pool 项目: https://github.com/jhao104/proxy_pool
REDIS_HOST = "127.0.0.1"
REDIS_PORT = 6379
REDIS_PASSWORD = os.environ.get("REDIS_PASSWORD", "")  # 生产环境必须通过环境变量设置

# proxy_pool HTTP API 地址
PROXY_POOL_API_URL = "http://127.0.0.1:5010"

# 旧版代理列表配置（已废弃，使用 proxy_pool 后不需要）
# PROXY_LIST = [
#     {"server": "http://123.123.123.123:8080"},
# ]


# --- MySQL（预留）---
MYSQL_HOST = "127.0.0.1"
MYSQL_PORT = 3306
MYSQL_USER = os.environ.get("MYSQL_USER", "root")
# 数据库密码必须通过环境变量设置，不提供默认值（防止因遗忘配置导致安全风险）
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD")
MYSQL_DB = os.environ.get("MYSQL_DB", "yingjie_spider")
