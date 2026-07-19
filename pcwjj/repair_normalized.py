"""
数据修复脚本：从原始数据表重新同步到规范化表
用于爬虫数据出错或丢失后的修复

用法：
    python pcwjj/repair_normalized.py              # 修复所有数据
    python pcwjj/repair_normalized.py 51job        # 只修复 前程无忧 数据
    python pcwjj/repair_normalized.py zhaopin      # 只修复智联数据
"""
import sys
import os
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 添加模块搜索路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from normalized_db import resync_from_source
import pymysql

# 数据库配置 —— 密码必须通过环境变量设置，不提供默认值
_DB_PASSWORD = os.environ.get('MYSQL_PASSWORD')
if not _DB_PASSWORD:
    print("错误: 环境变量 MYSQL_PASSWORD 未设置，无法连接数据库")
    print("请先执行: set MYSQL_PASSWORD=你的数据库密码")
    import sys
    sys.exit(1)

DB_CONFIG = {
    'host': '127.0.0.1',
    'port': 3306,
    'user': os.environ.get('MYSQL_USER', 'root'),
    'password': _DB_PASSWORD,
    'database': os.environ.get('MYSQL_DB', 'yingjie_spider'),
    'charset': 'utf8mb4'
}


def main():
    # 确定修复目标
    targets = []
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg == '51job':
            targets = [('jobs', '51job')]
        elif arg == 'zhaopin':
            targets = [('zhaopin_jobs', 'zhaopin')]
        else:
            print(f"未知参数: {arg}，可选: 51job, zhaopin")
            sys.exit(1)
    else:
        targets = [('jobs', '51job'), ('zhaopin_jobs', 'zhaopin')]

    # 连接数据库
    try:
        conn = pymysql.connect(**DB_CONFIG)
        logger.info("数据库连接成功")
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        sys.exit(1)

    # 执行修复
    total_success = 0
    total_fail = 0
    for table_name, data_source in targets:
        logger.info(f"\n{'='*50}")
        logger.info(f"开始修复: {table_name} → {data_source}")
        logger.info(f"{'='*50}")
        success, fail = resync_from_source(conn, table_name, data_source, log=logger)
        total_success += success
        total_fail += fail

    conn.close()
    logger.info(f"\n{'='*50}")
    logger.info(f"修复完成: 成功={total_success}, 失败={total_fail}")
    logger.info(f"{'='*50}")


if __name__ == '__main__':
    main()
