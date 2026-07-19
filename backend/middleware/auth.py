"""认证与授权中间件模块

提供三个装饰器用于接口的访问控制：
  - token_required      仅验证令牌有效性（已登录即可）
  - role_required       验证令牌 + 检查用户角色是否在允许列表中
  - permission_required 验证令牌 + 检查用户是否拥有特定权限
"""

from functools import wraps

from flask import request, jsonify

from backend.models.user import User
from backend.utils.security import verify_token


def token_required(f):
    """JWT令牌验证装饰器

    从请求头 Authorization 中提取 Bearer Token，验证其有效性。
    验证通过后将用户信息注入 request.current_user 供下游使用。
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization', '').replace('Bearer ', '')
        if not token:
            return jsonify({'code': 401, 'msg': '未提供认证令牌'}), 401
        payload = verify_token(token)
        if not payload:
            return jsonify({'code': 401, 'msg': '令牌无效或已过期'}), 401
        request.current_user = {
            'user_id': payload['user_id'],
            'username': payload['username'],
            'role': payload['role']
        }
        return f(*args, **kwargs)
    return decorated


def role_required(allowed_roles):
    """角色验证装饰器（装饰器工厂模式）

    先验证 JWT 令牌，再检查用户角色是否在允许列表中。
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            token = request.headers.get('Authorization', '').replace('Bearer ', '')
            if not token:
                return jsonify({'code': 401, 'msg': '未提供认证令牌'}), 401
            payload = verify_token(token)
            if not payload:
                return jsonify({'code': 401, 'msg': '令牌无效或已过期'}), 401
            if payload['role'] not in allowed_roles:
                return jsonify({'code': 403, 'msg': '权限不足'}), 403
            request.current_user = {
                'user_id': payload['user_id'],
                'username': payload['username'],
                'role': payload['role']
            }
            return f(*args, **kwargs)
        return decorated
    return decorator


def permission_required(permission_name):
    """权限验证装饰器（装饰器工厂模式，最细粒度的访问控制）"""
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            token = request.headers.get('Authorization', '').replace('Bearer ', '')
            if not token:
                return jsonify({'code': 401, 'msg': '未提供认证令牌'}), 401
            payload = verify_token(token)
            if not payload:
                return jsonify({'code': 401, 'msg': '令牌无效或已过期'}), 401
            user = User.find_by_id(payload['user_id'])
            if not user:
                return jsonify({'code': 404, 'msg': '用户不存在'}), 404
            if not user.has_permission(permission_name):
                return jsonify({'code': 403, 'msg': '权限不足'}), 403
            request.current_user = {
                'user_id': payload['user_id'],
                'username': payload['username'],
                'role': payload['role']
            }
            return f(*args, **kwargs)
        return decorated
    return decorator
