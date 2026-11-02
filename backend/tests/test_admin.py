from unittest.mock import MagicMock, patch, ANY

import jwt
import pytest

from backend.tests.mock_data import (
    mock_user, mock_guest_role, mock_vip_role, mock_admin_role,
    mock_roles, mock_permissions, mock_vip_application, mock_user_log
)
from backend.core.config import Config
from backend.middleware.auth import role_required
from backend.tests.conftest import _make_token


class TestAdminUsersList:
    """GET /api/admin/users"""

    def test_list_users_success(self, client, mock_db, admin_auth_header):
        mock_db['cursor'].fetchall.return_value = [dict(mock_user, roles='guest')]

        def fetchone_side_effect():
            return {'total': 1}
        mock_db['cursor'].fetchone.side_effect = fetchone_side_effect

        resp = client.get('/api/admin/users', headers=admin_auth_header)
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['code'] == 200
        assert len(data['data']['users']) == 1

    def test_list_users_no_auth(self, client, mock_db):
        resp = client.get('/api/admin/users')
        assert resp.status_code == 401

    def test_list_users_forbidden_guest(self, client, mock_db, auth_header):
        resp = client.get('/api/admin/users', headers=auth_header)
        assert resp.status_code == 403


class TestAdminCreateUser:
    """POST /api/admin/users"""

    def test_create_user_success(self, client, mock_db, admin_auth_header):
        mock_db['cursor'].lastrowid = 10

        with patch('backend.models.user.User.find_by_username', return_value=None):
            with patch('backend.models.role.Role.find_by_name', return_value=MagicMock(id=1, name='guest')):
                with patch('backend.models.user.User.save', return_value=MagicMock(id=10)):
                    resp = client.post('/api/admin/users', headers=admin_auth_header, json={
                        'username': 'newuser',
                        'password': 'StrongPass1',
                        'role_name': 'guest'
                    })
        assert resp.status_code == 200
        assert resp.get_json()['msg'] == '用户创建成功'

    def test_create_user_missing_fields(self, client, mock_db, admin_auth_header):
        resp = client.post('/api/admin/users', headers=admin_auth_header, json={
            'username': 'newuser'
        })
        assert resp.status_code == 400

    def test_create_user_duplicate(self, client, mock_db, admin_auth_header):
        with patch('backend.models.user.User.find_by_username', return_value=mock_user):
            resp = client.post('/api/admin/users', headers=admin_auth_header, json={
                'username': 'testuser',
                'password': 'StrongPass1',
                'role_name': 'guest'
            })
        assert resp.status_code == 400
        assert '已存在' in resp.get_json()['msg']

    def test_create_user_role_not_found(self, client, mock_db, admin_auth_header):
        with patch('backend.models.user.User.find_by_username', return_value=None):
            with patch('backend.models.role.Role.find_by_name', return_value=None):
                resp = client.post('/api/admin/users', headers=admin_auth_header, json={
                    'username': 'newuser',
                    'password': 'StrongPass1',
                    'role_name': 'nonexistent'
                })
        assert resp.status_code == 404


class TestAdminDeleteUser:
    """DELETE /api/admin/users/<id>"""

    def test_delete_user_success(self, client, mock_db, admin_auth_header):
        with patch('backend.models.user.User.find_by_id', return_value=MagicMock(id=1, username='testuser')):
            resp = client.delete('/api/admin/users/1', headers=admin_auth_header)
        assert resp.status_code == 200
        assert resp.get_json()['msg'] == '用户删除成功'

    def test_delete_user_not_found(self, client, mock_db, admin_auth_header):
        with patch('backend.models.user.User.find_by_id', return_value=None):
            resp = client.delete('/api/admin/users/999', headers=admin_auth_header)
        assert resp.status_code == 404


class TestAdminUpdateUserRole:
    """PUT /api/admin/users/<id>/role"""

    def test_update_role_success(self, client, mock_db, admin_auth_header):
        with patch('backend.models.user.User.find_by_id', return_value=MagicMock(id=1, username='testuser')):
            with patch('backend.models.role.Role.find_by_name', return_value=MagicMock(id=2, name='vip')):
                resp = client.put('/api/admin/users/1/role', headers=admin_auth_header, json={
                    'role_name': 'vip'
                })
        assert resp.status_code == 200
        assert resp.get_json()['msg'] == '角色修改成功'

    def test_update_role_not_found(self, client, mock_db, admin_auth_header):
        with patch('backend.models.user.User.find_by_id', return_value=None):
            resp = client.put('/api/admin/users/999/role', headers=admin_auth_header, json={
                'role_name': 'vip'
            })
        assert resp.status_code == 404

    def test_update_role_invalid_role(self, client, mock_db, admin_auth_header):
        with patch('backend.models.user.User.find_by_id', return_value=MagicMock(id=1)):
            with patch('backend.models.role.Role.find_by_name', return_value=None):
                resp = client.put('/api/admin/users/1/role', headers=admin_auth_header, json={
                    'role_name': 'nonexistent'
                })
        assert resp.status_code == 404


class TestAdminGetUserRole:
    """GET /api/admin/users/<id>/role"""

    def test_get_user_role_success(self, client, mock_db, admin_auth_header):
        mock_db['cursor'].fetchall.return_value = [mock_vip_role]
        mock_db['cursor'].fetchone.return_value = mock_vip_role

        resp = client.get('/api/admin/users/1/role', headers=admin_auth_header)
        assert resp.status_code == 200
        assert resp.get_json()['data'] is not None

    def test_get_user_role_not_found(self, client, mock_db, admin_auth_header):
        mock_db['cursor'].fetchall.return_value = []
        mock_db['cursor'].fetchone.return_value = None

        resp = client.get('/api/admin/users/999/role', headers=admin_auth_header)
        assert resp.status_code == 200
        assert resp.get_json()['data'] is None


class TestAdminToggleUserStatus:
    """PUT /api/admin/users/<id>/status"""

    def test_toggle_status_active(self, client, mock_db, admin_auth_header):
        with patch('backend.models.user.User.find_by_id', return_value=MagicMock(id=1, username='testuser')):
            resp = client.put('/api/admin/users/1/status', headers=admin_auth_header, json={
                'status': 'disabled'
            })
        assert resp.status_code == 200
        assert resp.get_json()['msg'] == '状态更新成功'

    def test_toggle_status_invalid(self, client, mock_db, admin_auth_header):
        resp = client.put('/api/admin/users/1/status', headers=admin_auth_header, json={
            'status': 'invalid_status'
        })
        assert resp.status_code == 400

    def test_toggle_status_user_not_found(self, client, mock_db, admin_auth_header):
        with patch('backend.models.user.User.find_by_id', return_value=None):
            resp = client.put('/api/admin/users/999/status', headers=admin_auth_header, json={
                'status': 'active'
            })
        assert resp.status_code == 404


class TestAdminResetPassword:
    """PUT /api/admin/users/<id>/reset-password"""

    def test_reset_password_success(self, client, mock_db, admin_auth_header):
        with patch('backend.models.user.User.find_by_id', return_value=MagicMock(id=1, username='testuser')):
            resp = client.put('/api/admin/users/1/reset-password', headers=admin_auth_header, json={
                'new_password': 'NewStrongPass1'
            })
        assert resp.status_code == 200
        assert resp.get_json()['msg'] == '密码重置成功'

    def test_reset_password_compat_route(self, client, mock_db, admin_auth_header):
        with patch('backend.models.user.User.find_by_id', return_value=MagicMock(id=1, username='testuser')):
            resp = client.put('/api/admin/users/1/password', headers=admin_auth_header, json={
                'password': 'NewStrongPass1'
            })
        assert resp.status_code == 200

    def test_reset_password_user_not_found(self, client, mock_db, admin_auth_header):
        with patch('backend.models.user.User.find_by_id', return_value=None):
            resp = client.put('/api/admin/users/999/reset-password', headers=admin_auth_header, json={
                'new_password': 'NewStrongPass1'
            })
        assert resp.status_code == 404


class TestAdminPermissions:
    """GET /api/admin/permissions"""

    def test_get_permissions_success(self, client, mock_db, admin_auth_header):
        mock_db['cursor'].fetchall.return_value = mock_permissions

        resp = client.get('/api/admin/permissions', headers=admin_auth_header)
        data = resp.get_json()
        assert resp.status_code == 200
        assert len(data['data']) == 11


class TestAdminRoles:
    """GET /api/admin/roles"""

    def test_get_roles_success(self, client, mock_db, admin_auth_header):
        mock_db['cursor'].fetchall.return_value = mock_roles

        with patch('backend.models.role.Role.find_by_id') as mock_find:
            mock_role_obj = MagicMock()
            mock_role_obj.get_permissions.return_value = [
                {'id': 1, 'name': 'view_charts'}
            ]
            mock_find.return_value = mock_role_obj

            resp = client.get('/api/admin/roles', headers=admin_auth_header)
        data = resp.get_json()
        assert resp.status_code == 200
        assert len(data['data']) == 3
        assert data['data'][0]['name'] == 'guest'

    def test_get_roles_no_auth(self, client, mock_db):
        resp = client.get('/api/admin/roles')
        assert resp.status_code == 401


class TestAdminUpdateRolePermissions:
    """PUT /api/admin/roles/<id>/permissions"""

    def test_update_permissions_success(self, client, mock_db, admin_auth_header):
        with patch('backend.models.role.Role.find_by_id', return_value=MagicMock(id=1, name='guest')):
            resp = client.put('/api/admin/roles/1/permissions', headers=admin_auth_header, json={
                'permission_ids': [1, 2, 3]
            })
        assert resp.status_code == 200

    def test_update_permissions_missing_ids(self, client, mock_db, admin_auth_header):
        resp = client.put('/api/admin/roles/1/permissions', headers=admin_auth_header, json={})
        assert resp.status_code == 400

    def test_update_permissions_role_not_found(self, client, mock_db, admin_auth_header):
        with patch('backend.models.role.Role.find_by_id', return_value=None):
            resp = client.put('/api/admin/roles/999/permissions', headers=admin_auth_header, json={
                'permission_ids': [1, 2]
            })
        assert resp.status_code == 404


class TestAdminVipApplications:
    """GET /api/admin/vip-applications"""

    def test_get_vip_applications(self, client, mock_db, admin_auth_header):
        mock_db['cursor'].fetchall.return_value = [mock_vip_application]

        resp = client.get('/api/admin/vip-applications', headers=admin_auth_header)
        data = resp.get_json()
        assert resp.status_code == 200
        assert len(data['data']) == 1


class TestAdminApproveVip:
    """POST /api/admin/vip-applications/<id>/approve"""

    def test_approve_vip_success(self, client, mock_db, admin_auth_header):
        mock_db['cursor'].fetchone.side_effect = [mock_vip_application, {'id': 2, 'name': 'vip'}]

        resp = client.post('/api/admin/vip-applications/1/approve', headers=admin_auth_header)
        assert resp.status_code == 200
        assert resp.get_json()['msg'] == 'VIP申请已通过'

    def test_approve_vip_not_found(self, client, mock_db, admin_auth_header):
        mock_db['cursor'].fetchone.side_effect = [None, None]

        resp = client.post('/api/admin/vip-applications/999/approve', headers=admin_auth_header)
        assert resp.status_code == 404


class TestAdminRejectVip:
    """POST /api/admin/vip-applications/<id>/reject"""

    def test_reject_vip_success(self, client, mock_db, admin_auth_header):
        mock_db['cursor'].fetchone.side_effect = [mock_vip_application]

        resp = client.post('/api/admin/vip-applications/1/reject', headers=admin_auth_header, json={
            'remark': '不符合条件'
        })
        assert resp.status_code == 200
        assert resp.get_json()['msg'] == 'VIP申请已拒绝'

    def test_reject_vip_not_found(self, client, mock_db, admin_auth_header):
        mock_db['cursor'].fetchone.side_effect = [None, None]

        resp = client.post('/api/admin/vip-applications/999/reject', headers=admin_auth_header, json={
            'remark': '不符合条件'
        })
        assert resp.status_code == 404


class TestAdminUserLogs:
    """GET /api/admin/users/<id>/logs"""

    def test_get_user_logs_success(self, client, mock_db, admin_auth_header):
        mock_db['cursor'].fetchall.return_value = [mock_user_log]
        mock_db['cursor'].fetchone.return_value = {'total': 1}

        resp = client.get('/api/admin/users/1/logs', headers=admin_auth_header)
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['code'] == 200
        assert len(data['data']['logs']) == 1

    def test_get_all_user_logs(self, client, mock_db, admin_auth_header):
        mock_db['cursor'].fetchall.return_value = [mock_user_log]
        mock_db['cursor'].fetchone.return_value = {'total': 1}

        resp = client.get('/api/admin/user-logs', headers=admin_auth_header)
        data = resp.get_json()
        assert resp.status_code == 200
        assert len(data['data']['logs']) == 1

    def test_get_all_user_logs_compat_route(self, client, mock_db, admin_auth_header):
        mock_db['cursor'].fetchall.return_value = [mock_user_log]
        mock_db['cursor'].fetchone.return_value = {'total': 1}

        resp = client.get('/api/admin/users/logs', headers=admin_auth_header)
        assert resp.status_code == 200
