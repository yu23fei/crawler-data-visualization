# admin.py - 管理员接口模块
# 提供用户管理（列表、创建、删除、角色修改、状态变更）、角色管理和权限管理等后台功能
# 所有接口均受 @role_required(['admin']) 保护，仅管理员可访问
# 用户管理涉及 users + user_roles 两张表的级联操作（先删关联再删用户）
from flask import Blueprint, request, jsonify
from backend.models.user import User
from backend.models.role import Role
from backend.middleware.auth import role_required
from backend.utils.security import hash_password, verify_token, audit_log
import pymysql
from backend.core.config import Config

admin_bp = Blueprint('admin', __name__)


from backend.api.v1.auth import _get_client_ip


def get_db_conn():
    """
    获取数据库连接（通用方法）
    返回 pymysql 连接对象，调用方负责关闭连接以释放资源
    """
    return pymysql.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        charset='utf8mb4'
    )


@admin_bp.route('/api/admin/users', methods=['GET'])
@role_required(['admin'])
def get_users():
    """获取用户列表（分页），关联查询每个用户的角色"""
    conn = get_db_conn()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size

    # LEFT JOIN user_roles + roles，通过 GROUP_CONCAT 将多个角色名合并为逗号分隔字符串
    cursor.execute("""
        SELECT u.*, GROUP_CONCAT(r.name) as roles
        FROM users u
        LEFT JOIN user_roles ur ON u.id = ur.user_id
        LEFT JOIN roles r ON ur.role_id = r.id
        GROUP BY u.id
        LIMIT %s, %s
    """, (offset, size))
    users = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) as total FROM users")
    total = cursor.fetchone()['total']

    conn.close()

    return jsonify({
        'code': 200,
        'data': {
            'users': users,
            'total': total,
            'page': page,
            'size': size
        }
    })


@admin_bp.route('/api/admin/users', methods=['POST'])
@role_required(['admin'])
def create_user():
    """创建新用户（含密码加密和角色分配）"""
    data = request.get_json()

    # 校验必填字段
    required_fields = ['username', 'password', 'role_name']
    for field in required_fields:
        if field not in data:
            return jsonify({'code': 400, 'msg': f'缺少必填字段: {field}'}), 400

    # 检查用户名是否已存在
    existing = User.find_by_username(data['username'])
    if existing:
        return jsonify({'code': 400, 'msg': '用户名已存在'}), 400

    # 查找对应角色
    role = Role.find_by_name(data['role_name'])
    if not role:
        return jsonify({'code': 404, 'msg': '角色不存在'}), 404

    # 创建用户对象并保存到数据库
    user = User(
        username=data['username'],
        password_hash=hash_password(data['password']),
        plain_password=data['password'],
        email=data.get('email'),
        phone=data.get('phone'),
        status=data.get('status', 'active')
    )
    user.save()

    # 分配角色（写入 user_roles 关联表）
    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO user_roles (user_id, role_id) VALUES (%s, %s)", (user.id, role.id))
    conn.commit()
    conn.close()

    # 记录审计日志
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    payload = verify_token(token)
    admin_id = payload['user_id'] if payload else None
    if admin_id:
        audit_log(admin_id, 'create_user', f"创建用户: {data['username']}, 角色: {data['role_name']}", _get_client_ip())

    return jsonify({'code': 200, 'msg': '用户创建成功', 'data': {'user_id': user.id, 'password': data['password']}})


@admin_bp.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@role_required(['admin'])
def delete_user(user_id):
    """删除用户（禁止删除自己），会同时清理 user_roles 关联数据"""
    user = User.find_by_id(user_id)
    if not user:
        return jsonify({'code': 404, 'msg': '用户不存在'}), 404

    # 通过 token 解析当前登录用户ID，禁止删除自己的账号
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    payload = verify_token(token)
    if payload and payload['user_id'] == user_id:
        return jsonify({'code': 400, 'msg': '不能删除自己的账号'}), 400

    conn = get_db_conn()
    cursor = conn.cursor()

    # 先删除用户角色关联（外键约束），再删除用户本身
    cursor.execute("DELETE FROM user_roles WHERE user_id = %s", (user_id,))
    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))

    conn.commit()
    conn.close()

    # 记录审计日志
    if payload and payload['user_id'] != user_id:
        audit_log(payload['user_id'], 'delete_user', f"删除用户ID: {user_id} ({user.username})", _get_client_ip())

    return jsonify({'code': 200, 'msg': '用户删除成功'})


@admin_bp.route('/api/admin/users/<int:user_id>/role', methods=['PUT'])
@role_required(['admin'])
def update_user_role(user_id):
    """
    修改用户角色
    逻辑：先删除旧的用户-角色关联，再插入新的关联
    """
    data = request.get_json()

    if 'role_name' not in data:
        return jsonify({'code': 400, 'msg': '缺少角色名称'}), 400

    user = User.find_by_id(user_id)
    if not user:
        return jsonify({'code': 404, 'msg': '用户不存在'}), 404

    role = Role.find_by_name(data['role_name'])
    if not role:
        return jsonify({'code': 404, 'msg': '角色不存在'}), 404

    conn = get_db_conn()
    cursor = conn.cursor()

    # 先删后插，实现角色替换
    cursor.execute("DELETE FROM user_roles WHERE user_id = %s", (user_id,))
    cursor.execute("INSERT INTO user_roles (user_id, role_id) VALUES (%s, %s)", (user_id, role.id))

    conn.commit()
    conn.close()

    # 记录审计日志
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    payload = verify_token(token)
    admin_id = payload['user_id'] if payload else None
    if admin_id:
        audit_log(admin_id, 'update_user_role', f"修改用户ID {user_id} 角色为: {data['role_name']}", _get_client_ip())

    return jsonify({'code': 200, 'msg': '角色修改成功'})


@admin_bp.route('/api/admin/users/<int:user_id>/status', methods=['PUT'])
@role_required(['admin'])
def update_user_status(user_id):
    """启用/禁用用户（支持 active/disabled/pending 三种状态）"""
    data = request.get_json()

    if 'status' not in data:
        return jsonify({'code': 400, 'msg': '缺少状态参数'}), 400

    # 校验状态值合法性
    if data['status'] not in ['active', 'disabled', 'pending']:
        return jsonify({'code': 400, 'msg': '无效的状态值'}), 400

    user = User.find_by_id(user_id)
    if not user:
        return jsonify({'code': 404, 'msg': '用户不存在'}), 404

    # 修改状态并通过 User.save() 持久化
    user.status = data['status']
    user.save()

    # 记录审计日志
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    payload = verify_token(token)
    admin_id = payload['user_id'] if payload else None
    if admin_id:
        audit_log(admin_id, 'update_user_status', f"修改用户ID {user_id} 状态为: {data['status']}", _get_client_ip())

    return jsonify({'code': 200, 'msg': '状态更新成功'})


@admin_bp.route('/api/admin/users/logs', methods=['GET'])
@role_required(['admin'])
def get_user_logs():
    """查看用户活动日志（分页，按时间倒序）"""
    conn = get_db_conn()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size

    # 关联查询用户名，按创建时间倒序排列
    cursor.execute("""
        SELECT l.*, u.username
        FROM user_logs l
        LEFT JOIN users u ON l.user_id = u.id
        ORDER BY l.created_at DESC
        LIMIT %s, %s
    """, (offset, size))
    logs = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) as total FROM user_logs")
    total = cursor.fetchone()['total']

    conn.close()

    return jsonify({
        'code': 200,
        'data': {
            'logs': logs,
            'total': total,
            'page': page,
            'size': size
        }
    })


@admin_bp.route('/api/admin/roles', methods=['GET'])
@role_required(['admin'])
def get_roles():
    """获取所有角色列表"""
    roles = Role.get_all()
    return jsonify({
        'code': 200,
        'data': [role.to_dict() for role in roles]
    })


@admin_bp.route('/api/admin/roles/<int:role_id>/permissions', methods=['PUT'])
@role_required(['admin'])
def update_role_permissions(role_id):
    """
    更新角色权限
    逻辑：先删除该角色的所有旧权限关联，再插入新的权限关联
    """
    data = request.get_json()

    if 'permission_ids' not in data:
        return jsonify({'code': 400, 'msg': '缺少权限ID列表'}), 400

    role = Role.find_by_id(role_id)
    if not role:
        return jsonify({'code': 404, 'msg': '角色不存在'}), 404

    conn = get_db_conn()
    cursor = conn.cursor()

    # 先清空该角色的所有权限
    cursor.execute("DELETE FROM role_permissions WHERE role_id = %s", (role_id,))

    # 逐条插入新的权限关联
    for perm_id in data['permission_ids']:
        cursor.execute("INSERT INTO role_permissions (role_id, permission_id) VALUES (%s, %s)", (role_id, perm_id))

    conn.commit()
    conn.close()

    # 记录审计日志
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    payload = verify_token(token)
    admin_id = payload['user_id'] if payload else None
    if admin_id:
        audit_log(admin_id, 'update_role_permissions', f"更新角色ID {role_id} 的权限，新权限ID列表: {data['permission_ids']}", _get_client_ip())

    return jsonify({'code': 200, 'msg': '权限更新成功'})


@admin_bp.route('/api/admin/users/<int:user_id>/password', methods=['PUT'])
@role_required(['admin'])
def reset_user_password(user_id):
    """管理员重置指定用户的密码"""
    data = request.get_json()
    if 'password' not in data:
        return jsonify({'code': 400, 'msg': '缺少新密码'}), 400

    new_password = data['password']
    from backend.api.v1.auth import validate_password
    err = validate_password(new_password)
    if err:
        return jsonify({'code': 400, 'msg': err}), 400

    user = User.find_by_id(user_id)
    if not user:
        return jsonify({'code': 404, 'msg': '用户不存在'}), 404

    user.password_hash = hash_password(new_password)
    user.plain_password = new_password
    user.save()

    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    payload = verify_token(token)
    admin_id = payload['user_id'] if payload else None
    if admin_id:
        audit_log(admin_id, 'reset_password', f"重置用户ID {user_id} ({user.username}) 的密码", _get_client_ip())

    return jsonify({'code': 200, 'msg': '密码重置成功'})


@admin_bp.route('/api/admin/permissions', methods=['GET'])
@role_required(['admin'])
def get_permissions():
    """获取所有权限列表（用于前端权限勾选展示）"""
    conn = get_db_conn()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    cursor.execute("SELECT * FROM permissions ORDER BY id")
    permissions = cursor.fetchall()

    conn.close()

    return jsonify({'code': 200, 'data': permissions})


@admin_bp.route('/api/admin/vip-applications', methods=['GET'])
@role_required(['admin'])
def get_vip_applications():
    """获取VIP申请列表（含申请人信息）"""
    conn = get_db_conn()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("""
        SELECT va.*, u.username, u.email
        FROM vip_applications va
        JOIN users u ON va.user_id = u.id
        ORDER BY va.created_at DESC
    """)
    applications = cursor.fetchall()
    conn.close()
    return jsonify({'code': 200, 'data': applications})


@admin_bp.route('/api/admin/vip-applications/<int:user_id>/approve', methods=['PUT'])
@role_required(['admin'])
def approve_vip(user_id):
    """审批通过VIP申请：将用户角色改为vip"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    payload = verify_token(token)
    admin_id = payload['user_id'] if payload else None

    user = User.find_by_id(user_id)
    if not user:
        return jsonify({'code': 404, 'msg': '用户不存在'}), 404

    role = Role.find_by_name('vip')
    if not role:
        return jsonify({'code': 500, 'msg': 'VIP角色不存在'}), 500

    conn = get_db_conn()
    cursor = conn.cursor()

    # 替换角色：先删旧的，再插入VIP
    cursor.execute("DELETE FROM user_roles WHERE user_id = %s", (user_id,))
    cursor.execute("INSERT INTO user_roles (user_id, role_id) VALUES (%s, %s)", (user_id, role.id))

    # 更新申请表状态
    cursor.execute("""
        UPDATE vip_applications SET status = 'approved', handled_by = %s
        WHERE user_id = %s AND status = 'pending'
    """, (admin_id, user_id))

    conn.commit()
    conn.close()

    # 记录审计日志
    if admin_id:
        audit_log(admin_id, 'approve_vip', f"审批通过用户ID {user_id} 的VIP申请", _get_client_ip())

    return jsonify({'code': 200, 'msg': 'VIP审批通过'})


@admin_bp.route('/api/admin/vip-applications/<int:user_id>/reject', methods=['PUT'])
@role_required(['admin'])
def reject_vip(user_id):
    """拒绝VIP申请"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    payload = verify_token(token)
    admin_id = payload['user_id'] if payload else None

    data = request.get_json() or {}

    conn = get_db_conn()
    cursor = conn.cursor()
    cursor.execute("""
        UPDATE vip_applications SET status = 'rejected', handled_by = %s, remark = %s
        WHERE user_id = %s AND status = 'pending'
    """, (admin_id, data.get('remark', ''), user_id))
    conn.commit()
    conn.close()

    # 记录审计日志
    if admin_id:
        audit_log(admin_id, 'reject_vip', f"拒绝用户ID {user_id} 的VIP申请，备注: {data.get('remark', '')}", _get_client_ip())

    return jsonify({'code': 200, 'msg': '已拒绝VIP申请'})
