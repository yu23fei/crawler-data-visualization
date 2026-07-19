"""认证接口模块

提供用户注册、登录、密码重置、个人信息查询等认证相关接口。
所有密码和安全答案均经过 bcrypt 加密存储。
登录成功后返回 JWT 令牌，后续请求需在 Header 中携带 Authorization: Bearer <token>。
"""

import re
import time
from collections import defaultdict

import pymysql
from flask import Blueprint, request, jsonify

from backend.core.config import Config
from backend.models.user import User
from backend.models.role import Role
from backend.utils.security import hash_password, verify_password, generate_token, verify_token, audit_log, add_to_blacklist

auth_bp = Blueprint('auth', __name__)

_rate_limit_store = defaultdict(lambda: defaultdict(list))


def _check_rate_limit(endpoint_key, ip, max_requests, window_seconds):
    """检查指定IP在时间窗口内的请求次数是否超限"""
    now = time.time()
    window_start = now - window_seconds
    requests_list = _rate_limit_store[endpoint_key][ip]
    _rate_limit_store[endpoint_key][ip] = [t for t in requests_list if t > window_start]
    if len(_rate_limit_store[endpoint_key][ip]) >= max_requests:
        return False
    _rate_limit_store[endpoint_key][ip].append(now)
    return True


def _get_client_ip():
    """获取客户端真实IP，优先从反向代理头获取"""
    forwarded = request.headers.get('X-Forwarded-For', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.remote_addr or '127.0.0.1'


def _get_db_conn():
    """获取数据库连接（临时，后续迁移至 database 工具模块）"""
    conn = pymysql.connect(
        host=Config.DB_HOST, port=Config.DB_PORT,
        user=Config.DB_USER, password=Config.DB_PASSWORD,
        database=Config.DB_NAME, charset='utf8mb4'
    )
    return conn


def validate_username(v):
    """校验用户名格式：3-30个字符，仅含字母数字中文下划线"""
    if not v or len(v) < 3 or len(v) > 30:
        return '用户名需3-30个字符'
    if not re.match(r'^[a-zA-Z0-9_\u4e00-\u9fff]+$', v):
        return '用户名只能包含字母、数字、中文和下划线'
    return None


def validate_password(v):
    """增强密码复杂度校验：长度8-64，须包含大小写字母和数字"""
    if not v or len(v) < 8 or len(v) > 64:
        return '密码需8-64个字符'
    if not re.search(r'[A-Z]', v):
        return '密码必须包含至少一个大写字母'
    if not re.search(r'[a-z]', v):
        return '密码必须包含至少一个小写字母'
    if not re.search(r'[0-9]', v):
        return '密码必须包含至少一个数字'
    return None


def validate_email(v):
    """校验邮箱格式"""
    if not v:
        return None
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', v):
        return '邮箱格式不正确'
    return None


@auth_bp.route('/api/auth/register', methods=['POST'])
def register():
    """用户注册接口

    请求体：username, password, security_question, security_answer
    注册成功后默认分配 guest 角色。
    """
    data = request.get_json()
    if not data:
        return jsonify({'code': 400, 'msg': '请求数据为空'}), 400

    required = ['username', 'password', 'security_question', 'security_answer']
    for field in required:
        if field not in data or not data[field]:
            return jsonify({'code': 400, 'msg': f'缺少必填字段: {field}'}), 400

    err = validate_username(data['username'])
    if err:
        return jsonify({'code': 400, 'msg': err}), 400
    err = validate_password(data['password'])
    if err:
        return jsonify({'code': 400, 'msg': err}), 400

    existing_user = User.find_by_username(data['username'])
    if existing_user:
        return jsonify({'code': 400, 'msg': '用户名已存在'}), 400

    user = User(
        username=data['username'],
        password_hash=hash_password(data['password']),
        email=data.get('email'),
        phone=data.get('phone'),
        security_question=data['security_question'],
        security_answer=hash_password(data['security_answer']),
        status='active'
    )
    user.save()

    role = Role.find_by_name('guest')
    if role:
        conn = _get_db_conn()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT IGNORE INTO user_roles (user_id, role_id) VALUES (%s, %s)",
            (user.id, role.id)
        )
        conn.commit()
        conn.close()

    return jsonify({'code': 200, 'msg': '注册成功'})


@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    """用户登录接口

    验证用户名密码，返回 JWT 令牌。
    登录失败超过限制时触发限流。
    """
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'code': 400, 'msg': '请提供用户名和密码'}), 400

    client_ip = _get_client_ip()
    if not _check_rate_limit('login', client_ip, Config.LOGIN_RATE_LIMIT, 60):
        return jsonify({'code': 429, 'msg': '登录尝试过于频繁，请稍后再试'}), 429

    user = User.find_by_username(data['username'])
    if not user:
        audit_log(None, 'login_failed', f"用户名不存在: {data['username']}", client_ip)
        return jsonify({'code': 401, 'msg': '用户名或密码错误'}), 401

    if user.status == 'disabled':
        return jsonify({'code': 403, 'msg': '账户已被禁用，请联系管理员'}), 403

    if not verify_password(data['password'], user.password_hash):
        audit_log(user.id, 'login_failed', '密码错误', client_ip)
        return jsonify({'code': 401, 'msg': '用户名或密码错误'}), 401

    roles = user.get_roles()
    role_name = roles[0]['name'] if roles else 'guest'
    token = generate_token(user.id, user.username, role_name)

    audit_log(user.id, 'login', '用户登录成功', client_ip)
    return jsonify({
        'code': 200,
        'msg': '登录成功',
        'token': token,
        'username': user.username,
        'role': role_name
    })


@auth_bp.route('/api/auth/profile', methods=['GET'])
def get_profile():
    """获取当前用户个人信息"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    payload = verify_token(token)
    if not payload:
        return jsonify({'code': 401, 'msg': '未登录或令牌已过期'}), 401

    user = User.find_by_id(payload['user_id'])
    if not user:
        return jsonify({'code': 404, 'msg': '用户不存在'}), 404

    user_data = user.to_dict()
    roles = user.get_roles()
    user_data['role'] = roles[0]['name'] if roles else 'guest'
    user_data['permissions'] = user.get_permissions()
    user_data.pop('password_hash', None)
    user_data.pop('security_answer', None)
    return jsonify({'code': 200, 'data': user_data})


@auth_bp.route('/api/auth/update-profile', methods=['PUT'])
def update_profile():
    """更新当前用户个人信息"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    payload = verify_token(token)
    if not payload:
        return jsonify({'code': 401, 'msg': '未登录或令牌已过期'}), 401

    data = request.get_json()
    if not data:
        return jsonify({'code': 400, 'msg': '请求数据为空'}), 400

    user = User.find_by_id(payload['user_id'])
    if not user:
        return jsonify({'code': 404, 'msg': '用户不存在'}), 404

    if 'email' in data and data['email']:
        err = validate_email(data['email'])
        if err:
            return jsonify({'code': 400, 'msg': err}), 400
        user.email = data['email']
    if 'phone' in data:
        user.phone = data['phone']
    if 'security_question' in data and 'security_answer' in data:
        user.security_question = data['security_question']
        user.security_answer = hash_password(data['security_answer'])

    user.save()
    return jsonify({'code': 200, 'msg': '个人信息已更新'})


@auth_bp.route('/api/auth/change-password', methods=['PUT'])
def change_password():
    """修改当前用户密码"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    payload = verify_token(token)
    if not payload:
        return jsonify({'code': 401, 'msg': '未登录或令牌已过期'}), 401

    data = request.get_json()
    if not data or not data.get('old_password') or not data.get('new_password'):
        return jsonify({'code': 400, 'msg': '请提供原密码和新密码'}), 400

    client_ip = _get_client_ip()
    if not _check_rate_limit('change_password', client_ip, Config.RESET_RATE_LIMIT, 60):
        return jsonify({'code': 429, 'msg': '操作过于频繁，请稍后再试'}), 429

    user = User.find_by_id(payload['user_id'])
    if not user:
        return jsonify({'code': 404, 'msg': '用户不存在'}), 404

    if not verify_password(data['old_password'], user.password_hash):
        return jsonify({'code': 400, 'msg': '原密码错误'}), 400

    err = validate_password(data['new_password'])
    if err:
        return jsonify({'code': 400, 'msg': err}), 400

    user.password_hash = hash_password(data['new_password'])
    user.save()

    add_to_blacklist(token)
    return jsonify({'code': 200, 'msg': '密码修改成功，请重新登录'})


@auth_bp.route('/api/auth/reset-password', methods=['POST'])
def reset_password():
    """通过密保问题重置密码"""
    data = request.get_json()
    if not data or not data.get('username') or not data.get('security_answer') or not data.get('new_password'):
        return jsonify({'code': 400, 'msg': '请提供用户名、安全答案和新密码'}), 400

    client_ip = _get_client_ip()
    if not _check_rate_limit('reset_password', client_ip, Config.RESET_RATE_LIMIT, 60):
        return jsonify({'code': 429, 'msg': '操作过于频繁，请稍后再试'}), 429

    user = User.find_by_username(data['username'])
    if not user:
        return jsonify({'code': 404, 'msg': '用户不存在'}), 404

    if not verify_password(data['security_answer'], user.security_answer):
        return jsonify({'code': 400, 'msg': '安全答案错误'}), 400

    err = validate_password(data['new_password'])
    if err:
        return jsonify({'code': 400, 'msg': err}), 400

    user.password_hash = hash_password(data['new_password'])
    user.save()

    return jsonify({'code': 200, 'msg': '密码重置成功，请使用新密码登录'})
