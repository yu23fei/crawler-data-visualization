# auth.py - 认证与授权中间件模块
# 提供三个装饰器用于接口的访问控制：
#   token_required   → 仅验证令牌有效性（已登录即可）
#   role_required    → 验证令牌 + 检查用户角色是否在允许列表中
#   permission_required → 验证令牌 + 检查用户是否拥有特定权限
#
# 使用示例：
#   @token_required           → 登录用户可访问
#   @role_required(['admin']) → 只有管理员可访问
#   @permission_required('manage_users') → 拥有"管理用户"权限可访问

from functools import wraps
from flask import request, jsonify

from backend.models.user import User
from backend.utils.security import verify_token


def token_required(f):
    """
    JWT令牌验证装饰器
    从请求头 Authorization 中提取 Bearer Token，验证其有效性
    验证通过后将用户信息注入 request.current_user 供下游使用
    适用场景：需要登录才能访问的接口
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        # 从请求头提取JWT令牌（格式：Bearer <token>）
        token = request.headers.get('Authorization', '').replace('Bearer ', '')

        if not token:
            return jsonify({'code': 401, 'msg': '未提供认证令牌'}), 401

        # 验证令牌签名和有效期
        payload = verify_token(token)
        if not payload:
            return jsonify({'code': 401, 'msg': '令牌无效或已过期'}), 401

        # 将解析出的用户信息挂载到request对象，后续视图函数可直接使用
        request.current_user = {
            'user_id': payload['user_id'],
            'username': payload['username'],
            'role': payload['role']
        }

        return f(*args, **kwargs)
    return decorated


def role_required(allowed_roles):
    """
    角色验证装饰器（装饰器工厂模式）
    先验证JWT令牌，再检查用户角色是否在允许列表中
    适用场景：需要特定角色才能访问的接口（如仅管理员可操作）
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # 第一步：验证JWT令牌
            token = request.headers.get('Authorization', '').replace('Bearer ', '')

            if not token:
                return jsonify({'code': 401, 'msg': '未提供认证令牌'}), 401

            payload = verify_token(token)
            if not payload:
                return jsonify({'code': 401, 'msg': '令牌无效或已过期'}), 401

            # 第二步：检查角色是否在白名单内
            if payload['role'] not in allowed_roles:
                return jsonify({'code': 403, 'msg': '权限不足'}), 403

            # 注入用户信息到请求上下文
            request.current_user = {
                'user_id': payload['user_id'],
                'username': payload['username'],
                'role': payload['role']
            }

            return f(*args, **kwargs)
        return decorated
    return decorator


def permission_required(permission_name):
    """
    权限验证装饰器（装饰器工厂模式，最细粒度的访问控制）
    先验证JWT令牌，再查询用户拥有的权限列表，检查是否包含所需权限
    适用场景：需要特定操作权限的接口（如仅限"管理用户"权限的操作）
    """
    def decorator(f):
        @wraps(f)
        def decorated(*args, **kwargs):
            # 第一步：验证JWT令牌
            token = request.headers.get('Authorization', '').replace('Bearer ', '')

            if not token:
                return jsonify({'code': 401, 'msg': '未提供认证令牌'}), 401

            payload = verify_token(token)
            if not payload:
                return jsonify({'code': 401, 'msg': '令牌无效或已过期'}), 401

            # 第二步：从数据库查询用户实例并检查权限
            user = User.find_by_id(payload['user_id'])
            if not user:
                return jsonify({'code': 404, 'msg': '用户不存在'}), 404

            # 通过角色→权限关联链查询用户是否拥有该权限
            if not user.has_permission(permission_name):
                return jsonify({'code': 403, 'msg': '权限不足'}), 403

            # 注入用户信息到请求上下文
            request.current_user = {
                'user_id': payload['user_id'],
                'username': payload['username'],
                'role': payload['role']
            }

            return f(*args, **kwargs)
        return decorated
    return decorator