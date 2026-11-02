from unittest.mock import patch, MagicMock, ANY

import pytest
from backend.tests.mock_data import mock_user, mock_guest_role, mock_vip_role, mock_roles, mock_user_log


class TestRegister:
    """POST /api/auth/register"""

    def test_register_success(self, client, mock_db):
        mock_db['cursor'].fetchone.return_value = None
        mock_db['cursor'].lastrowid = 1

        def fetchone_side_effect():
            fetchone_side_effect.call_count += 1
            if fetchone_side_effect.call_count == 1:
                return None
            if fetchone_side_effect.call_count == 2:
                return {'id': 1, 'name': 'guest', 'description': '普通访客'}
            return None
        fetchone_side_effect.call_count = 0
        mock_db['cursor'].fetchone = MagicMock(side_effect=fetchone_side_effect)

        resp = client.post('/api/auth/register', json={
            'username': 'newuser',
            'password': 'NewPass123',
            'security_question': '你的宠物名字？',
            'security_answer': '旺财'
        })
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['code'] == 200
        assert data['msg'] == '注册成功'

    def test_register_missing_fields(self, client, mock_db):
        resp = client.post('/api/auth/register', json={
            'username': 'newuser'
        })
        assert resp.status_code == 400
        assert resp.get_json()['code'] == 400

    def test_register_empty_body(self, client, mock_db):
        resp = client.post('/api/auth/register', json={})
        assert resp.status_code == 400

    def test_register_no_body(self, client, mock_db):
        resp = client.post('/api/auth/register', data='{}', content_type='application/json')
        assert resp.status_code == 400

    def test_register_duplicate_username(self, client, mock_db):
        mock_db['cursor'].fetchone.side_effect = [mock_user]
        resp = client.post('/api/auth/register', json={
            'username': 'testuser',
            'password': 'NewPass123',
            'security_question': '问题',
            'security_answer': '答案'
        })
        assert resp.status_code == 400
        assert resp.get_json()['msg'] == '用户名已存在'

    def test_register_invalid_username(self, client, mock_db):
        mock_db['cursor'].fetchone.return_value = None
        resp = client.post('/api/auth/register', json={
            'username': 'ab',
            'password': 'NewPass123',
            'security_question': '问题',
            'security_answer': '答案'
        })
        assert resp.status_code == 400
        assert '用户名' in resp.get_json()['msg']

    def test_register_weak_password(self, client, mock_db):
        mock_db['cursor'].fetchone.return_value = None
        resp = client.post('/api/auth/register', json={
            'username': 'newuser',
            'password': 'weak',
            'security_question': '问题',
            'security_answer': '答案'
        })
        assert resp.status_code == 400


class TestLogin:
    """POST /api/auth/login"""

    @pytest.fixture(autouse=True)
    def clear_login_attempts(self):
        import backend.api.v1.auth
        backend.api.v1.auth._login_attempts.clear()
        yield

    def test_login_success(self, client, mock_db):
        mock_db['cursor'].fetchone.return_value = mock_user

        with patch('backend.api.v1.auth.verify_password', return_value=True):
            with patch('backend.api.v1.auth.generate_token', return_value='mock-token-123'):
                resp = client.post('/api/auth/login', json={
                    'username': 'testuser',
                    'password': 'TestPass123'
                })
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['code'] == 200
        assert data['data']['token'] == 'mock-token-123'

    def test_login_missing_fields(self, client, mock_db):
        resp = client.post('/api/auth/login', json={'username': 'testuser'})
        assert resp.status_code == 400

    def test_login_wrong_password(self, client, mock_db):
        mock_db['cursor'].fetchone.return_value = mock_user
        with patch('backend.api.v1.auth.verify_password', return_value=False):
            resp = client.post('/api/auth/login', json={
                'username': 'testuser',
                'password': 'WrongPass123'
            })
        assert resp.status_code == 401

    def test_login_user_not_found(self, client, mock_db):
        mock_db['cursor'].fetchone.return_value = None
        resp = client.post('/api/auth/login', json={
            'username': 'nonexistent',
            'password': 'TestPass123'
        })
        assert resp.status_code == 401

    def test_login_disabled_user(self, client, mock_db):
        disabled_user = dict(mock_user, status='disabled')
        mock_db['cursor'].fetchone.return_value = disabled_user
        resp = client.post('/api/auth/login', json={
            'username': 'testuser',
            'password': 'TestPass123'
        })
        assert resp.status_code == 403
        assert '禁用' in resp.get_json()['msg']


class TestProfile:
    """GET /api/auth/profile"""

    def test_get_profile_success(self, client, mock_db, auth_header):
        with patch('backend.api.v1.auth.User.find_by_id') as mock_find:
            mock_user_obj = MagicMock()
            mock_user_obj.to_dict.return_value = {k: v for k, v in mock_user.items()
                                                  if k not in ('password_hash', 'security_answer')}
            mock_user_obj.plain_password = 'TestPass123'
            mock_user_obj.get_roles.return_value = [{'name': 'guest'}]
            mock_user_obj.get_permissions.return_value = ['view_charts', 'view_data']
            mock_find.return_value = mock_user_obj

            resp = client.get('/api/auth/profile', headers=auth_header)

        assert resp.status_code == 200
        data = resp.get_json()
        assert data['code'] == 200

    def test_get_profile_no_token(self, client, mock_db):
        resp = client.get('/api/auth/profile')
        assert resp.status_code == 401

    def test_get_profile_invalid_token(self, client, mock_db):
        resp = client.get('/api/auth/profile', headers={'Authorization': 'Bearer invalid-token'})
        assert resp.status_code == 401


class TestUpdateProfile:
    """PUT /api/auth/update-profile"""

    def test_update_profile_success(self, client, mock_db, auth_header):
        with patch('backend.api.v1.auth.User.find_by_id') as mock_find:
            mock_user_obj = MagicMock()
            mock_find.return_value = mock_user_obj
            resp = client.put('/api/auth/update-profile', headers=auth_header, json={
                'email': 'new@example.com',
                'phone': '13900139000'
            })
        assert resp.status_code == 200
        assert resp.get_json()['msg'] == '个人信息已更新'

    def test_update_profile_no_auth(self, client, mock_db):
        resp = client.put('/api/auth/update-profile', json={'email': 'new@example.com'})
        assert resp.status_code == 401

    def test_update_profile_invalid_email(self, client, mock_db, auth_header):
        with patch('backend.api.v1.auth.User.find_by_id') as mock_find:
            mock_user_obj = MagicMock()
            mock_find.return_value = mock_user_obj
            resp = client.put('/api/auth/update-profile', headers=auth_header, json={
                'email': 'not-an-email'
            })
        assert resp.status_code == 400
        assert '邮箱' in resp.get_json()['msg']


class TestChangePassword:
    """PUT /api/auth/change-password"""

    def test_change_password_success(self, client, mock_db, auth_header):
        with patch('backend.api.v1.auth.User.find_by_id') as mock_find:
            mock_user_obj = MagicMock()
            mock_user_obj.password_hash = mock_user['password_hash']
            mock_find.return_value = mock_user_obj

            with patch('backend.api.v1.auth.verify_password', return_value=True):
                with patch('backend.api.v1.auth.add_to_blacklist') as mock_blacklist:
                    resp = client.put('/api/auth/change-password', headers=auth_header, json={
                        'old_password': 'OldPass123',
                        'new_password': 'NewPass456'
                    })

        assert resp.status_code == 200
        assert '重新登录' in resp.get_json()['msg']

    def test_change_password_no_auth(self, client, mock_db):
        resp = client.put('/api/auth/change-password', json={
            'old_password': 'OldPass123',
            'new_password': 'NewPass456'
        })
        assert resp.status_code == 401

    def test_change_password_wrong_old(self, client, mock_db, auth_header):
        with patch('backend.api.v1.auth.User.find_by_id') as mock_find:
            mock_user_obj = MagicMock()
            mock_user_obj.password_hash = mock_user['password_hash']
            mock_find.return_value = mock_user_obj

            with patch('backend.api.v1.auth.verify_password', return_value=False):
                resp = client.put('/api/auth/change-password', headers=auth_header, json={
                    'old_password': 'WrongPass',
                    'new_password': 'NewPass456'
                })
        assert resp.status_code == 400
        assert '原密码错误' in resp.get_json()['msg']


class TestResetPassword:
    """POST /api/auth/reset-password"""

    def test_reset_password_success(self, client, mock_db):
        mock_db['cursor'].fetchone.return_value = mock_user
        with patch('backend.api.v1.auth.verify_password', return_value=True):
            resp = client.post('/api/auth/reset-password', json={
                'username': 'testuser',
                'security_answer': '旺财',
                'new_password': 'NewPass789'
            })
        assert resp.status_code == 200
        assert '重置成功' in resp.get_json()['msg']

    def test_reset_password_missing_fields(self, client, mock_db):
        resp = client.post('/api/auth/reset-password', json={'username': 'testuser'})
        assert resp.status_code == 400

    def test_reset_password_user_not_found(self, client, mock_db):
        mock_db['cursor'].fetchone.return_value = None
        resp = client.post('/api/auth/reset-password', json={
            'username': 'nonexistent',
            'security_answer': '答案',
            'new_password': 'NewPass789'
        })
        assert resp.status_code == 404

    def test_reset_password_wrong_answer(self, client, mock_db):
        mock_db['cursor'].fetchone.return_value = mock_user
        with patch('backend.api.v1.auth.verify_password', return_value=False):
            resp = client.post('/api/auth/reset-password', json={
                'username': 'testuser',
                'security_answer': '错误答案',
                'new_password': 'NewPass789'
            })
        assert resp.status_code == 400
        assert '安全答案错误' in resp.get_json()['msg']


class TestApplyVip:
    """POST /api/auth/apply-vip"""

    def test_apply_vip_success(self, client, mock_db, auth_header):
        mock_db['cursor'].fetchone.side_effect = [None, None]
        mock_db['cursor'].fetchall.return_value = []

        with patch('backend.api.v1.auth.User.find_by_id') as mock_find:
            mock_user_obj = MagicMock()
            mock_user_obj.get_roles.return_value = [{'name': 'guest'}]
            mock_find.return_value = mock_user_obj

            resp = client.post('/api/auth/apply-vip', headers=auth_header)
        assert resp.status_code == 200
        assert 'VIP申请已提交' in resp.get_json()['msg']

    def test_apply_vip_no_auth(self, client, mock_db):
        resp = client.post('/api/auth/apply-vip')
        assert resp.status_code == 401

    def test_apply_vip_already_vip(self, client, mock_db, auth_header):
        with patch('backend.api.v1.auth.User.find_by_id') as mock_find:
            mock_user_obj = MagicMock()
            mock_user_obj.get_roles.return_value = [{'name': 'vip'}]
            mock_find.return_value = mock_user_obj

            resp = client.post('/api/auth/apply-vip', headers=auth_header)
        assert resp.status_code == 400
        assert '已是VIP' in resp.get_json()['msg']

    def test_apply_vip_pending_exists(self, client, mock_db, auth_header):
        mock_db['cursor'].fetchone.return_value = {'id': 1, 'status': 'pending'}

        with patch('backend.api.v1.auth.User.find_by_id') as mock_find:
            mock_user_obj = MagicMock()
            mock_user_obj.get_roles.return_value = [{'name': 'guest'}]
            mock_find.return_value = mock_user_obj

            resp = client.post('/api/auth/apply-vip', headers=auth_header)
        assert resp.status_code == 400
        assert '待审批' in resp.get_json()['msg']


class TestLogout:
    """POST /api/auth/logout"""

    def test_logout_success(self, client, mock_db, auth_header):
        resp = client.post('/api/auth/logout', headers=auth_header)
        assert resp.status_code == 200
        assert resp.get_json()['msg'] == '已登出'

    def test_logout_no_token(self, client, mock_db):
        resp = client.post('/api/auth/logout')
        assert resp.status_code == 401
