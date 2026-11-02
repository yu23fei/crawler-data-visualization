import json
from unittest.mock import MagicMock, patch, ANY

import pytest

from backend.tests.mock_data import (
    mock_51job_record, mock_zhaopin_record, mock_user,
    mock_job_analysis, mock_job_core, mock_job_company
)


class TestJobData:
    """GET /api/jobData"""

    def test_get_all_job_success(self, client, mock_db, auth_header):
        mock_db['cursor'].fetchall.return_value = [mock_51job_record]

        resp = client.get('/api/jobData', headers=auth_header)
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['code'] == 200
        assert len(data['data']) == 1

    def test_get_all_job_no_auth(self, client, mock_db):
        resp = client.get('/api/jobData')
        assert resp.status_code == 401


class TestZhaopinJobData:
    """GET /api/zhaopin/jobData"""

    def test_get_zhaopin_job_success(self, client, mock_db, auth_header):
        mock_db['cursor'].fetchall.return_value = [mock_zhaopin_record]

        resp = client.get('/api/zhaopin/jobData', headers=auth_header)
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['code'] == 200
        assert len(data['data']) == 1


class TestMergedJobData:
    """GET /api/jobData/merged"""

    def test_get_merged_success(self, client, mock_db, auth_header):
        mock_db['cursor'].fetchall.side_effect = [
            [dict(mock_51job_record, data_source='51job')],
            [dict(mock_zhaopin_record, data_source='zhaopin')]
        ]

        resp = client.get('/api/jobData/merged', headers=auth_header)
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['code'] == 200
        assert data['total_count'] == 2


class TestJobStats:
    """GET /api/jobData/stats"""

    def test_stats_all(self, client, mock_db, auth_header):
        def fetchone_side_effect():
            fetchone_side_effect.call_count += 1
            if fetchone_side_effect.call_count == 1:
                return {'count': 10}
            return {'count': 20}
        fetchone_side_effect.call_count = 0
        mock_db['cursor'].fetchone.side_effect = fetchone_side_effect

        resp = client.get('/api/jobData/stats?source=all', headers=auth_header)
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['data']['total'] == 30


class TestPagination:
    """分页接口测试"""

    def test_zhaopin_page(self, client, mock_db, auth_header):
        mock_db['cursor'].fetchall.return_value = [mock_zhaopin_record]
        mock_db['cursor'].fetchone.return_value = {'total': 1}

        resp = client.get('/api/zhaopin/job/page?page=1&size=10', headers=auth_header)
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['code'] == 200

    def test_51job_page(self, client, mock_db, auth_header):
        mock_db['cursor'].fetchall.return_value = [mock_51job_record]
        mock_db['cursor'].fetchone.return_value = {'total': 1}

        resp = client.get('/api/51job/job/page?page=1&size=10', headers=auth_header)
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['code'] == 200


class TestJobCRUD:
    """岗位 CRUD 接口测试（管理员）"""

    def test_add_job_success(self, client, mock_db, admin_auth_header):
        with patch('backend.main.audit_log'):
            resp = client.post('/api/job/add', headers=admin_auth_header, json={
                'job_id': 100,
                'major': '计算机',
                'education': '本科',
                'experience': '1-3年',
                'salary': '10000-15000',
                'company_name': '测试公司',
                'company_nature': '民营',
                'company_scale': '100-500人',
                'work_city': '北京',
                'job_name': '软件工程师',
                'update_time': '2024-06-01'
            })
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['code'] == 200
        assert data['msg'] == '新增成功'

    def test_add_job_missing_fields(self, client, mock_db, admin_auth_header):
        resp = client.post('/api/job/add', headers=admin_auth_header, json={
            'job_id': 100,
            'major': '计算机'
        })
        assert resp.status_code == 400

    def test_add_job_empty_body(self, client, mock_db, admin_auth_header):
        resp = client.post('/api/job/add', headers=admin_auth_header, json={})
        assert resp.status_code == 400

    def test_add_job_no_auth(self, client, mock_db):
        resp = client.post('/api/job/add', json={'job_id': 100})
        assert resp.status_code == 401

    def test_add_job_forbidden_guest(self, client, mock_db, auth_header):
        resp = client.post('/api/job/add', headers=auth_header, json={'job_id': 100})
        assert resp.status_code == 403

    def test_update_job_success(self, client, mock_db, admin_auth_header):
        with patch('backend.main.audit_log'):
            resp = client.put('/api/job/update', headers=admin_auth_header, json={
                'job_id': 100,
                'major': '计算机科学',
                'education': '硕士',
                'experience': '3-5年',
                'salary': '20000-30000',
                'company_name': '测试公司',
                'company_nature': '上市公司',
                'company_scale': '1000-5000人',
                'work_city': '上海',
                'job_name': '高级工程师',
                'update_time': '2024-06-02'
            })
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['code'] == 200

    def test_update_job_empty_body(self, client, mock_db, admin_auth_header):
        resp = client.put('/api/job/update', headers=admin_auth_header, json={})
        assert resp.status_code == 400

    def test_delete_job_success(self, client, mock_db, admin_auth_header):
        with patch('backend.main.audit_log'):
            resp = client.delete('/api/job/del/100', headers=admin_auth_header)
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['code'] == 200

    def test_delete_job_no_auth(self, client, mock_db):
        resp = client.delete('/api/job/del/100')
        assert resp.status_code == 401


class TestCrawler:
    """爬虫管理接口测试"""

    def test_crawler_status(self, client, mock_db, admin_auth_header):
        resp = client.get('/api/admin/crawler/status', headers=admin_auth_header)
        data = resp.get_json()
        assert resp.status_code == 200
        assert '51job' in data['data']
        assert 'zhaopin' in data['data']

    def test_crawler_source_status(self, client, mock_db, admin_auth_header):
        resp = client.get('/api/admin/crawler/51job/status', headers=admin_auth_header)
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['data']['status'] == 'stopped'

    def test_crawler_invalid_source(self, client, mock_db, admin_auth_header):
        resp = client.get('/api/admin/crawler/invalid/status', headers=admin_auth_header)
        assert resp.status_code == 400

    def test_crawler_start_missing_script(self, client, mock_db, admin_auth_header):
        with patch('os.path.exists', return_value=False):
            resp = client.post('/api/admin/crawler/51job/start', headers=admin_auth_header)
        data = resp.get_json()
        assert resp.status_code == 500
        assert '爬虫脚本' in data.get('msg', '')

    def test_crawler_stop_not_running(self, client, mock_db, admin_auth_header):
        resp = client.post('/api/admin/crawler/51job/stop', headers=admin_auth_header)
        data = resp.get_json()
        assert resp.status_code == 400
        assert '未在运行' in data['msg']

    def test_crawler_no_auth(self, client, mock_db):
        resp = client.get('/api/admin/crawler/status')
        assert resp.status_code == 401


class TestDatabaseManage:
    """数据库管理接口测试"""

    def test_get_tables(self, client, mock_db, admin_auth_header):
        mock_db['cursor'].fetchall.return_value = [
            {'Tables_in_yingjie_spider': 'users'},
            {'Tables_in_yingjie_spider': 'jobs'}
        ]

        resp = client.get('/api/admin/database/tables', headers=admin_auth_header)
        data = resp.get_json()
        assert resp.status_code == 200
        assert len(data['data']) == 2

    def test_get_table_data(self, client, mock_db, admin_auth_header):
        def fetchall_side_effect():
            fetchall_side_effect.call_count += 1
            if fetchall_side_effect.call_count == 1:
                return [{'Tables_in_yingjie_spider': 'users'}]
            if fetchall_side_effect.call_count == 2:
                return [mock_user]
            if fetchall_side_effect.call_count == 3:
                return [{'Field': 'id'}, {'Field': 'username'}]
            return []
        fetchall_side_effect.call_count = 0
        mock_db['cursor'].fetchall.side_effect = fetchall_side_effect
        mock_db['cursor'].fetchone.return_value = {'total': 1}

        resp = client.get('/api/admin/database/table/users', headers=admin_auth_header)
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['code'] == 200

    def test_get_table_data_invalid_table(self, client, mock_db, admin_auth_header):
        mock_db['cursor'].fetchall.return_value = [{'Tables_in_yingjie_spider': 'users'}]

        resp = client.get('/api/admin/database/table/nonexistent', headers=admin_auth_header)
        assert resp.status_code == 400

    def test_add_record_success(self, client, mock_db, admin_auth_header):
        def fetchall_side_effect():
            fetchall_side_effect.call_count += 1
            if fetchall_side_effect.call_count == 1:
                return [{'Tables_in_yingjie_spider': 'users'}]
            return [{'Field': 'id'}, {'Field': 'username'}]
        fetchall_side_effect.call_count = 0
        mock_db['cursor'].fetchall.side_effect = fetchall_side_effect
        mock_db['cursor'].lastrowid = 100

        with patch('backend.main.audit_log'):
            resp = client.post('/api/admin/database/record', headers=admin_auth_header, json={
                'table': 'users',
                'record': {'username': 'new_record'}
            })
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['data']['id'] == 100

    def test_add_record_missing_table(self, client, mock_db, admin_auth_header):
        resp = client.post('/api/admin/database/record', headers=admin_auth_header, json={
            'record': {'username': 'test'}
        })
        assert resp.status_code == 400

    def test_add_record_invalid_table(self, client, mock_db, admin_auth_header):
        mock_db['cursor'].fetchall.return_value = [{'Tables_in_yingjie_spider': 'users'}]

        resp = client.post('/api/admin/database/record', headers=admin_auth_header, json={
            'table': 'nonexistent',
            'record': {'username': 'test'}
        })
        assert resp.status_code == 400

    def test_update_record_success(self, client, mock_db, admin_auth_header):
        def fetchall_side_effect():
            fetchall_side_effect.call_count += 1
            if fetchall_side_effect.call_count == 1:
                return [{'Tables_in_yingjie_spider': 'users'}]
            return [{'Field': 'id'}, {'Field': 'username'}]
        fetchall_side_effect.call_count = 0
        mock_db['cursor'].fetchall.side_effect = fetchall_side_effect

        with patch('backend.main.audit_log'):
            resp = client.put('/api/admin/database/record', headers=admin_auth_header, json={
                'table': 'users',
                'id': 1,
                'record': {'username': 'updated'}
            })
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['msg'] == '记录更新成功'

    def test_update_record_missing_fields(self, client, mock_db, admin_auth_header):
        resp = client.put('/api/admin/database/record', headers=admin_auth_header, json={
            'table': 'users'
        })
        assert resp.status_code == 400

    def test_delete_record_success(self, client, mock_db, admin_auth_header):
        def fetchall_side_effect():
            return [{'Tables_in_yingjie_spider': 'jobs'}]
        mock_db['cursor'].fetchall.side_effect = fetchall_side_effect

        with patch('backend.main.audit_log'):
            resp = client.delete('/api/admin/database/record/1?table=jobs', headers=admin_auth_header)
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['msg'] == '记录删除成功'

    def test_delete_record_missing_table(self, client, mock_db, admin_auth_header):
        resp = client.delete('/api/admin/database/record/1', headers=admin_auth_header)
        assert resp.status_code == 400

    def test_delete_record_restricted_table(self, client, mock_db, admin_auth_header):
        def fetchall_side_effect():
            return [{'Tables_in_yingjie_spider': 'users'}]
        mock_db['cursor'].fetchall.side_effect = fetchall_side_effect

        resp = client.delete('/api/admin/database/record/1?table=users', headers=admin_auth_header)
        assert resp.status_code == 403


class TestRecentJobs:
    """GET /api/admin/recent-jobs"""

    def test_recent_jobs_all(self, client, mock_db, admin_auth_header):
        mock_db['cursor'].fetchall.side_effect = [
            [mock_51job_record],
            [mock_zhaopin_record]
        ]

        resp = client.get('/api/admin/recent-jobs', headers=admin_auth_header)
        data = resp.get_json()
        assert resp.status_code == 200
        assert len(data['data']) == 2

    def test_recent_jobs_by_source(self, client, mock_db, admin_auth_header):
        mock_db['cursor'].fetchall.side_effect = [
            [mock_51job_record]
        ]

        resp = client.get('/api/admin/recent-jobs?source=51job&limit=5', headers=admin_auth_header)
        data = resp.get_json()
        assert resp.status_code == 200
        assert len(data['data']) == 1


class TestCatchAll:
    """SPA catch-all 路由"""

    def test_index_page(self, client, mock_db):
        resp = client.get('/')
        assert resp.status_code == 200

    def test_catch_all_frontend_route(self, client, mock_db):
        resp = client.get('/some/frontend/route')
        assert resp.status_code == 200

    def test_catch_all_api_404(self, client, mock_db):
        resp = client.get('/api/nonexistent/route')
        assert resp.status_code == 404
        assert resp.get_json()['msg'] == '接口不存在'
