"""数据库连接工具模块

提供数据库连接的上下文管理器，确保连接使用后自动关闭
"""

from contextlib import contextmanager

import pymysql
from backend.core.config import Config


@contextmanager
def get_db_connection(database=None):
    """获取数据库连接的上下文管理器

    使用 with 语句自动管理连接生命周期，避免连接泄漏。
    可通过 database 参数指定数据库名，不传则使用 Config.DB_NAME。
    """
    conn = pymysql.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=database or Config.DB_NAME,
        charset='utf8mb4'
    )
    try:
        yield conn
    finally:
        conn.close()


@contextmanager
def get_db_cursor(dict_cursor=True):
    """获取数据库游标的上下文管理器

    自动创建带 DictCursor 的游标，并在退出时关闭连接。
    dict_cursor=False 时返回普通游标。
    """
    conn = pymysql.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        charset='utf8mb4'
    )
    try:
        cursor = conn.cursor(pymysql.cursors.DictCursor if dict_cursor else None)
        yield conn, cursor
    finally:
        conn.close()
