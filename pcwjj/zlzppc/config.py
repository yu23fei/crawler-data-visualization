# ============================================================
# 智联招聘爬虫配置
# ============================================================

import os

# --- MySQL ---
MYSQL_HOST = "127.0.0.1"
MYSQL_PORT = 3306
MYSQL_USER = os.environ.get("MYSQL_USER", "root")
# 数据库密码必须通过环境变量设置，不提供默认值（防止因遗忘配置导致安全风险）
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD")
MYSQL_DB = os.environ.get("MYSQL_DB", "yingjie_spider")

# --- 爬虫配置 ---
# 起始ID（不含CCL前缀）
BASE_JOB_ID = "1358940740J40870875012"
# 采集范围：前后各200000条
RANGE_OFFSET = 200000


# --- ID生成策略 ---
# 策略模式: "single"=仅变第一段(原逻辑), "dual"=双段组合(推荐)
ID_GEN_MODE = "dual"
# 第一段数字偏移范围（前后各）
OFFSET_PART1 = 5000
# 第二段数字偏移范围（前后各，0表示不变）
OFFSET_PART2 = 20000
# 双段模式下，控制每批最大生成ID数（防止组合爆炸）
MAX_DUAL_IDS = 100000

# --- 多线程 ---
# 工作线程数（根据CPU核心数和网络带宽调整）
# 推荐：本地IP用10-15，有IP池可用20-30
WORKERS = 10

# --- 请求配置 ---
# 请求超时时间（秒）
REQUEST_TIMEOUT = 15
# 最大重试次数
MAX_RETRY = 2

# --- 随机延迟 ---
# 请求间隔（秒）- 降低延迟提升速度
# 保守模式：2-5秒（当前）
# 快速模式：0.5-2秒（推荐）
# 极速模式：0.2-1秒（有风险）
MIN_DELAY = 2
MAX_DELAY = 5

# --- IP池配置 ---
# 是否启用IP池（False则使用本地IP）
USE_PROXY_POOL = False
# IP池API地址（返回JSON格式：[{"ip": "xxx", "port": xxx}]
PROXY_POOL_API = "http://localhost:8080/get_proxy"
# 单个IP最大使用次数
MAX_USES_PER_PROXY = 50

# --- User-Agent池 ---
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:120.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36",
]

# --- Playwright ID采集 ---
PLAYWRIGHT_CITIES = ["chongqing"]
PLAYWRIGHT_MAX_PAGES = 50
PLAYWRIGHT_PAGE_WAIT = 3
PLAYWRIGHT_PAGE_DELAY = 2
COLLECTED_IDS_FILE = 'collected_ids.json'
