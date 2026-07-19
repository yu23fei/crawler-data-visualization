"""数据接口模块

提供岗位数据的分析、分页查询、筛选等接口。
核心数据链路：jobs_analysis（分析宽表）→ jobs_core（标准格式）→ jobs_company（公司详情）。
"""

from contextlib import closing

import pymysql
from flask import Blueprint, request, jsonify

from backend.core.config import Config
from backend.middleware.auth import token_required, permission_required

data_bp = Blueprint('data', __name__)


def _get_db_conn():
    """获取数据库连接"""
    conn = pymysql.connect(
        host=Config.DB_HOST, port=Config.DB_PORT,
        user=Config.DB_USER, password=Config.DB_PASSWORD,
        database=Config.DB_NAME, charset='utf8mb4'
    )
    return conn


@data_bp.route('/api/v2/analysis', methods=['GET'])
@token_required
def get_v2_analysis():
    """聚合分析数据接口（v2版本）

    返回15个维度的统计数据，供前端 ECharts 图表展示。
    """
    conn = _get_db_conn()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    try:
        result = {}

        cursor.execute(
            "SELECT COUNT(*) as total, ROUND(COALESCE(AVG(salary_avg), 0), 0) as avg_salary "
            "FROM jobs_core"
        )
        row = cursor.fetchone()
        result['overview'] = {
            'total_jobs': row['total'],
            'avg_salary': float(row['avg_salary']) if row['avg_salary'] else 0
        }

        cursor.execute("SELECT COUNT(DISTINCT company_name) as cnt FROM jobs_company")
        result['overview']['total_companies'] = cursor.fetchone()['cnt']

        cursor.execute("SELECT COUNT(DISTINCT city) as cnt FROM jobs_analysis")
        result['overview']['total_cities'] = cursor.fetchone()['cnt']

        cursor.execute(
            "SELECT city, COUNT(*) as cnt FROM jobs_analysis "
            "GROUP BY city ORDER BY cnt DESC LIMIT 15"
        )
        result['city_distribution'] = [
            {'name': r['city'], 'value': r['cnt']} for r in cursor.fetchall()
        ]

        cursor.execute(
            "SELECT education_std, COUNT(*) as cnt FROM jobs_analysis "
            "GROUP BY education_std ORDER BY cnt DESC"
        )
        result['education_distribution'] = [
            {'name': r['education_std'], 'value': r['cnt']} for r in cursor.fetchall()
        ]

        cursor.execute(
            "SELECT salary_range, COUNT(*) as cnt FROM jobs_analysis "
            "GROUP BY salary_range ORDER BY FIELD(salary_range, "
            "'0-3k','3-5k','5-8k','8-12k','12-20k','20k+','面议'), cnt DESC"
        )
        result['salary_distribution'] = [
            {'name': r['salary_range'] or '面议', 'value': r['cnt']} for r in cursor.fetchall()
        ]

        cursor.execute(
            "SELECT exp_range, COUNT(*) as cnt FROM jobs_analysis "
            "GROUP BY exp_range ORDER BY cnt DESC"
        )
        result['experience_distribution'] = [
            {'name': r['exp_range'] or '未知', 'value': r['cnt']} for r in cursor.fetchall()
        ]

        cursor.execute(
            "SELECT company_size, COUNT(*) as cnt FROM jobs_analysis "
            "GROUP BY company_size ORDER BY cnt DESC"
        )
        result['company_size_distribution'] = [
            {'name': r['company_size'], 'value': r['cnt']} for r in cursor.fetchall()
        ]

        cursor.execute(
            "SELECT company_nature, COUNT(*) as cnt FROM jobs_analysis "
            "GROUP BY company_nature ORDER BY cnt DESC"
        )
        result['company_nature_distribution'] = [
            {'name': r['company_nature'], 'value': r['cnt']} for r in cursor.fetchall()
        ]

        cursor.execute(
            "SELECT industry_category, COUNT(*) as cnt FROM jobs_analysis "
            "GROUP BY industry_category ORDER BY cnt DESC"
        )
        result['industry_distribution'] = [
            {'name': r['industry_category'], 'value': r['cnt']} for r in cursor.fetchall()
        ]

        cursor.execute(
            "SELECT city_tier, COUNT(*) as cnt FROM jobs_analysis "
            "GROUP BY city_tier ORDER BY cnt DESC"
        )
        result['city_tier_distribution'] = [
            {'name': r['city_tier'], 'value': r['cnt']} for r in cursor.fetchall()
        ]

        cursor.execute("""
            SELECT city_tier, ROUND(AVG(salary_avg), 0) as avg_sal
            FROM jobs_analysis WHERE salary_avg > 0
            GROUP BY city_tier ORDER BY avg_sal DESC
        """)
        result['city_tier_salary'] = [
            {'name': r['city_tier'], 'value': float(r['avg_sal'])} for r in cursor.fetchall()
        ]

        cursor.execute("""
            SELECT exp_range, ROUND(AVG(salary_avg), 0) as avg_sal
            FROM jobs_analysis WHERE salary_avg > 0
            GROUP BY exp_range ORDER BY FIELD(exp_range,
            '无需经验','在校生/应届生','1年经验','1-3年经验','3-5年经验',
            '5-10年经验','10年以上经验'), avg_sal DESC
        """)
        result['experience_salary'] = [
            {'name': r['exp_range'], 'value': float(r['avg_sal'])} for r in cursor.fetchall()
        ]

        cursor.execute(
            "SELECT benefit_score, COUNT(*) as cnt FROM jobs_salary_benefit "
            "GROUP BY benefit_score ORDER BY benefit_score"
        )
        result['benefit_distribution'] = [
            {'name': str(r['benefit_score']), 'value': r['cnt']} for r in cursor.fetchall()
        ]

        cursor.execute(
            "SELECT work_type, COUNT(*) as cnt FROM jobs_analysis "
            "GROUP BY work_type ORDER BY cnt DESC"
        )
        result['work_type_distribution'] = [
            {'name': r['work_type'], 'value': r['cnt']} for r in cursor.fetchall()
        ]

        cursor.execute("""
            SELECT education_std, ROUND(AVG(salary_avg), 0) as avg_sal
            FROM jobs_analysis WHERE salary_avg > 0
            GROUP BY education_std ORDER BY avg_sal DESC
        """)
        result['education_salary'] = [
            {'name': r['education_std'], 'value': float(r['avg_sal'])} for r in cursor.fetchall()
        ]

        cursor.execute("""
            SELECT company_nature, company_size,
                   COUNT(*) as cnt, ROUND(AVG(salary_avg), 0) as avg_sal
            FROM jobs_analysis WHERE salary_avg > 0
            GROUP BY company_nature, company_size ORDER BY cnt DESC
        """)
        result['company_cross'] = cursor.fetchall()

    finally:
        conn.close()

    return jsonify({'code': 200, 'data': result})


@data_bp.route('/api/v2/data', methods=['GET'])
@token_required
def get_v2_data():
    """分页查询岗位数据接口"""
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 50))
    offset = (page - 1) * size

    conn = _get_db_conn()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    cursor.execute("""
        SELECT jc.*, jcomp.company_name, jcomp.company_nature,
               jcomp.company_scale, jcomp.registered_capital
        FROM jobs_core jc
        LEFT JOIN jobs_company jcomp ON jc.company_id = jcomp.id
        ORDER BY jc.id DESC
        LIMIT %s, %s
    """, (offset, size))
    records = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) as total FROM jobs_core")
    total = cursor.fetchone()['total']

    conn.close()

    return jsonify({
        'code': 200,
        'data': {
            'records': records,
            'total': total,
            'page': page,
            'size': size
        }
    })


@data_bp.route('/api/v2/filter', methods=['POST'])
@permission_required('filter_jobs')
def filter_v2_data():
    """多维筛选接口（支持城市、学历、薪资、经验等多条件组合筛选）"""
    data = request.get_json() or {}

    conn = _get_db_conn()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    conditions = []
    params = []

    if data.get('city'):
        conditions.append("ja.city = %s")
        params.append(data['city'])
    if data.get('education'):
        conditions.append("ja.education_std = %s")
        params.append(data['education'])
    if data.get('salary_min'):
        conditions.append("ja.salary_avg >= %s")
        params.append(float(data['salary_min']))
    if data.get('salary_max'):
        conditions.append("ja.salary_avg <= %s")
        params.append(float(data['salary_max']))
    if data.get('experience'):
        conditions.append("ja.exp_range = %s")
        params.append(data['experience'])
    if data.get('industry'):
        conditions.append("ja.industry_category = %s")
        params.append(data['industry'])
    if data.get('company_size'):
        conditions.append("ja.company_size = %s")
        params.append(data['company_size'])
    if data.get('company_nature'):
        conditions.append("ja.company_nature = %s")
        params.append(data['company_nature'])

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    page = int(data.get('page', 1))
    size = int(data.get('size', 50))
    offset = (page - 1) * size

    cursor.execute(f"""
        SELECT ja.*, jc.position_name, jc.salary_avg, jc.salary_range,
               jcomp.company_name, jcomp.company_nature, jcomp.company_scale
        FROM jobs_analysis ja
        JOIN jobs_core jc ON ja.job_core_id = jc.id
        LEFT JOIN jobs_company jcomp ON jc.company_id = jcomp.id
        WHERE {where_clause}
        ORDER BY jc.id DESC LIMIT %s, %s
    """, params + [offset, size])
    records = cursor.fetchall()

    cursor.execute(f"""
        SELECT COUNT(*) as total FROM jobs_analysis ja
        JOIN jobs_core jc ON ja.job_core_id = jc.id
        WHERE {where_clause}
    """, params)
    total = cursor.fetchone()['total']

    conn.close()

    return jsonify({
        'code': 200,
        'data': {
            'records': records,
            'total': total,
            'page': page,
            'size': size
        }
    })


@data_bp.route('/api/v2/filter/options', methods=['GET'])
@token_required
def get_filter_options():
    """获取筛选选项（城市、学历、经验等去重列表）"""
    conn = _get_db_conn()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    cursor.execute(
        "SELECT DISTINCT city FROM jobs_analysis WHERE city IS NOT NULL ORDER BY city"
    )
    cities = [r['city'] for r in cursor.fetchall()]

    cursor.execute(
        "SELECT DISTINCT education_std FROM jobs_analysis "
        "WHERE education_std IS NOT NULL ORDER BY education_std"
    )
    educations = [r['education_std'] for r in cursor.fetchall()]

    cursor.execute(
        "SELECT DISTINCT exp_range FROM jobs_analysis "
        "WHERE exp_range IS NOT NULL ORDER BY exp_range"
    )
    experiences = [r['exp_range'] for r in cursor.fetchall()]

    cursor.execute(
        "SELECT DISTINCT industry_category FROM jobs_analysis "
        "WHERE industry_category IS NOT NULL ORDER BY industry_category"
    )
    industries = [r['industry_category'] for r in cursor.fetchall()]

    cursor.execute(
        "SELECT DISTINCT company_size FROM jobs_analysis "
        "WHERE company_size IS NOT NULL ORDER BY company_size"
    )
    company_sizes = [r['company_size'] for r in cursor.fetchall()]

    cursor.execute(
        "SELECT DISTINCT company_nature FROM jobs_analysis "
        "WHERE company_nature IS NOT NULL ORDER BY company_nature"
    )
    company_natures = [r['company_nature'] for r in cursor.fetchall()]

    conn.close()

    return jsonify({
        'code': 200,
        'data': {
            'cities': cities,
            'educations': educations,
            'experiences': experiences,
            'industries': industries,
            'company_sizes': company_sizes,
            'company_natures': company_natures
        }
    })
