# user.py - 用户模型模块
# 定义User实体类，封装用户相关的数据库操作（增、查、角色关联、权限查询）
# 采用Active Record风格模式，每个User实例关联一条users表记录

import pymysql
from backend.core.config import Config


class User:
    """
    用户模型类
    对应数据库 users 表，提供 find_by_username、find_by_id、save 等方法
    通过关联表 user_roles 和 role_permissions 实现基于角色的权限控制（RBAC）
    """
    def __init__(self, id=None, username=None, password_hash=None, plain_password=None, email=None,
                 phone=None, security_question=None, security_answer=None,
                 status=None, created_at=None, updated_at=None):
        self.id = id
        self.username = username
        self.password_hash = password_hash
        self.plain_password = plain_password
        self.email = email
        self.phone = phone
        self.security_question = security_question
        self.security_answer = security_answer
        self.status = status
        self.created_at = created_at
        self.updated_at = updated_at

    @staticmethod
    def get_db_conn():
        """获取数据库连接"""
        conn = pymysql.connect(
            host=Config.DB_HOST,
            port=Config.DB_PORT,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            database=Config.DB_NAME,
            charset='utf8mb4'
        )
        return conn

    @classmethod
    def find_by_username(cls, username):
        """根据用户名查找用户"""
        conn = cls.get_db_conn()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user_data = cursor.fetchone()
        conn.close()

        if user_data:
            return cls(**user_data)
        return None

    @classmethod
    def find_by_id(cls, user_id):
        """根据ID查找用户"""
        conn = cls.get_db_conn()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("SELECT * FROM users WHERE id = %s", (user_id,))
        user_data = cursor.fetchone()
        conn.close()

        if user_data:
            return cls(**user_data)
        return None

    def save(self):
        """保存用户到数据库"""
        conn = self.get_db_conn()
        cursor = conn.cursor()

        if self.id:
            # 更新现有用户
            cursor.execute("""
                UPDATE users SET username=%s, password_hash=%s, plain_password=%s, email=%s, phone=%s,
                security_question=%s, security_answer=%s, status=%s
                WHERE id=%s
            """, (self.username, self.password_hash, self.plain_password, self.email, self.phone,
                  self.security_question, self.security_answer, self.status, self.id))
        else:
            # 创建新用户
            cursor.execute("""
                INSERT INTO users (username, password_hash, plain_password, email, phone, security_question, security_answer, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            """, (self.username, self.password_hash, self.plain_password, self.email, self.phone,
                  self.security_question, self.security_answer, self.status))
            self.id = cursor.lastrowid

        conn.commit()
        conn.close()
        return self

    def get_roles(self):
        """获取用户角色"""
        conn = self.get_db_conn()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("""
            SELECT r.* FROM roles r
            JOIN user_roles ur ON r.id = ur.role_id
            WHERE ur.user_id = %s
        """, (self.id,))
        roles = cursor.fetchall()
        conn.close()
        return roles

    def get_permissions(self):
        """获取用户权限"""
        conn = self.get_db_conn()
        cursor = conn.cursor(pymysql.cursors.DictCursor)
        cursor.execute("""
            SELECT DISTINCT p.name FROM permissions p
            JOIN role_permissions rp ON p.id = rp.permission_id
            JOIN user_roles ur ON rp.role_id = ur.role_id
            WHERE ur.user_id = %s
        """, (self.id,))
        permissions = [row['name'] for row in cursor.fetchall()]
        conn.close()
        return permissions

    def has_permission(self, permission_name):
        """检查用户是否有指定权限"""
        permissions = self.get_permissions()
        return permission_name in permissions

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'username': self.username,
            'password_hash': self.password_hash,
            'plain_password': self.plain_password,
            'email': self.email,
            'phone': self.phone,
            'status': self.status,
            'created_at': self.created_at,
            'updated_at': self.updated_at
        }
