import os
from unittest.mock import patch, MagicMock

import jwt
import pytest

os.environ['DB_PASSWORD'] = 'test_password_123'
os.environ['JWT_SECRET'] = 'test_jwt_secret_key_at_least_32_chars!!'
os.environ['SECRET_KEY'] = 'test_secret_key_for_testing_12345'

from backend.core.config import Config
from backend.main import app as flask_app


@pytest.fixture
def app():
    flask_app.config['TESTING'] = True
    flask_app.config['JWT_SECRET'] = 'test_jwt_secret_key_at_least_32_chars!!'
    return flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def mock_db():
    with patch('pymysql.connect') as mock_conn:
        conn_instance = MagicMock()
        cursor_instance = MagicMock()

        conn_instance.cursor.return_value = cursor_instance
        conn_instance.__enter__.return_value = conn_instance
        conn_instance.__exit__.return_value = None
        cursor_instance.__enter__.return_value = cursor_instance
        cursor_instance.__exit__.return_value = None
        cursor_instance.fetchone.return_value = None
        cursor_instance.fetchall.return_value = []
        cursor_instance.rowcount = 0
        cursor_instance.lastrowid = 1
        conn_instance.cursor.return_value = cursor_instance

        def cursor_side_effect(cursor_class=None, cursor=None):
            return cursor_instance
        conn_instance.cursor.side_effect = cursor_side_effect

        mock_conn.return_value = conn_instance

        yield {
            'conn': conn_instance,
            'cursor': cursor_instance,
            'mock_conn': mock_conn
        }


_jti_counter = 0


def _make_token(user_id=1, username='testuser', role='guest'):
    global _jti_counter
    _jti_counter += 1
    payload = {
        'user_id': user_id,
        'username': username,
        'role': role,
        'jti': f'test-jti-{_jti_counter}',
        'exp': 9999999999,
        'iat': 1000000000
    }
    token = jwt.encode(payload, Config.JWT_SECRET, algorithm='HS256')
    if isinstance(token, bytes):
        token = token.decode('utf-8')
    return token


@pytest.fixture
def guest_token():
    return _make_token(user_id=1, username='guestuser', role='guest')


@pytest.fixture
def vip_token():
    return _make_token(user_id=2, username='vipuser', role='vip')


@pytest.fixture
def admin_token():
    return _make_token(user_id=3, username='adminuser', role='admin')


@pytest.fixture
def auth_header(guest_token):
    return {'Authorization': f'Bearer {guest_token}'}


@pytest.fixture
def admin_auth_header(admin_token):
    return {'Authorization': f'Bearer {admin_token}'}


@pytest.fixture
def mock_empty_db(mock_db):
    def find_by_username_side_effect(username):
        return None
    mock_db['cursor'].fetchone.return_value = None
    return mock_db
