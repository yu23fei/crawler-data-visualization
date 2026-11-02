"""数据库初始化模块

首次启动时自动创建数据库及所有必需表，并插入默认角色和权限数据。
所有建表语句使用 IF NOT EXISTS，支持幂等执行（多次运行不会破坏已有数据）。
"""

import pymysql
from backend.core.config import Config


def init_database():
    """初始化数据库结构并灌入默认角色/权限数据

    执行流程：连接MySQL → 创建数据库 → 建表 → 插入默认数据 → 关闭连接。
    """
    conn = pymysql.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        charset='utf8mb4'
    )
    cursor = conn.cursor()

    cursor.execute(
        f"CREATE DATABASE IF NOT EXISTS {Config.DB_NAME} "
        f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
    )
    cursor.execute(f"USE {Config.DB_NAME}")

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INT PRIMARY KEY AUTO_INCREMENT          COMMENT '用户唯一标识',
        username VARCHAR(50) UNIQUE NOT NULL       COMMENT '登录用户名',
        password_hash VARCHAR(255) NOT NULL        COMMENT 'bcrypt加密后的密码',
        plain_password VARCHAR(255)                COMMENT '明文密码(仅管理员可见)',
        email VARCHAR(100)                         COMMENT '电子邮箱',
        phone VARCHAR(20)                           COMMENT '手机号码',
        security_question VARCHAR(100)              COMMENT '密保问题',
        security_answer VARCHAR(100)                COMMENT '密保答案(bcrypt加密)',
        status ENUM('pending', 'active', 'disabled') DEFAULT 'active' COMMENT '账户状态',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  COMMENT '注册时间',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间'
    )
    """)

    # 兼容旧数据库：如果 plain_password 列不存在则自动添加
    try:
        cursor.execute("""
        ALTER TABLE users ADD COLUMN plain_password VARCHAR(255)
        COMMENT '明文密码(仅管理员可见)' AFTER password_hash
        """)
        print("已为 users 表添加 plain_password 列")
    except Exception as e:
        # 1060 = Duplicate column name（列已存在），忽略即可
        if getattr(e, 'args', [None])[0] == 1060:
            pass
        else:
            raise

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS roles (
        id INT PRIMARY KEY AUTO_INCREMENT    COMMENT '角色唯一标识',
        name VARCHAR(50) UNIQUE NOT NULL     COMMENT '角色名称(guest/vip/admin)',
        description VARCHAR(200)             COMMENT '角色描述',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  COMMENT '创建时间'
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS permissions (
        id INT PRIMARY KEY AUTO_INCREMENT    COMMENT '权限唯一标识',
        name VARCHAR(50) UNIQUE NOT NULL     COMMENT '权限名称(如 view_charts)',
        description VARCHAR(200)             COMMENT '权限描述',
        resource VARCHAR(50)                 COMMENT '资源标识(charts/data/users等)',
        action VARCHAR(50)                   COMMENT '操作类型(read/manage/filter等)'
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS role_permissions (
        role_id INT              COMMENT '角色ID，外键关联roles表',
        permission_id INT         COMMENT '权限ID，外键关联permissions表',
        PRIMARY KEY (role_id, permission_id),
        FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
        FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_roles (
        user_id INT              COMMENT '用户ID，外键关联users表',
        role_id INT              COMMENT '角色ID，外键关联roles表',
        PRIMARY KEY (user_id, role_id),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS vip_applications (
        id INT PRIMARY KEY AUTO_INCREMENT          COMMENT '申请记录ID',
        user_id INT NOT NULL                       COMMENT '申请人用户ID',
        status ENUM('pending', 'approved', 'rejected') DEFAULT 'pending' COMMENT '审批状态',
        handled_by INT                             COMMENT '审批人管理员ID',
        remark VARCHAR(500)                        COMMENT '审批备注',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  COMMENT '申请时间',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '处理时间',
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (handled_by) REFERENCES users(id) ON DELETE SET NULL
    )
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS favorites (
        id INT PRIMARY KEY AUTO_INCREMENT          COMMENT '收藏记录ID',
        user_id INT NOT NULL                       COMMENT '用户ID',
        job_id INT NOT NULL                        COMMENT '岗位ID（关联jobs_analysis.id）',
        data_source VARCHAR(20) NOT NULL           COMMENT '数据来源（51job/zhaopin）',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '收藏时间',
        UNIQUE KEY uk_user_job (user_id, job_id, data_source),
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    ) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS job_view_history (
        id INT PRIMARY KEY AUTO_INCREMENT          COMMENT '浏览记录ID',
        user_id INT NOT NULL                       COMMENT '用户ID',
        job_id INT NOT NULL                        COMMENT '岗位ID（关联jobs_analysis.id）',
        data_source VARCHAR(20) NOT NULL           COMMENT '数据来源（51job/zhaopin）',
        viewed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '浏览时间',
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    ) DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_0900_ai_ci
    """)

    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_logs (
        id INT PRIMARY KEY AUTO_INCREMENT    COMMENT '日志唯一标识',
        user_id INT                          COMMENT '操作用户ID',
        action VARCHAR(50)                   COMMENT '操作类型',
        details TEXT                         COMMENT '操作详情',
        ip_address VARCHAR(45)               COMMENT '客户端IP地址(支持IPv6)',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  COMMENT '操作时间',
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
    )
    """)

    default_roles = [
        ('guest', '普通访客，可以查看图表、数据和岗位详情'),
        ('vip', 'VIP用户，可以查看图表、筛选数据、管理收藏和浏览历史'),
        ('admin', '管理员，可以管理用户、爬虫、数据库')
    ]
    for name, description in default_roles:
        cursor.execute(
            "INSERT IGNORE INTO roles (name, description) VALUES (%s, %s)",
            (name, description)
        )

    default_permissions = [
        ('view_charts', '查看图表', 'charts', 'read'),
        ('view_data', '查看数据', 'data', 'read'),
        ('filter_jobs', '筛选岗位', 'jobs', 'filter'),
        ('view_detail', '查看岗位详情', 'jobs', 'read'),
        ('manage_favorites', '管理收藏', 'favorites', 'manage'),
        ('view_history', '查看浏览历史', 'history', 'read'),
        ('manage_users', '管理用户', 'users', 'manage'),
        ('manage_crawlers', '管理爬虫', 'crawlers', 'manage'),
        ('manage_database', '管理数据库', 'database', 'manage'),
        ('approve_users', '审批用户', 'users', 'approve'),
        ('view_user_logs', '查看用户日志', 'logs', 'read')
    ]
    for name, description, resource, action in default_permissions:
        cursor.execute(
            "INSERT IGNORE INTO permissions (name, description, resource, action) "
            "VALUES (%s, %s, %s, %s)",
            (name, description, resource, action)
        )

    cursor.execute("SELECT id FROM roles WHERE name='guest'")
    guest_id = cursor.fetchone()[0]
    for perm_name in ['view_charts', 'view_data', 'view_detail']:
        cursor.execute("SELECT id FROM permissions WHERE name=%s", (perm_name,))
        perm_id = cursor.fetchone()[0]
        cursor.execute(
            "INSERT IGNORE INTO role_permissions (role_id, permission_id) VALUES (%s, %s)",
            (guest_id, perm_id)
        )

    cursor.execute("SELECT id FROM roles WHERE name='vip'")
    vip_id = cursor.fetchone()[0]
    for perm_name in ['view_charts', 'filter_jobs', 'view_detail', 'manage_favorites', 'view_history']:
        cursor.execute("SELECT id FROM permissions WHERE name=%s", (perm_name,))
        perm_id = cursor.fetchone()[0]
        cursor.execute(
            "INSERT IGNORE INTO role_permissions (role_id, permission_id) VALUES (%s, %s)",
            (vip_id, perm_id)
        )

    cursor.execute("SELECT id FROM roles WHERE name='admin'")
    admin_id = cursor.fetchone()[0]
    cursor.execute("SELECT id FROM permissions WHERE name != 'view_data'")
    all_perms = cursor.fetchall()
    for perm_id in all_perms:
        cursor.execute(
            "INSERT IGNORE INTO role_permissions (role_id, permission_id) VALUES (%s, %s)",
            (admin_id, perm_id[0])
        )

    conn.commit()
    conn.close()
    print("数据库初始化完成")


if __name__ == '__main__':
    init_database()
