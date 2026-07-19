# auth.py - 认证接口模块
# 提供用户注册、登录、密码重置、个人信息查询等认证相关接口
# 所有密码和安全答案均经过bcrypt加密存储
# 登录成功后返回JWT令牌，后续请求需在Header中携带 Authorization: Bearer <token>

from flask import Blueprint, request, jsonify
import pymysql
import time
from collections import defaultdict

from backend.models.user import User
from backend.models.role import Role
from backend.utils.security import hash_password, verify_password, generate_token, verify_token
from backend.core.config import Config
import re

# 创建认证蓝图，后续在main.py中注册
auth_bp = Blueprint('auth', __name__)


# ==================== 简易内存限流器 ====================
# 生产环境建议替换为 Redis 限流方案
# 存储结构：{ endpoint_key: { ip: [(timestamp, timestamp, ...)] } }
_rate_limit_store = defaultdict(lambda: defaultdict(list))


def _check_rate_limit(endpoint_key, ip, max_requests, window_seconds):
    """
    检查指定IP在时间窗口内的请求次数是否超限
    返回 True 表示可以继续，False 表示已被限流
    """
    now = time.time()
    window_start = now - window_seconds
    # 清理过期的时间戳记录
    requests_list = _rate_limit_store[endpoint_key][ip]
    _rate_limit_store[endpoint_key][ip] = [t for t in requests_list if t > window_start]
    # 判断是否超限
    if len(_rate_limit_store[endpoint_key][ip]) >= max_requests:
        return False
    # 记录本次请求
    _rate_limit_store[endpoint_key][ip].append(now)
    return True


def _get_client_ip():
    """获取客户端真实IP，优先从反向代理头获取"""
    forwarded = request.headers.get('X-Forwarded-For', '')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.remote_addr or '127.0.0.1'


def validate_username(v):
    """校验用户名格式：3-30个字符，仅含字母数字中文下划线"""
    if not v or len(v) < 3 or len(v) > 30:
        return '用户名需3-30个字符'
    if not re.match(r'^[a-zA-Z0-9_一-龥]+$', v):
        return '用户名只能包含字母、数字、中文和下划线'
    return None


def validate_password(v):
    """
    增强密码复杂度校验：
      - 长度 8-64 个字符
      - 必须包含大写字母、小写字母、数字
    """
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
    if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', v):
        return '邮箱格式不正确'
    return None


def validate_phone(v):
    """校验手机号格式"""
    if not v:
        return None
    if not re.match(r'^1\d{10}$', v):
        return '手机号格式不正确'
    return None


def validate_question(v):
    """校验安全问题长度"""
    if not v or len(v) < 2 or len(v) > 200:
        return '安全问题需2-200个字符'
    return None


def validate_answer(v):
    """校验安全答案长度"""
    if not v or len(v) < 2 or len(v) > 200:
        return '安全答案需2-200个字符'
    return None


# ==================== 登录失败锁定 ====================
# 生产环境建议替换为 Redis 方案
# 存储结构：{ username: (fail_count, first_fail_timestamp, locked_until) }
_login_failures = {}


def _check_login_lockout(username):
    """
    检查账户是否因多次登录失败被临时锁定
    锁定策略：连续5次失败后锁定15分钟
    返回 (is_locked: bool, remaining_seconds: int)
    """
    if username not in _login_failures:
        return False, 0
    fail_count, first_fail, locked_until = _login_failures[username]
    now = time.time()
    if locked_until and now < locked_until:
        return True, int(locked_until - now)
    # 锁定已过期，清理记录
    if locked_until and now >= locked_until:
        del _login_failures[username]
    # 超过15分钟重置失败计数
    if now - first_fail > 900:
        del _login_failures[username]
    return False, 0


def _record_login_failure(username):
    """记录一次失败的登录尝试"""
    now = time.time()
    if username in _login_failures:
        fail_count, first_fail, _ = _login_failures[username]
        fail_count += 1
        if fail_count >= 5:
            _login_failures[username] = (fail_count, first_fail, now + 900)
        else:
            _login_failures[username] = (fail_count, first_fail, None)
    else:
        _login_failures[username] = (1, now, None)


def _clear_login_failures(username):
    """登录成功后清除失败记录"""
    _login_failures.pop(username, None)


def get_db_conn():
    """获取数据库连接"""
    return pymysql.connect(
        host=Config.DB_HOST, port=Config.DB_PORT, user=Config.DB_USER,
        password=Config.DB_PASSWORD, database=Config.DB_NAME, charset='utf8mb4'
    )


@auth_bp.route('/api/auth/register', methods=['POST'])
def register():
    """
    用户注册接口
    请求体需包含: username, password, security_question, security_answer
    可选字段: email, phone
    注册后直接激活，默认为普通用户(guest)角色
    """
    data = request.get_json()

    # 校验必填字段
    required_fields = ['username', 'password', 'security_question', 'security_answer']
    for field in required_fields:
        if field not in data:
            return jsonify({'code': 400, 'msg': f'缺少必填字段: {field}'}), 400

    # 输入合法性校验
    err = validate_username(data['username'])
    if err:
        return jsonify({'code': 400, 'msg': err}), 400
    err = validate_password(data['password'])
    if err:
        return jsonify({'code': 400, 'msg': err}), 400
    err = validate_email(data.get('email'))
    if err:
        return jsonify({'code': 400, 'msg': err}), 400
    err = validate_phone(data.get('phone'))
    if err:
        return jsonify({'code': 400, 'msg': err}), 400
    err = validate_question(data['security_question'])
    if err:
        return jsonify({'code': 400, 'msg': err}), 400
    err = validate_answer(data['security_answer'])
    if err:
        return jsonify({'code': 400, 'msg': err}), 400

    # 检查用户名唯一性
    existing_user = User.find_by_username(data['username'])
    if existing_user:
        return jsonify({'code': 400, 'msg': '用户名已存在'}), 400

    # 创建用户对象（密码和安全答案均使用bcrypt加密，同时保存明文供管理员查看）
    user = User(
        username=data['username'],
        password_hash=hash_password(data['password']),
        plain_password=data['password'],
        email=data.get('email'),
        phone=data.get('phone'),
        security_question=data['security_question'],
        security_answer=hash_password(data['security_answer']),
        status='active'
    )
    user.save()

    # 自动分配 guest（普通用户）角色
    role = Role.find_by_name('guest')
    if role:
        conn = get_db_conn()
        cursor = conn.cursor()
        cursor.execute("INSERT IGNORE INTO user_roles (user_id, role_id) VALUES (%s, %s)", (user.id, role.id))
        conn.commit()
        conn.close()

    return jsonify({'code': 200, 'msg': '注册成功'})


@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    """
    用户登录接口
    包含限流（每IP每分钟5次）和账户锁定（5次失败锁15分钟）
    流程：校验输入 -> 检查限流 -> 检查锁定 -> 验证密码 -> 生成JWT
    """
    # 请求频率限制（每IP每分钟最多5次登录尝试）
    client_ip = _get_client_ip()
    if not _check_rate_limit('login', client_ip, Config.LOGIN_RATE_LIMIT, 60):
        return jsonify({'code': 429, 'msg': '请求过于频繁，请稍后重试'}), 429

    data = request.get_json()

    # 校验必填字段
    if 'username' not in data or 'password' not in data:
        return jsonify({'code': 400, 'msg': '用户名和密码不能为空'}), 400

    username = data.get('username', '').strip()
    password = data.get('password', '')

    # 输入合法性校验
    err = validate_username(username)
    if err:
        return jsonify({'code': 400, 'msg': err}), 400
    if not password:
        return jsonify({'code': 400, 'msg': '密码不能为空'}), 400

    # 检查账户是否因多次登录失败被临时锁定（防暴力破解）
    is_locked, remaining = _check_login_lockout(username)
    if is_locked:
        minutes = max(1, remaining // 60)
        return jsonify({'code': 429, 'msg': f'账户已被临时锁定，请{minutes}分钟后再试'}), 429

    # 第一步：查找用户（不存在时返回统一错误，防用户名枚举）
    user = User.find_by_username(username)
    if not user:
        _record_login_failure(username)
        return jsonify({'code': 401, 'msg': '用户名或密码错误'}), 401

    # 第二步：验证密码（bcrypt比对）
    if not verify_password(password, user.password_hash):
        _record_login_failure(username)
        return jsonify({'code': 401, 'msg': '用户名或密码错误'}), 401

    # 第三步：检查账户状态（只有 active 状态的用户才能登录）
    if user.status != 'active':
        return jsonify({'code': 403, 'msg': '账户未激活或已被禁用'}), 403

    # 第四步：获取用户角色列表
    roles = user.get_roles()
    if not roles:
        return jsonify({'code': 403, 'msg': '用户没有分配角色'}), 403

    # 登录成功，清除失败计数
    _clear_login_failures(username)

    # 使用第一个角色（当前版本每个用户只有一个角色）
    role_name = roles[0]['name']

    # 第五步：生成JWT令牌（包含用户ID、用户名、角色，有效期24小时）
    token = generate_token(user.id, user.username, role_name)

    return jsonify({
        'code': 200,
        'msg': '登录成功',
        'data': {
            'token': token,
            'user': user.to_dict(),
            'role': role_name
        }
    })


@auth_bp.route('/api/auth/reset-password', methods=['POST'])
def reset_password():
    """
    密码重置接口（通过密保问题验证身份）
    包含限流（每IP每分钟3次）
    修复了用户名枚举漏洞：无论用户是否存在，返回统一的消息格式
    """
    # 请求频率限制
    client_ip = _get_client_ip()
    if not _check_rate_limit('reset_password', client_ip, Config.RESET_RATE_LIMIT, 60):
        return jsonify({'code': 429, 'msg': '请求过于频繁，请稍后重试'}), 429

    data = request.get_json()

    # 校验必填字段
    required_fields = ['username', 'security_answer', 'new_password']
    for field in required_fields:
        if field not in data:
            return jsonify({'code': 400, 'msg': f'缺少必填字段: {field}'}), 400

    # 输入合法性校验
    err = validate_username(data['username'])
    if err:
        return jsonify({'code': 400, 'msg': err}), 400
    err = validate_password(data['new_password'])
    if err:
        return jsonify({'code': 400, 'msg': err}), 400
    err = validate_answer(data['security_answer'])
    if err:
        return jsonify({'code': 400, 'msg': err}), 400

    # 第一步：查找用户 —— 修复用户名枚举漏洞
    # 不存在时返回与「安全答案错误」相同的状态码和统一消息
    user = User.find_by_username(data['username'])
    if not user:
        return jsonify({'code': 401, 'msg': '身份验证失败，请检查输入信息'}), 401

    # 第二步：验证安全答案
    if not verify_password(data['security_answer'], user.security_answer):
        return jsonify({'code': 401, 'msg': '身份验证失败，请检查输入信息'}), 401

    # 第三步：更新密码（新密码不能和旧密码相同）
    if verify_password(data['new_password'], user.password_hash):
        return jsonify({'code': 400, 'msg': '新密码不能与旧密码相同'}), 400

    user.password_hash = hash_password(data['new_password'])
    user.save()

    return jsonify({'code': 200, 'msg': '密码重置成功'})


@auth_bp.route('/api/auth/apply-vip', methods=['POST'])
def apply_vip():
    """普通用户申请升级为VIP"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if not token:
        return jsonify({'code': 401, 'msg': '未登录'}), 401
    payload = verify_token(token)
    if not payload:
        return jsonify({'code': 401, 'msg': '令牌无效或已过期'}), 401

    user = User.find_by_id(payload['user_id'])
    if not user:
        return jsonify({'code': 404, 'msg': '用户不存在'}), 404

    roles = user.get_roles()
    role_names = [r['name'] for r in roles]

    if 'vip' in role_names:
        return jsonify({'code': 400, 'msg': '您已经是VIP用户'}), 400

    conn = get_db_conn()
    cursor = conn.cursor()
    # 检查是否已有待审批申请
    cursor.execute("SELECT status FROM vip_applications WHERE user_id = %s ORDER BY created_at DESC LIMIT 1", (user.id,))
    existing = cursor.fetchone()
    if existing and existing[0] == 'pending':
        conn.close()
        return jsonify({'code': 400, 'msg': '您已提交过申请，请等待管理员审批'}), 400

    cursor.execute("INSERT INTO vip_applications (user_id, status) VALUES (%s, 'pending')", (user.id,))
    conn.commit()
    conn.close()
    return jsonify({'code': 200, 'msg': 'VIP申请已提交，请等待管理员审批'})


@auth_bp.route('/api/auth/profile', methods=['GET'])
def get_profile():
    """
    获取当前登录用户个人信息
    从请求头提取JWT令牌，解析后查询用户详情、角色和权限
    """
    token = request.headers.get('Authorization', '').replace('Bearer ', '')

    if not token:
        return jsonify({'code': 401, 'msg': '未提供认证令牌'}), 401

    payload = verify_token(token)
    if not payload:
        return jsonify({'code': 401, 'msg': '令牌无效或已过期'}), 401

    user = User.find_by_id(payload['user_id'])
    if not user:
        return jsonify({'code': 404, 'msg': '用户不存在'}), 404

    return jsonify({
        'code': 200,
        'data': {
            'user': user.to_dict(),
            'roles': user.get_roles(),
            'permissions': user.get_permissions()
        }
    })
