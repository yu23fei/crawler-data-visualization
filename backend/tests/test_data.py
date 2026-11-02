from unittest.mock import MagicMock, patch, ANY

import pytest

from backend.tests.mock_data import (
    mock_job_analysis, mock_job_core, mock_job_company,
    mock_favorite, mock_history
)


def _make_analysis_fetchone():
    """生成分析接口所需的 fetchone 返回值序列"""
    calls = [
        {'total': 100, 'avg_salary': 10000.0},
        {'cnt': 50},
        {'cnt': 10},
    ]
    idx = 0

    def side_effect():
        nonlocal idx
        if idx < len(calls):
            val = calls[idx]
            idx += 1
            return val
        return {'total': 100, 'avg_salary': 10000.0}
    return side_effect


def _make_analysis_fetchall():
    """生成分析接口所需的 fetchall 返回值序列"""
    return [
        # city_distribution
        [{'city': '北京', 'cnt': 30}, {'city': '上海', 'cnt': 20}],
        # education_distribution
        [{'education_std': '本科', 'cnt': 60}, {'education_std': '硕士', 'cnt': 30}],
        # salary_distribution
        [{'salary_range': '8-12k', 'cnt': 40}, {'salary_range': '12-20k', 'cnt': 30}],
        # experience_distribution
        [{'exp_range': '1-3年经验', 'cnt': 50}],
        # company_size_distribution
        [{'company_size': '100-500人', 'cnt': 40}],
        # company_type_distribution
        [{'property': '民营', 'cnt': 60}],
        # industry_distribution
        [{'industry_category': '互联网', 'cnt': 70}],
        # city_tier_distribution
        [{'city_tier': '一线城市', 'cnt': 50}],
        # city_tier_salary
        [{'city_tier': '一线城市', 'avg_sal': 12000.0}],
        # experience_salary
        [{'exp_range': '1-3年经验', 'avg_sal': 10000.0}],
        # benefit_score_distribution
        [{'benefit_score': 3, 'cnt': 30, 'pct': 30.0}],
        # work_type_distribution
        [{'work_type': '全职', 'cnt': 80}],
        # education_salary
        [{'education_std': '本科', 'avg_sal': 11000.0}],
        # heatmap_edu_salary
        [{'education_std': '本科', 'salary_range': '8-12k', 'cnt': 30}],
        # company_cross
        [{'company_size': '100-500人', 'property': '民营', 'cnt': 30}],
    ]


class TestV2Analysis:
    """GET /api/v2/analysis"""

    def test_analysis_success(self, client, mock_db, auth_header):
        mock_db['cursor'].fetchone.side_effect = _make_analysis_fetchone()

        fetchall_results = _make_analysis_fetchall()
        mock_db['cursor'].fetchall.side_effect = fetchall_results

        resp = client.get('/api/v2/analysis', headers=auth_header)
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['code'] == 200
        assert data['data']['overview']['total_jobs'] == 100

    def test_analysis_no_auth(self, client, mock_db):
        resp = client.get('/api/v2/analysis')
        assert resp.status_code == 401


class TestV2Data:
    """GET /api/v2/data"""

    def test_v2_data_success(self, client, mock_db, auth_header):
        mock_db['cursor'].fetchall.return_value = [mock_job_core]
        mock_db['cursor'].fetchone.return_value = {'total': 1}

        resp = client.get('/api/v2/data', headers=auth_header)
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['code'] == 200
        assert len(data['data']['records']) == 1

    def test_v2_data_pagination(self, client, mock_db, auth_header):
        mock_db['cursor'].fetchall.return_value = []
        mock_db['cursor'].fetchone.return_value = {'total': 0}

        resp = client.get('/api/v2/data?page=1&size=10', headers=auth_header)
        assert resp.status_code == 200


class TestV2Filter:
    """POST /api/v2/filter"""

    def test_filter_success(self, client, mock_db, auth_header):
        mock_db['cursor'].fetchall.return_value = [mock_job_analysis]
        mock_db['cursor'].fetchone.return_value = {'total': 1}

        with patch('backend.middleware.auth.User.find_by_id') as mock_find:
            mock_user_obj = MagicMock()
            mock_user_obj.has_permission.return_value = True
            mock_find.return_value = mock_user_obj

            resp = client.post('/api/v2/filter', headers=auth_header, json={
                'city': '北京',
                'education': '本科',
                'page': 1,
                'size': 20
            })
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['code'] == 200
        assert len(data['data']['records']) == 1

    def test_filter_no_auth(self, client, mock_db):
        resp = client.post('/api/v2/filter', json={'city': '北京'})
        assert resp.status_code == 401


class TestFilterOptions:
    """GET /api/v2/filter/options"""

    def test_filter_options_success(self, client, mock_db, auth_header):
        mock_db['cursor'].fetchall.side_effect = [
            [{'city': '北京'}],
            [{'education_std': '本科'}],
            [{'exp_range': '3-5年'}],
            [{'industry_category': 'IT'}],
            [{'company_size': '100-499人'}],
            [{'property': '民营'}],
        ]

        resp = client.get('/api/v2/filter/options', headers=auth_header)
        data = resp.get_json()
        assert resp.status_code == 200
        assert 'data' in data


class TestJobPage:
    """GET /api/job/page (兼容旧版前端)"""

    def test_job_page_success(self, client, mock_db, auth_header):
        mock_db['cursor'].fetchall.return_value = [mock_job_analysis]
        mock_db['cursor'].fetchone.return_value = {'total': 1}

        with patch('backend.middleware.auth.User.find_by_id') as mock_find:
            mock_user_obj = MagicMock()
            mock_user_obj.has_permission.return_value = True
            mock_find.return_value = mock_user_obj

            resp = client.get('/api/job/page', headers=auth_header)
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['code'] == 200


class TestJobFilter:
    """GET /api/job/filter (兼容旧版前端)"""

    def test_job_filter_success(self, client, mock_db, auth_header):
        mock_db['cursor'].fetchall.return_value = [mock_job_analysis]
        mock_db['cursor'].fetchone.return_value = {'total': 1}

        with patch('backend.middleware.auth.User.find_by_id') as mock_find:
            mock_user_obj = MagicMock()
            mock_user_obj.has_permission.return_value = True
            mock_find.return_value = mock_user_obj

            resp = client.get('/api/job/filter?city=北京', headers=auth_header)
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['code'] == 200


class TestJobDetail:
    """GET /api/job/detail"""

    def test_job_detail_success(self, client, mock_db, auth_header):
        analysis_with_company = dict(mock_job_analysis)
        analysis_with_company['company_name'] = '测试公司'
        mock_db['cursor'].fetchone.return_value = analysis_with_company

        with patch('backend.middleware.auth.User.find_by_id') as mock_find:
            mock_user_obj = MagicMock()
            mock_user_obj.has_permission.return_value = True
            mock_find.return_value = mock_user_obj

            resp = client.get('/api/job/detail?id=1&source=51job', headers=auth_header)
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['code'] == 200

    def test_job_detail_missing_params(self, client, mock_db, auth_header):
        mock_db['cursor'].fetchone.return_value = None
        with patch('backend.middleware.auth.User.find_by_id') as mock_find:
            mock_user_obj = MagicMock()
            mock_user_obj.has_permission.return_value = True
            mock_find.return_value = mock_user_obj

            resp = client.get('/api/job/detail', headers=auth_header)
        assert resp.status_code == 400

    def test_job_detail_not_found(self, client, mock_db, auth_header):
        mock_db['cursor'].fetchone.return_value = None

        with patch('backend.middleware.auth.User.find_by_id') as mock_find:
            mock_user_obj = MagicMock()
            mock_user_obj.has_permission.return_value = True
            mock_find.return_value = mock_user_obj

            resp = client.get('/api/job/detail?id=999&source=51job', headers=auth_header)
        assert resp.status_code == 404


class TestFavorites:
    """收藏接口测试"""

    def test_add_favorite_success(self, client, mock_db, auth_header):
        mock_db['cursor'].rowcount = 1

        resp = client.post('/api/job/favorite', headers=auth_header, json={
            'job_id': 1,
            'data_source': '51job'
        })
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['msg'] == '收藏成功'

    def test_add_favorite_duplicate(self, client, mock_db, auth_header):
        mock_db['cursor'].rowcount = 0

        resp = client.post('/api/job/favorite', headers=auth_header, json={
            'job_id': 1,
            'data_source': '51job'
        })
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['msg'] == '已收藏过'

    def test_add_favorite_missing_params(self, client, mock_db, auth_header):
        resp = client.post('/api/job/favorite', headers=auth_header, json={})
        assert resp.status_code == 400

    def test_add_favorite_no_auth(self, client, mock_db):
        resp = client.post('/api/job/favorite', json={'job_id': 1, 'data_source': '51job'})
        assert resp.status_code == 401

    def test_remove_favorite_success(self, client, mock_db, auth_header):
        resp = client.delete('/api/job/favorite', headers=auth_header, json={
            'job_id': 1,
            'data_source': '51job'
        })
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['msg'] == '已取消收藏'

    def test_remove_favorite_missing_params(self, client, mock_db, auth_header):
        resp = client.delete('/api/job/favorite', headers=auth_header, json={})
        assert resp.status_code == 400

    def test_get_favorites_success(self, client, mock_db, auth_header):
        mock_db['cursor'].fetchall.return_value = [{
            'favorite_id': 1, 'job_id': 1, 'data_source': '51job',
            'favorited_at': '2024-06-01 10:00:00', 'company_name': '测试公司',
            'source': '51job', 'city': '北京', 'position_name': '软件工程师',
            'salary_avg': 10000.0, 'education_std': '本科', 'exp_range': '1-3年经验',
            'created_at': '2024-06-01 10:00:00'
        }]
        mock_db['cursor'].fetchone.return_value = {'total': 1}

        resp = client.get('/api/job/favorites', headers=auth_header)
        data = resp.get_json()
        assert resp.status_code == 200
        assert len(data['data']) == 1


class TestHistory:
    """浏览历史接口测试"""

    def test_record_history_success(self, client, mock_db, auth_header):
        resp = client.post('/api/job/history', headers=auth_header, json={
            'job_id': 1,
            'data_source': '51job'
        })
        data = resp.get_json()
        assert resp.status_code == 200
        assert data['msg'] == '记录成功'

    def test_record_history_missing_params(self, client, mock_db, auth_header):
        resp = client.post('/api/job/history', headers=auth_header, json={})
        assert resp.status_code == 400

    def test_record_history_no_auth(self, client, mock_db):
        resp = client.post('/api/job/history', json={'job_id': 1, 'data_source': '51job'})
        assert resp.status_code == 401

    def test_get_history_success(self, client, mock_db, auth_header):
        mock_db['cursor'].fetchall.return_value = [{
            'history_id': 1, 'job_id': 1, 'data_source': '51job',
            'viewed_at': '2024-06-01 10:00:00', 'company_name': '测试公司',
            'source': '51job', 'city': '北京', 'position_name': '软件工程师',
            'salary_avg': 10000.0, 'education_std': '本科', 'exp_range': '1-3年经验',
            'created_at': '2024-06-01 10:00:00'
        }]
        mock_db['cursor'].fetchone.return_value = {'total': 1}

        resp = client.get('/api/job/history', headers=auth_header)
        data = resp.get_json()
        assert resp.status_code == 200
        assert len(data['data']) == 1
