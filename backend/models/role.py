"""角色模型模块

定义 Role 实体类，封装角色相关的数据库查询及权限关联操作。
系统预设 guest/vip/admin 三种角色，通过 role_permissions 关联表绑定权限。
"""

from contextlib import closing

import pymysql
from backend.core.config import Config


class Role:
    """角色模型类

    对应数据库 roles 表，提供 find_by_name、find_by_id、get_all 等方法。
    预置三种角色：guest（访客）、vip（VIP用户）、admin（管理员）。
    """

    def __init__(self, id=None, name=None, description=None, created_at=None):
        self.id = id
        self.name = name
        self.description = description
        self.created_at = created_at

    @staticmethod
    def _get_connection():
        conn = pymysql.connect(
            host=Config.DB_HOST, port=Config.DB_PORT,
            user=Config.DB_USER, password=Config.DB_PASSWORD,
            database=Config.DB_NAME, charset='utf8mb4'
        )
        return conn

    @classmethod
    def find_by_name(cls, name):
        """根据名称查找角色"""
        with closing(cls._get_connection()) as conn:
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute("SELECT * FROM roles WHERE name = %s", (name,))
            role_data = cursor.fetchone()
        if role_data:
            return cls(**role_data)
        return None

    @classmethod
    def find_by_id(cls, role_id):
        """根据ID查找角色"""
        with closing(cls._get_connection()) as conn:
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute("SELECT * FROM roles WHERE id = %s", (role_id,))
            role_data = cursor.fetchone()
        if role_data:
            return cls(**role_data)
        return None

    @classmethod
    def get_all(cls):
        """获取所有角色"""
        with closing(cls._get_connection()) as conn:
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute("SELECT * FROM roles")
            roles_data = cursor.fetchall()
        return [cls(**role_data) for role_data in roles_data]

    def get_permissions(self):
        """获取角色权限列表"""
        with closing(self._get_connection()) as conn:
            cursor = conn.cursor(pymysql.cursors.DictCursor)
            cursor.execute("""
                SELECT p.* FROM permissions p
                JOIN role_permissions rp ON p.id = rp.permission_id
                WHERE rp.role_id = %s
            """, (self.id,))
            permissions = cursor.fetchall()
        return permissions

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'created_at': self.created_at
        }
