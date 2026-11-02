mock_user = {
    'id': 1,
    'username': 'testuser',
    'password_hash': '$2b$12$LJ3m4ys3Lk4wQ5k6J7kL8uH1v2w3x4y5z6A7B8C9D0E1F2G3H4I5J6K7L',
    'plain_password': 'TestPass123',
    'email': 'test@example.com',
    'phone': '13800138000',
    'security_question': '你的宠物名字？',
    'security_answer': '$2b$12$LJ3m4ys3Lk4wQ5k6J7kL8uH1v2w3x4y5z6A7B8C9D0E1F2G3H4I5J6K7L',
    'status': 'active',
    'created_at': '2024-01-01 00:00:00',
    'updated_at': '2024-01-01 00:00:00'
}

mock_guest_role = {
    'id': 1, 'name': 'guest', 'description': '普通访客', 'created_at': '2024-01-01 00:00:00'
}

mock_vip_role = {
    'id': 2, 'name': 'vip', 'description': 'VIP用户', 'created_at': '2024-01-01 00:00:00'
}

mock_admin_role = {
    'id': 3, 'name': 'admin', 'description': '管理员', 'created_at': '2024-01-01 00:00:00'
}

mock_roles = [mock_guest_role, mock_vip_role, mock_admin_role]

mock_permissions = [
    {'id': 1, 'name': 'view_charts', 'description': '查看图表', 'resource': 'charts', 'action': 'read'},
    {'id': 2, 'name': 'view_data', 'description': '查看数据', 'resource': 'data', 'action': 'read'},
    {'id': 3, 'name': 'filter_jobs', 'description': '筛选岗位', 'resource': 'jobs', 'action': 'filter'},
    {'id': 4, 'name': 'view_detail', 'description': '查看岗位详情', 'resource': 'jobs', 'action': 'read'},
    {'id': 5, 'name': 'manage_favorites', 'description': '管理收藏', 'resource': 'favorites', 'action': 'manage'},
    {'id': 6, 'name': 'view_history', 'description': '查看浏览历史', 'resource': 'history', 'action': 'read'},
    {'id': 7, 'name': 'manage_users', 'description': '管理用户', 'resource': 'users', 'action': 'manage'},
    {'id': 8, 'name': 'manage_crawlers', 'description': '管理爬虫', 'resource': 'crawlers', 'action': 'manage'},
    {'id': 9, 'name': 'manage_database', 'description': '管理数据库', 'resource': 'database', 'action': 'manage'},
    {'id': 10, 'name': 'approve_users', 'description': '审批用户', 'resource': 'users', 'action': 'approve'},
    {'id': 11, 'name': 'view_user_logs', 'description': '查看用户日志', 'resource': 'logs', 'action': 'read'},
]

mock_vip_application = {
    'id': 1, 'user_id': 1, 'status': 'pending',
    'handled_by': None, 'remark': None,
    'created_at': '2024-06-01 10:00:00', 'updated_at': '2024-06-01 10:00:00',
    'username': 'testuser'
}

mock_user_log = {
    'id': 1, 'user_id': 1, 'action': 'login',
    'details': '用户登录成功', 'ip_address': '127.0.0.1',
    'created_at': '2024-06-01 10:00:00', 'username': 'testuser'
}

mock_job_analysis = {
    'id': 1, 'source': '51job', 'city': '北京', 'education_std': '本科',
    'salary_range': '8-12k', 'salary_avg': 10000.0, 'exp_range': '1-3年经验',
    'company_size': '100-500人', 'property': '民营', 'industry_category': '互联网',
    'city_tier': '一线城市', 'benefit_score': 3, 'work_type': '全职',
    'position_name': '软件工程师', 'company_name': '测试公司'
}

mock_job_core = {
    'id': 1, 'data_source': '51job', 'source_id': 1,
    'position_name': '软件工程师', 'salary_avg': 10000.0,
    'salary_range': '8-12k', 'publish_date': '2024-06-01',
    'recruit_number': 2
}

mock_job_company = {
    'id': 1, 'data_source': '51job', 'company_name': '测试公司',
    'property': '民营', 'company_size': '100-500人',
    'industry': '互联网', 'financing_stage': '不需要融资',
    'company_intro_clean': '这是一家测试公司',
    'company_logo': '', 'industry_category': '互联网'
}

mock_favorite = {
    'id': 1, 'user_id': 1, 'job_id': 1, 'data_source': '51job',
    'created_at': '2024-06-01 10:00:00', 'favorited_at': '2024-06-01 10:00:00'
}

mock_history = {
    'id': 1, 'user_id': 1, 'job_id': 1, 'data_source': '51job',
    'viewed_at': '2024-06-01 10:00:00'
}

mock_51job_record = {
    'id': 1, 'position_id': '1001', 'job_url': '', 'position_name': '软件工程师',
    'company_name': '测试公司', 'salary': '10000-15000', 'city': '北京',
    'created_at': '2024-06-01 10:00:00'
}

mock_zhaopin_record = {
    'id': 1, 'position_id': '2001', 'job_url': 'http://example.com',
    'position_name': '高级工程师', 'company_name': '测试公司2',
    'salary': '15000-20000', 'city': '上海', 'created_at': '2024-06-01 10:00:00'
}
