# optimize_db.py - 数据库优化模块（兼容MySQL 5.7+）
# 遵循阿里巴巴Java开发手册数据库规范，提供8大类优化操作：
#   1.清理废弃表   2.统一引擎和字符集   3.添加审计时间戳   4.添加必要索引
#   5.添加NOT NULL约束  6.添加字段注释  7.添加表注释  8.用户表索引优化
#
# 所有优化操作均为幂等——重复执行不会报错，已存在的配置会自动跳过
# 使用方式：python -m backend.core.optimize_db
import sys
sys.path.insert(0, '.')
from backend.core.config import Config
import pymysql


def execute_sql(cursor, sql, desc=""):
    """执行SQL并打印结果"""
    try:
        cursor.execute(sql)
        if desc:
            print(f"  [OK] {desc}")
        return True
    except Exception:
        # 不暴露具体异常详情（防止敏感信息泄露）
        print(f"  [SKIP] {desc}")
        return False


def column_exists(cursor, table, column):
    """检查列是否存在"""
    cursor.execute(f"SHOW COLUMNS FROM `{table}` LIKE '{column}'")
    return cursor.fetchone() is not None


def index_exists(cursor, table, index_name):
    """检查索引是否存在"""
    cursor.execute(f"SHOW INDEX FROM `{table}` WHERE Key_name = '{index_name}'")
    return cursor.fetchone() is not None


def add_column_if_not_exists(cursor, table, column_def, desc=""):
    """安全添加列"""
    col_name = column_def.split()[0].strip('`')
    if not column_exists(cursor, table, col_name):
        execute_sql(cursor, f"ALTER TABLE `{table}` ADD COLUMN {column_def}", desc)
    else:
        print(f"  [SKIP] {desc} (已存在)")


def add_index_if_not_exists(cursor, table, index_def, index_name, desc=""):
    """安全添加索引"""
    if not index_exists(cursor, table, index_name):
        execute_sql(cursor, f"ALTER TABLE `{table}` ADD INDEX {index_def}", desc)
    else:
        print(f"  [SKIP] {desc} (已存在)")


def optimize_database():
    conn = pymysql.connect(
        host=Config.DB_HOST, port=Config.DB_PORT,
        user=Config.DB_USER, password=Config.DB_PASSWORD,
        database=Config.DB_NAME, charset='utf8mb4'
    )
    cursor = conn.cursor()

    print("=" * 60)
    print("Alibaba Database Optimization")
    print("=" * 60)

    # ========================================
    # 1. 删除废弃表 user（与 users 重复）
    # ========================================
    print("\n[1] Cleanup obsolete tables")
    execute_sql(cursor, "DROP TABLE IF EXISTS `user`", "Drop obsolete table 'user'")

    # ========================================
    # 2. 统一表引擎和字符集
    # ========================================
    print("\n[2] Standardize engine and charset (InnoDB + utf8mb4)")
    tables_to_fix = [
        'users', 'roles', 'permissions', 'role_permissions',
        'user_roles', 'user_logs',
        'jobs', 'zhaopin_jobs', 'jobs_core', 'jobs_analysis',
        'jobs_company', 'jobs_salary_benefit',
        'all_jobs_merged_physical', 'all_jobs_visualization',
        'clean_jobs', 'clean_zhaopin_jobs', 'clean_job_ids', 'job_ids',
        'city_tier_mapping', 'industry_standard', 'data_quality_log'
    ]
    for table in tables_to_fix:
        execute_sql(cursor,
            f"ALTER TABLE `{table}` ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci",
            f"Table {table}"
        )

    # ========================================
    # 3. 添加 created_at / updated_at 字段
    # ========================================
    print("\n[3] Add timestamp audit fields")
    tables_needing_timestamps = [
        'jobs_core', 'jobs_analysis', 'jobs_company', 'jobs_salary_benefit',
        'all_jobs_merged_physical', 'all_jobs_visualization',
        'clean_jobs', 'clean_zhaopin_jobs', 'clean_job_ids', 'job_ids',
        'city_tier_mapping', 'industry_standard'
    ]
    for table in tables_needing_timestamps:
        add_column_if_not_exists(cursor, table,
            "`created_at` datetime DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'",
            f"{table}.created_at")
        add_column_if_not_exists(cursor, table,
            "`updated_at` datetime DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间'",
            f"{table}.updated_at")

    # ========================================
    # 4. 为外键字段添加索引
    # ========================================
    print("\n[4] Add missing indexes")

    # user_logs
    add_index_if_not_exists(cursor, 'user_logs', '`idx_user_logs_user_id` (`user_id`)', 'idx_user_logs_user_id', 'user_logs.user_id')
    add_index_if_not_exists(cursor, 'user_logs', '`idx_user_logs_created_at` (`created_at`)', 'idx_user_logs_created_at', 'user_logs.created_at')
    add_index_if_not_exists(cursor, 'user_logs', '`idx_user_logs_action` (`action`)', 'idx_user_logs_action', 'user_logs.action')

    # role_permissions
    add_index_if_not_exists(cursor, 'role_permissions', '`idx_rp_role_id` (`role_id`)', 'idx_rp_role_id', 'role_permissions.role_id')
    add_index_if_not_exists(cursor, 'role_permissions', '`idx_rp_permission_id` (`permission_id`)', 'idx_rp_permission_id', 'role_permissions.permission_id')

    # user_roles
    add_index_if_not_exists(cursor, 'user_roles', '`idx_ur_user_id` (`user_id`)', 'idx_ur_user_id', 'user_roles.user_id')
    add_index_if_not_exists(cursor, 'user_roles', '`idx_ur_role_id` (`role_id`)', 'idx_ur_role_id', 'user_roles.role_id')

    # jobs
    add_index_if_not_exists(cursor, 'jobs', '`idx_jobs_city` (`city`)', 'idx_jobs_city', 'jobs.city')
    add_index_if_not_exists(cursor, 'jobs', '`idx_jobs_education` (`education`)', 'idx_jobs_education', 'jobs.education')
    add_index_if_not_exists(cursor, 'jobs', '`idx_jobs_company_name` (`company_name`)', 'idx_jobs_company_name', 'jobs.company_name')
    add_index_if_not_exists(cursor, 'jobs', '`idx_jobs_industry` (`industry`)', 'idx_jobs_industry', 'jobs.industry')

    # zhaopin_jobs
    add_index_if_not_exists(cursor, 'zhaopin_jobs', '`idx_zj_city` (`city`)', 'idx_zj_city', 'zhaopin_jobs.city')
    add_index_if_not_exists(cursor, 'zhaopin_jobs', '`idx_zj_education` (`education`)', 'idx_zj_education', 'zhaopin_jobs.education')
    add_index_if_not_exists(cursor, 'zhaopin_jobs', '`idx_zj_company_name` (`company_name`)', 'idx_zj_company_name', 'zhaopin_jobs.company_name')

    # jobs_core
    add_index_if_not_exists(cursor, 'jobs_core', '`idx_jc_city` (`city`)', 'idx_jc_city', 'jobs_core.city')
    add_index_if_not_exists(cursor, 'jobs_core', '`idx_jc_salary_avg` (`salary_avg`)', 'idx_jc_salary_avg', 'jobs_core.salary_avg')

    # jobs_analysis
    add_index_if_not_exists(cursor, 'jobs_analysis', '`idx_ja_city` (`city`)', 'idx_ja_city', 'jobs_analysis.city')
    add_index_if_not_exists(cursor, 'jobs_analysis', '`idx_ja_education_std` (`education_std`)', 'idx_ja_education_std', 'jobs_analysis.education_std')
    add_index_if_not_exists(cursor, 'jobs_analysis', '`idx_ja_industry_category` (`industry_category`)', 'idx_ja_industry_category', 'jobs_analysis.industry_category')
    add_index_if_not_exists(cursor, 'jobs_analysis', '`idx_ja_company_size` (`company_size`)', 'idx_ja_company_size', 'jobs_analysis.company_size')
    add_index_if_not_exists(cursor, 'jobs_analysis', '`idx_ja_exp_range` (`exp_range`)', 'idx_ja_exp_range', 'jobs_analysis.exp_range')

    # jobs_company
    add_index_if_not_exists(cursor, 'jobs_company', '`idx_jcomp_company_name` (`company_name`)', 'idx_jcomp_company_name', 'jobs_company.company_name')

    # jobs_salary_benefit
    add_index_if_not_exists(cursor, 'jobs_salary_benefit', '`idx_jsb_salary_avg` (`salary_avg`)', 'idx_jsb_salary_avg', 'jobs_salary_benefit.salary_avg')
    add_index_if_not_exists(cursor, 'jobs_salary_benefit', '`idx_jsb_benefit_score` (`benefit_score`)', 'idx_jsb_benefit_score', 'jobs_salary_benefit.benefit_score')

    # all_jobs_merged_physical
    add_index_if_not_exists(cursor, 'all_jobs_merged_physical', '`idx_ajmp_city` (`city`)', 'idx_ajmp_city', 'all_jobs_merged_physical.city')
    add_index_if_not_exists(cursor, 'all_jobs_merged_physical', '`idx_ajmp_company_name` (`company_name`)', 'idx_ajmp_company_name', 'all_jobs_merged_physical.company_name')
    add_index_if_not_exists(cursor, 'all_jobs_merged_physical', '`idx_ajmp_position_name` (`position_name`)', 'idx_ajmp_position_name', 'all_jobs_merged_physical.position_name')

    # all_jobs_visualization
    add_index_if_not_exists(cursor, 'all_jobs_visualization', '`idx_ajv_city_tier` (`city_tier`)', 'idx_ajv_city_tier', 'all_jobs_visualization.city_tier')
    add_index_if_not_exists(cursor, 'all_jobs_visualization', '`idx_ajv_industry_category` (`industry_category`)', 'idx_ajv_industry_category', 'all_jobs_visualization.industry_category')
    add_index_if_not_exists(cursor, 'all_jobs_visualization', '`idx_ajv_benefit_score` (`benefit_score`)', 'idx_ajv_benefit_score', 'all_jobs_visualization.benefit_score')

    # data_quality_log
    add_index_if_not_exists(cursor, 'data_quality_log', '`idx_dql_table_name` (`table_name`)', 'idx_dql_table_name', 'data_quality_log.table_name')
    add_index_if_not_exists(cursor, 'data_quality_log', '`idx_dql_check_time` (`check_time`)', 'idx_dql_check_time', 'data_quality_log.check_time')

    # ========================================
    # 5. 添加 NOT NULL 约束
    # ========================================
    print("\n[5] Add NOT NULL constraints")
    execute_sql(cursor, "ALTER TABLE `users` MODIFY COLUMN `username` varchar(50) NOT NULL COMMENT '用户名' AFTER `id`", "users.username NOT NULL")
    execute_sql(cursor, "ALTER TABLE `users` MODIFY COLUMN `password_hash` varchar(255) NOT NULL COMMENT '密码哈希' AFTER `username`", "users.password_hash NOT NULL")
    execute_sql(cursor, "ALTER TABLE `users` MODIFY COLUMN `status` enum('pending','active','disabled') NOT NULL DEFAULT 'pending' COMMENT '账户状态' AFTER `security_answer`", "users.status NOT NULL")
    execute_sql(cursor, "ALTER TABLE `roles` MODIFY COLUMN `name` varchar(50) NOT NULL COMMENT '角色名称' AFTER `id`", "roles.name NOT NULL")
    execute_sql(cursor, "ALTER TABLE `permissions` MODIFY COLUMN `name` varchar(50) NOT NULL COMMENT '权限名称' AFTER `id`", "permissions.name NOT NULL")
    execute_sql(cursor, "ALTER TABLE `user_logs` MODIFY COLUMN `action` varchar(50) NOT NULL COMMENT '操作类型' AFTER `user_id`", "user_logs.action NOT NULL")

    # ========================================
    # 6. 添加字段注释
    # ========================================
    print("\n[6] Add field comments")
    comments = [
        ("users", "id", "int NOT NULL AUTO_INCREMENT COMMENT '用户ID'"),
        ("users", "email", "varchar(100) DEFAULT NULL COMMENT '邮箱地址'"),
        ("users", "phone", "varchar(20) DEFAULT NULL COMMENT '手机号码'"),
        ("users", "security_question", "varchar(100) DEFAULT NULL COMMENT '安全问题'"),
        ("users", "security_answer", "varchar(100) DEFAULT NULL COMMENT '安全答案'"),
        ("roles", "id", "int NOT NULL AUTO_INCREMENT COMMENT '角色ID'"),
        ("roles", "description", "varchar(200) DEFAULT NULL COMMENT '角色描述'"),
        ("permissions", "id", "int NOT NULL AUTO_INCREMENT COMMENT '权限ID'"),
        ("permissions", "description", "varchar(200) DEFAULT NULL COMMENT '权限描述'"),
        ("permissions", "resource", "varchar(50) DEFAULT NULL COMMENT '资源标识'"),
        ("permissions", "action", "varchar(50) DEFAULT NULL COMMENT '操作类型'"),
        ("user_roles", "user_id", "int NOT NULL COMMENT '用户ID'"),
        ("user_roles", "role_id", "int NOT NULL COMMENT '角色ID'"),
        ("role_permissions", "role_id", "int NOT NULL COMMENT '角色ID'"),
        ("role_permissions", "permission_id", "int NOT NULL COMMENT '权限ID'"),
        ("user_logs", "id", "int NOT NULL AUTO_INCREMENT COMMENT '日志ID'"),
        ("user_logs", "details", "text COMMENT '操作详情'"),
        ("user_logs", "ip_address", "varchar(45) DEFAULT NULL COMMENT '客户端IP'"),
    ]
    for table, col, col_def in comments:
        execute_sql(cursor, f"ALTER TABLE `{table}` MODIFY COLUMN `{col}` {col_def}", f"{table}.{col} COMMENT")

    # ========================================
    # 7. 添加表注释
    # ========================================
    print("\n[7] Add table comments")
    table_comments = {
        'users': '用户表 - 存储系统用户基本信息',
        'roles': '角色表 - 存储系统角色定义',
        'permissions': '权限表 - 存储系统权限定义',
        'user_roles': '用户角色关联表 - 多对多关系',
        'role_permissions': '角色权限关联表 - 多对多关系',
        'user_logs': '用户操作日志表 - 记录用户行为',
        'jobs': '前程无忧岗位原始数据表',
        'zhaopin_jobs': '智联招聘岗位原始数据表',
        'jobs_core': '岗位核心数据表 - 清洗后统一格式',
        'jobs_analysis': '岗位分析数据表 - 可视化分析用',
        'jobs_company': '公司信息表 - 岗位关联公司',
        'jobs_salary_benefit': '薪资福利分析表',
        'all_jobs_merged_physical': '全量合并岗位表 - 物理去重',
        'all_jobs_visualization': '全量可视化数据表',
        'clean_jobs': '清洗后前程无忧岗位数据表',
        'clean_zhaopin_jobs': '清洗后智联岗位数据表',
        'clean_job_ids': '清洗后岗位ID表',
        'job_ids': '岗位ID池表',
        'city_tier_mapping': '城市等级映射表',
        'industry_standard': '行业标准分类表',
        'data_quality_log': '数据质量检查日志表',
    }
    for table, comment in table_comments.items():
        execute_sql(cursor, f"ALTER TABLE `{table}` COMMENT='{comment}'", f"Table {table}")

    # ========================================
    # 8. 添加 users 表索引
    # ========================================
    print("\n[8] Optimize users table indexes")
    add_index_if_not_exists(cursor, 'users', '`idx_users_status` (`status`)', 'idx_users_status', 'users.status')
    add_index_if_not_exists(cursor, 'users', '`idx_users_created_at` (`created_at`)', 'idx_users_created_at', 'users.created_at')

    conn.commit()
    conn.close()
    print("\n" + "=" * 60)
    print("Database optimization completed!")
    print("=" * 60)


if __name__ == '__main__':
    optimize_database()
