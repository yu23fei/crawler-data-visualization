"""管理员接口模块

提供用户管理（列表、创建、删除、角色修改、状态变更）、角色管理和权限管理等后台功能。
所有接口均受 @role_required(['admin']) 保护，仅管理员可访问。
"""

from contextlib import closing

import pymysql
from flask import Blueprint, request, jsonify

from backend.core.config import Config
from backend.middleware.auth import role_required
from backend.models.user import User
from backend.models.role import Role
from backend.utils.security import hash_password, verify_token, audit_log

admin_bp = Blueprint('admin', __name__)


def _get_db_conn():
    """获取数据库连接"""
    conn = pymysql.connect(
        host=Config.DB_HOST, port=Config.DB_PORT,
        user=Config.DB_USER, password=Config.DB_PASSWORD,
        database=Config.DB_NAME, charset='utf8mb4'
    )
    return conn


def _get_client_ip():
    """获取客户端真实IP"""
    forwarded = request.headers.get('X-Forwarded-For', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.remote_addr or '127.0.0.1'


@admin_bp.route('/api/admin/users', methods=['GET'])
@role_required(['admin'])
def get_users():
    """获取用户列表（分页），关联查询每个用户的角色"""
    conn = _get_db_conn()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size

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

    required_fields = ['username', 'password', 'role_name']
    for field in required_fields:
        if field not in data or not data[field]:
            return jsonify({'code': 400, 'msg': f'缺少必填字段: {field}'}), 400

    existing = User.find_by_username(data['username'])
    if existing:
        return jsonify({'code': 400, 'msg': '用户名已存在'}), 400

    role = Role.find_by_name(data['role_name'])
    if not role:
        return jsonify({'code': 404, 'msg': '角色不存在'}), 404

    user = User(
        username=data['username'],
        password_hash=hash_password(data['password']),
        plain_password=data['password'],
        email=data.get('email'),
        phone=data.get('phone'),
        status=data.get('status', 'active')
    )
    user.save()

    conn = _get_db_conn()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO user_roles (user_id, role_id) VALUES (%s, %s)",
        (user.id, role.id)
    )
    conn.commit()
    conn.close()

    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    payload = verify_token(token)
    admin_id = payload['user_id'] if payload else None
    if admin_id:
        audit_log(admin_id, 'create_user',
                  f"创建用户 {data['username']} (角色: {data['role_name']})", _get_client_ip())

    return jsonify({'code': 200, 'msg': '用户创建成功', 'data': {'id': user.id}})


@admin_bp.route('/api/admin/users/<int:user_id>', methods=['DELETE'])
@role_required(['admin'])
def delete_user(user_id):
    """删除用户（级联删除 user_roles 关联记录）"""
    user = User.find_by_id(user_id)
    if not user:
        return jsonify({'code': 404, 'msg': '用户不存在'}), 404

    conn = _get_db_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_roles WHERE user_id = %s", (user_id,))
    cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
    conn.commit()
    conn.close()

    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    payload = verify_token(token)
    admin_id = payload['user_id'] if payload else None
    if admin_id:
        audit_log(admin_id, 'delete_user',
                  f"删除用户 {user.username} (ID: {user_id})", _get_client_ip())

    return jsonify({'code': 200, 'msg': '用户删除成功'})


@admin_bp.route('/api/admin/users/<int:user_id>/role', methods=['PUT'])
@role_required(['admin'])
def update_user_role(user_id):
    """修改用户角色"""
    data = request.get_json()
    if not data or 'role_name' not in data:
        return jsonify({'code': 400, 'msg': '缺少角色名称'}), 400

    user = User.find_by_id(user_id)
    if not user:
        return jsonify({'code': 404, 'msg': '用户不存在'}), 404

    role = Role.find_by_name(data['role_name'])
    if not role:
        return jsonify({'code': 404, 'msg': '角色不存在'}), 404

    conn = _get_db_conn()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM user_roles WHERE user_id = %s", (user_id,))
    cursor.execute(
        "INSERT INTO user_roles (user_id, role_id) VALUES (%s, %s)",
        (user_id, role.id)
    )
    conn.commit()
    conn.close()

    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    payload = verify_token(token)
    admin_id = payload['user_id'] if payload else None
    if admin_id:
        audit_log(admin_id, 'update_user_role',
                  f"修改用户 {user.username} 角色为 {data['role_name']}", _get_client_ip())

    return jsonify({'code': 200, 'msg': '角色修改成功'})


@admin_bp.route('/api/admin/users/<int:user_id>/role', methods=['GET'])
@role_required(['admin'])
def get_user_role(user_id):
    """获取指定用户的当前角色"""
    conn = _get_db_conn()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("""
        SELECT r.* FROM roles r
        JOIN user_roles ur ON r.id = ur.role_id
        WHERE ur.user_id = %s
    """, (user_id,))
    roles = cursor.fetchall()
    conn.close()

    return jsonify({
        'code': 200,
        'data': roles[0] if roles else None
    })


@admin_bp.route('/api/admin/users/<int:user_id>/status', methods=['PUT'])
@role_required(['admin'])
def toggle_user_status(user_id):
    """启用或禁用用户账户"""
    data = request.get_json()
    if not data or 'status' not in data:
        return jsonify({'code': 400, 'msg': '缺少状态值'}), 400

    valid_statuses = ['active', 'disabled', 'pending']
    if data['status'] not in valid_statuses:
        return jsonify({'code': 400, 'msg': f'无效状态，仅支持: {", ".join(valid_statuses)}'}), 400

    user = User.find_by_id(user_id)
    if not user:
        return jsonify({'code': 404, 'msg': '用户不存在'}), 404

    user.status = data['status']
    user.save()

    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    payload = verify_token(token)
    admin_id = payload['user_id'] if payload else None
    if admin_id:
        audit_log(admin_id, 'toggle_user_status',
                  f"{'启用' if data['status'] == 'active' else '禁用'}用户 {user.username}",
                  _get_client_ip())

    return jsonify({'code': 200, 'msg': '状态更新成功'})


@admin_bp.route('/api/admin/users/<int:user_id>/reset-password', methods=['PUT'])
@admin_bp.route('/api/admin/users/<int:user_id>/password', methods=['PUT'])  # 兼容前端路由
@role_required(['admin'])
def reset_user_password(user_id):
    """管理员重置指定用户的密码"""
    data = request.get_json()
    # 兼容前端字段名 password 和后端字段名 new_password
    new_password = data.get('password') or data.get('new_password')
    if not new_password:
        return jsonify({'code': 400, 'msg': '缺少新密码'}), 400

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
        audit_log(admin_id, 'reset_password',
                  f"重置用户ID {user_id} ({user.username}) 的密码", _get_client_ip())

    return jsonify({'code': 200, 'msg': '密码重置成功'})


@admin_bp.route('/api/admin/permissions', methods=['GET'])
@role_required(['admin'])
def get_permissions():
    """获取所有权限列表（用于前端权限勾选展示）"""
    conn = _get_db_conn()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM permissions ORDER BY id")
    permissions = cursor.fetchall()
    conn.close()

    result = []
    for p in permissions:
        result.append({
            'id': p['id'],
            'name': p['name'],
            'description': p['description'],
            'resource': p['resource'],
            'action': p['action']
        })

    return jsonify({'code': 200, 'data': result})


@admin_bp.route('/api/admin/roles', methods=['GET'])
@role_required(['admin'])
def get_roles():
    """获取所有角色列表及关联权限"""
    conn = _get_db_conn()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("SELECT * FROM roles ORDER BY id")
    roles = cursor.fetchall()
    conn.close()

    result = []
    for role in roles:
        role_obj = Role.find_by_id(role['id'])
        permissions = role_obj.get_permissions() if role_obj else []
        result.append({
            'id': role['id'],
            'name': role['name'],
            'description': role['description'],
            'permissions': [{'id': p['id'], 'name': p['name']} for p in permissions]
        })

    return jsonify({'code': 200, 'data': result})


@admin_bp.route('/api/admin/roles/<int:role_id>/permissions', methods=['PUT'])
@role_required(['admin'])
def update_role_permissions(role_id):
    """更新指定角色的权限（批量覆盖）"""
    data = request.get_json()
    if not data or 'permission_ids' not in data:
        return jsonify({'code': 400, 'msg': '缺少权限ID列表'}), 400

    permission_ids = data['permission_ids']
    if not isinstance(permission_ids, list):
        return jsonify({'code': 400, 'msg': '权限ID列表格式不正确'}), 400

    role = Role.find_by_id(role_id)
    if not role:
        return jsonify({'code': 404, 'msg': '角色不存在'}), 404

    conn = _get_db_conn()
    cursor = conn.cursor()

    cursor.execute("DELETE FROM role_permissions WHERE role_id = %s", (role_id,))
    for perm_id in permission_ids:
        cursor.execute(
            "INSERT INTO role_permissions (role_id, permission_id) VALUES (%s, %s)",
            (role_id, perm_id)
        )

    conn.commit()
    conn.close()

    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    payload = verify_token(token)
    admin_id = payload['user_id'] if payload else None
    if admin_id:
        audit_log(admin_id, 'update_role_permissions',
                  f"更新角色 {role.name} 的权限配置", _get_client_ip())

    return jsonify({'code': 200, 'msg': '权限更新成功'})


@admin_bp.route('/api/admin/vip-applications', methods=['GET'])
@role_required(['admin'])
def get_vip_applications():
    """获取VIP申请列表"""
    conn = _get_db_conn()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("""
        SELECT va.*, u.username
        FROM vip_applications va
        JOIN users u ON va.user_id = u.id
        ORDER BY va.created_at DESC
    """)
    applications = cursor.fetchall()
    conn.close()

    return jsonify({'code': 200, 'data': applications})


@admin_bp.route('/api/admin/vip-applications/<int:app_id>/approve', methods=['POST', 'PUT'])
@role_required(['admin'])
def approve_vip_application(app_id):
    """审批VIP申请（通过）

    兼容两种调用方式：
    - POST /api/admin/vip-applications/<app_id>/approve（app_id = 申请记录ID）
    - PUT  /api/admin/vip-applications/<user_id>/approve（user_id = 用户ID，前端传入）
    """
    conn = _get_db_conn()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    # 先尝试按申请记录ID查询
    cursor.execute("SELECT * FROM vip_applications WHERE id = %s", (app_id,))
    app = cursor.fetchone()

    # 如果按申请ID找不到，尝试按用户ID查找最新的 pending 申请
    if not app:
        cursor.execute(
            "SELECT * FROM vip_applications WHERE user_id = %s AND status = 'pending' "
            "ORDER BY created_at DESC LIMIT 1",
            (app_id,)
        )
        app = cursor.fetchone()

    if not app:
        conn.close()
        return jsonify({'code': 404, 'msg': '申请记录不存在'}), 404

    cursor.execute("UPDATE vip_applications SET status = 'approved' WHERE id = %s", (app_id,))

    cursor.execute("SELECT id FROM roles WHERE name = 'vip'")
    vip_role = cursor.fetchone()
    if vip_role:
        cursor.execute(
            "INSERT IGNORE INTO user_roles (user_id, role_id) VALUES (%s, %s)",
            (app['user_id'], vip_role['id'])
        )

    conn.commit()
    conn.close()

    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    payload = verify_token(token)
    admin_id = payload['user_id'] if payload else None
    if admin_id:
        audit_log(admin_id, 'approve_vip', f"批准用户ID {app['user_id']} 的VIP申请", _get_client_ip())

    return jsonify({'code': 200, 'msg': 'VIP申请已通过'})


@admin_bp.route('/api/admin/vip-applications/<int:app_id>/reject', methods=['POST', 'PUT'])
@role_required(['admin'])
def reject_vip_application(app_id):
    """拒绝VIP申请

    兼容两种调用方式：
    - POST /api/admin/vip-applications/<app_id>/reject（app_id = 申请记录ID）
    - PUT  /api/admin/vip-applications/<user_id>/reject（user_id = 用户ID，前端传入）
    """
    data = request.get_json()

    conn = _get_db_conn()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    # 先尝试按申请记录ID查询
    cursor.execute("SELECT * FROM vip_applications WHERE id = %s", (app_id,))
    app = cursor.fetchone()

    # 如果按申请ID找不到，尝试按用户ID查找最新的 pending 申请
    if not app:
        cursor.execute(
            "SELECT * FROM vip_applications WHERE user_id = %s AND status = 'pending' "
            "ORDER BY created_at DESC LIMIT 1",
            (app_id,)
        )
        app = cursor.fetchone()

    if not app:
        conn.close()
        return jsonify({'code': 404, 'msg': '申请记录不存在'}), 404

    remark = data.get('remark', '') if data else ''
    cursor.execute(
        "UPDATE vip_applications SET status = 'rejected', remark = %s WHERE id = %s",
        (remark, app_id)
    )
    conn.commit()
    conn.close()

    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    payload = verify_token(token)
    admin_id = payload['user_id'] if payload else None
    if admin_id:
        audit_log(admin_id, 'reject_vip', f"拒绝用户ID {app['user_id']} 的VIP申请", _get_client_ip())

    return jsonify({'code': 200, 'msg': 'VIP申请已拒绝'})


@admin_bp.route('/api/admin/users/<int:user_id>/logs', methods=['GET'])
@role_required(['admin'])
def get_user_logs_by_user(user_id):
    """获取指定用户的操作日志"""
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 50))
    offset = (page - 1) * size

    conn = _get_db_conn()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("""
        SELECT ul.*, u.username
        FROM user_logs ul
        LEFT JOIN users u ON ul.user_id = u.id
        WHERE ul.user_id = %s
        ORDER BY ul.created_at DESC
        LIMIT %s, %s
    """, (user_id, offset, size))
    logs = cursor.fetchall()

    cursor.execute(
        "SELECT COUNT(*) as total FROM user_logs WHERE user_id = %s",
        (user_id,)
    )
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


@admin_bp.route('/api/admin/user-logs', methods=['GET'])
@admin_bp.route('/api/admin/users/logs', methods=['GET'])  # 兼容前端路由
@role_required(['admin'])
def get_user_logs():
    """获取用户操作日志"""
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 50))
    offset = (page - 1) * size

    conn = _get_db_conn()
    cursor = conn.cursor(pymysql.cursors.DictCursor)
    cursor.execute("""
        SELECT ul.*, u.username
        FROM user_logs ul
        LEFT JOIN users u ON ul.user_id = u.id
        ORDER BY ul.created_at DESC
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
