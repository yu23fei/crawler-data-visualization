# init_db.py - 数据库初始化模块
# 首次启动时自动创建数据库及所有必需表，并插入默认角色和权限数据
# 所有建表语句使用 IF NOT EXISTS，支持幂等执行（多次运行不会破坏已有数据）

import pymysql
from backend.core.config import Config


def init_database():
    """
    初始化数据库结构并灌入默认角色/权限数据
    执行流程：连接MySQL → 创建数据库 → 建表 → 插入默认数据 → 关闭连接
    """
    # 连接到MySQL服务器（不指定数据库，因为可能需要创建）
    conn = pymysql.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        charset='utf8mb4'
    )
    cursor = conn.cursor()

    # 创建数据库（如果不存在），使用utf8mb4编码以支持emoji等特殊字符
    cursor.execute(f"CREATE DATABASE IF NOT EXISTS {Config.DB_NAME} CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci")
    cursor.execute(f"USE {Config.DB_NAME}")

    # ==================== 用户表（users） ====================
    # 存储所有注册用户的基本信息
    # status字段采用ENUM限制值域：pending(待审批) → active(已激活) → disabled(已禁用)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INT PRIMARY KEY AUTO_INCREMENT          COMMENT '用户唯一标识',
        username VARCHAR(50) UNIQUE NOT NULL       COMMENT '登录用户名',
        password_hash VARCHAR(255) NOT NULL        COMMENT 'bcrypt加密后的密码',
        plain_password VARCHAR(255)                COMMENT '明文密码（仅管理员可见）',
        email VARCHAR(100)                         COMMENT '电子邮箱',
        phone VARCHAR(20)                           COMMENT '手机号码',
        security_question VARCHAR(100)              COMMENT '密保问题',
        security_answer VARCHAR(100)                COMMENT '密保答案(bcrypt加密)',
        status ENUM('pending', 'active', 'disabled') DEFAULT 'active' COMMENT '账户状态',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  COMMENT '注册时间',
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间'
    )
    """)

    # ==================== 角色表（roles） ====================
    # 系统预设三种角色：guest(访客)、vip(普通会员)、admin(管理员)
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS roles (
        id INT PRIMARY KEY AUTO_INCREMENT    COMMENT '角色唯一标识',
        name VARCHAR(50) UNIQUE NOT NULL     COMMENT '角色名称(guest/vip/admin)',
        description VARCHAR(200)             COMMENT '角色描述',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP  COMMENT '创建时间'
    )
    """)

    # ==================== 权限表（permissions） ====================
    # 定义系统所有可用权限，包含资源(resource)和操作(action)两个维度
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS permissions (
        id INT PRIMARY KEY AUTO_INCREMENT    COMMENT '权限唯一标识',
        name VARCHAR(50) UNIQUE NOT NULL     COMMENT '权限名称(如 view_charts)',
        description VARCHAR(200)             COMMENT '权限描述',
        resource VARCHAR(50)                 COMMENT '资源标识(charts/data/users等)',
        action VARCHAR(50)                   COMMENT '操作类型(read/manage/filter等)'
    )
    """)

    # ==================== 角色-权限关联表（role_permissions） ====================
    # 实现角色与权限的多对多关系
    # ON DELETE CASCADE: 删除角色或权限时自动清理关联记录
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS role_permissions (
        role_id INT              COMMENT '角色ID，外键关联roles表',
        permission_id INT         COMMENT '权限ID，外键关联permissions表',
        PRIMARY KEY (role_id, permission_id),  -- 复合主键，防止重复关联
        FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE,
        FOREIGN KEY (permission_id) REFERENCES permissions(id) ON DELETE CASCADE
    )
    """)

    # ==================== 用户-角色关联表（user_roles） ====================
    # 实现用户与角色的多对多关系
    # ON DELETE CASCADE: 删除用户或角色时自动清理关联
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS user_roles (
        user_id INT              COMMENT '用户ID，外键关联users表',
        role_id INT              COMMENT '角色ID，外键关联roles表',
        PRIMARY KEY (user_id, role_id),  -- 复合主键，防止重复分配
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (role_id) REFERENCES roles(id) ON DELETE CASCADE
    )
    """)

    # ==================== VIP 申请表（vip_applications） ====================
    # 普通用户申请升级VIP的记录，管理员审批后修改用户角色
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

    # ==================== 用户活动日志表（user_logs） ====================
    # 记录用户的关键操作（登录、数据访问等），用于安全审计
    # ON DELETE SET NULL: 用户被删除后日志保留，user_id置空
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

    # ==================== 预置默认数据 ====================
    # 插入三个内置角色（使用INSERT IGNORE保证幂等性）
    default_roles = [
        ('guest', '普通访客，只能查看图表'),
        ('vip', 'VIP用户，可以查看图表和数据，有筛选功能'),
        ('admin', '管理员，可以管理用户、爬虫、数据库')
    ]
    for name, description in default_roles:
        cursor.execute("INSERT IGNORE INTO roles (name, description) VALUES (%s, %s)", (name, description))

    # 插入八个内置权限（名称 + 描述 + 关联资源 + 操作类型）
    default_permissions = [
        ('view_charts', '查看图表', 'charts', 'read'),
        ('view_data', '查看数据', 'data', 'read'),
        ('filter_jobs', '筛选岗位', 'jobs', 'filter'),
        ('manage_users', '管理用户', 'users', 'manage'),
        ('manage_crawlers', '管理爬虫', 'crawlers', 'manage'),
        ('manage_database', '管理数据库', 'database', 'manage'),
        ('approve_users', '审批用户', 'users', 'approve'),
        ('view_user_logs', '查看用户日志', 'logs', 'read')
    ]
    for name, description, resource, action in default_permissions:
        cursor.execute("INSERT IGNORE INTO permissions (name, description, resource, action) VALUES (%s, %s, %s, %s)",
                      (name, description, resource, action))

    # ==================== 分配默认权限给各角色 ====================

    # 访客(guest)：只能查看图表
    cursor.execute("SELECT id FROM roles WHERE name='guest'")
    guest_id = cursor.fetchone()[0]
    cursor.execute("SELECT id FROM permissions WHERE name='view_charts'")
    view_charts_id = cursor.fetchone()[0]
    cursor.execute("INSERT IGNORE INTO role_permissions (role_id, permission_id) VALUES (%s, %s)", (guest_id, view_charts_id))

    # VIP用户：可以查看图表、查看数据、筛选岗位
    cursor.execute("SELECT id FROM roles WHERE name='vip'")
    vip_id = cursor.fetchone()[0]
    for perm_name in ['view_charts', 'view_data', 'filter_jobs']:
        cursor.execute("SELECT id FROM permissions WHERE name=%s", (perm_name,))
        perm_id = cursor.fetchone()[0]
        cursor.execute("INSERT IGNORE INTO role_permissions (role_id, permission_id) VALUES (%s, %s)", (vip_id, perm_id))

    # 管理员(admin)：拥有所有权限
    cursor.execute("SELECT id FROM roles WHERE name='admin'")
    admin_id = cursor.fetchone()[0]
    cursor.execute("SELECT id FROM permissions")
    all_perms = cursor.fetchall()
    for perm_id in all_perms:
        cursor.execute("INSERT IGNORE INTO role_permissions (role_id, permission_id) VALUES (%s, %s)", (admin_id, perm_id[0]))

    # 提交所有变更并关闭连接
    conn.commit()
    conn.close()
    print("数据库初始化完成")

if __name__ == '__main__':
    init_database()