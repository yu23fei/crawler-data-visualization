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
            "SELECT COUNT(*) as total, "
            "ROUND(COALESCE(AVG(CASE WHEN salary_avg > 0 THEN salary_avg END), 0), 0) as avg_salary "
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
            "SELECT property, COUNT(*) as cnt FROM jobs_analysis "
            "GROUP BY property ORDER BY cnt DESC LIMIT 15"
        )
        result['company_type_distribution'] = [
            {'name': r['property'] or '未知', 'value': r['cnt']} for r in cursor.fetchall()
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

        cursor.execute("""
            SELECT benefit_score, COUNT(*) as cnt,
                ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM jobs_analysis), 1) as pct
            FROM jobs_analysis
            GROUP BY benefit_score
            ORDER BY benefit_score
        """)
        benefit_labels = {
            0: "无福利", 1: "1项", 2: "2项", 3: "3项",
            4: "4项", 5: "5项", 6: "6项", 7: "7项"
        }
        benefit_desc = {
            0: "岗位未提供任何福利项",
            1: "仅提供1项福利（多为社保）",
            2: "提供2项福利",
            3: "提供3项福利",
            4: "提供4项福利",
            5: "提供5项福利",
            6: "提供6项及以上福利",
            7: "提供全部7项福利"
        }
        result["benefit_score_distribution"] = []
        for r in cursor.fetchall():
            score = r["benefit_score"]
            result["benefit_score_distribution"].append({
                "name": benefit_labels.get(score, str(score)),
                "value": r["cnt"],
                "pct": float(r["pct"]),
                "score": score,
                "desc": benefit_desc.get(score, "未知")
            })

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
            SELECT education_std, salary_range, COUNT(*) as cnt
            FROM jobs_analysis WHERE salary_range IS NOT NULL
            GROUP BY education_std, salary_range
        """)
        heatmap = {}
        edu_set = set()
        sal_set = set()
        for r in cursor.fetchall():
            edu = r['education_std']
            sal = r['salary_range']
            key = f"{edu}|{sal}"
            heatmap[key] = r['cnt']
            edu_set.add(edu)
            sal_set.add(sal)
        result['heatmap_edu_salary'] = {
            'education': list(edu_set),
            'salary': list(sal_set),
            'data': heatmap
        }

        cursor.execute("""
            SELECT company_size, property, COUNT(*) as cnt
            FROM jobs_analysis GROUP BY company_size, property
        """)
        cross_size_type = {}
        for r in cursor.fetchall():
            key = f"{r['company_size']}|{r['property']}"
            cross_size_type[key] = r['cnt']
        result['company_cross'] = cross_size_type

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
        SELECT jc.*, jcomp.company_name, jcomp.property AS company_nature,
               jcomp.company_size AS company_scale, jcomp.industry
        FROM jobs_core jc
        LEFT JOIN jobs_company jcomp ON jc.source_id = jcomp.id AND jc.data_source = jcomp.data_source
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
    if data.get('company_type'):
        conditions.append("ja.property = %s")
        params.append(data['company_type'])

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    page = int(data.get('page', 1))
    size = int(data.get('size', 50))
    offset = (page - 1) * size

    cursor.execute(f"""
        SELECT ja.*, jc.position_name, jc.salary_avg, jc.salary_range,
               jcomp.company_name, jcomp.property AS company_nature, jcomp.company_size AS company_scale
        FROM jobs_analysis ja
        JOIN jobs_core jc ON ja.id = jc.id AND ja.source = jc.data_source
        LEFT JOIN jobs_company jcomp ON jc.source_id = jcomp.id AND jc.data_source = jcomp.data_source
        WHERE {where_clause}
        ORDER BY jc.id DESC LIMIT %s, %s
    """, params + [offset, size])
    records = cursor.fetchall()

    cursor.execute(f"""
        SELECT COUNT(*) as total FROM jobs_analysis ja
        JOIN jobs_core jc ON ja.id = jc.id AND ja.source = jc.data_source
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
        "SELECT DISTINCT property FROM jobs_analysis "
        "WHERE property IS NOT NULL ORDER BY property"
    )
    company_types = [r['property'] for r in cursor.fetchall()]

    conn.close()

    return jsonify({
        'code': 200,
        'data': {
            'cities': cities,
            'educations': educations,
            'experiences': experiences,
            'industries': industries,
            'company_sizes': company_sizes,
            'company_types': company_types
        }
    })


# ============================================================
# 兼容旧版前端路由（重构后前端尚未更新，需保留以下两个接口）
# 前端 api.js 调用 /api/job/page 和 /api/job/filter
# ============================================================

@data_bp.route('/api/job/page', methods=['GET'])
@permission_required('view_data')
def job_page():
    """分页查询岗位数据（兼容旧版前端路由）

    关联路径：jobs_analysis → jobs_core → jobs_company
    """
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 200))
    offset = (page - 1) * size

    conn = _get_db_conn()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    cursor.execute("""
        SELECT a.*, co.company_name
        FROM jobs_analysis a
        JOIN jobs_core jc ON a.id = jc.id AND a.source = jc.data_source
        LEFT JOIN jobs_company co ON jc.source_id = co.id AND jc.data_source = co.data_source
        ORDER BY a.id
        LIMIT %s, %s
    """, (offset, size))
    records = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) as total FROM jobs_analysis")
    total = cursor.fetchone()['total']

    conn.close()

    return jsonify({
        "code": 200,
        "data": records,
        "total": total,
        "page": page,
        "size": size
    })


@data_bp.route('/api/job/filter', methods=['GET'])
@permission_required('filter_jobs')
def filter_jobs():
    """多维筛选岗位数据（兼容旧版前端路由）

    支持城市、学历、公司规模、行业、公司性质等多条件组合筛选。
    """
    city = request.args.get('city')
    education = request.args.get('education')
    company_size = request.args.get('company_size')
    industry = request.args.get('industry')
    company_type = request.args.get('company_type')
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 200))
    offset = (page - 1) * size

    conn = _get_db_conn()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    conditions = []
    params = []

    if city:
        conditions.append("a.city = %s")
        params.append(city)
    if education:
        conditions.append("a.education_std = %s")
        params.append(education)
    if company_size:
        conditions.append("a.company_size = %s")
        params.append(company_size)
    if industry:
        conditions.append("a.industry_category = %s")
        params.append(industry)
    if company_type:
        conditions.append("a.property = %s")
        params.append(company_type)

    where_clause = " AND ".join(conditions) if conditions else "1=1"

    cursor.execute(f"""
        SELECT a.*, co.company_name
        FROM jobs_analysis a
        JOIN jobs_core jc ON a.id = jc.id AND a.source = jc.data_source
        LEFT JOIN jobs_company co ON jc.source_id = co.id AND jc.data_source = co.data_source
        WHERE {where_clause}
        ORDER BY a.id
        LIMIT %s, %s
    """, params + [offset, size])
    records = cursor.fetchall()

    cursor.execute(f"""
        SELECT COUNT(*) as total FROM jobs_analysis a
        WHERE {where_clause}
    """, params)
    total = cursor.fetchone()['total']

    cursor.execute("SELECT DISTINCT city FROM jobs_analysis WHERE city IS NOT NULL ORDER BY city")
    cities = [r['city'] for r in cursor.fetchall()]

    conn.close()

    return jsonify({
        "code": 200,
        "data": records,
        "total": total,
        "page": page,
        "size": size,
        "filters": {"cities": cities}
    })


# ============================================================
# 岗位详情、收藏、浏览历史接口（VIP/Admin 通用）
# ============================================================

@data_bp.route('/api/job/detail', methods=['GET'])
@permission_required('view_detail')
def job_detail():
    """获取岗位详情

    根据 jobs_analysis.id 和 data_source 查询岗位完整信息，
    关联 jobs_company 获取公司详情。
    """
    job_id = request.args.get('id')
    data_source = request.args.get('source')

    if not job_id or not data_source:
        return jsonify({'code': 400, 'msg': '缺少 id 或 source 参数'}), 400

    conn = _get_db_conn()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    cursor.execute("""
        SELECT a.*, jc.publish_date, jc.recruit_number,
               co.company_name, co.industry AS company_industry,
               co.company_size, co.property AS company_nature,
               co.financing_stage, co.company_intro_clean,
               co.company_logo, co.industry_category
        FROM jobs_analysis a
        JOIN jobs_core jc ON a.id = jc.id AND a.source = jc.data_source
        LEFT JOIN jobs_company co ON jc.source_id = co.id AND jc.data_source = co.data_source
        WHERE a.id = %s AND a.source = %s
    """, (int(job_id), data_source))

    record = cursor.fetchone()
    conn.close()

    if not record:
        return jsonify({'code': 404, 'msg': '岗位不存在'}), 404

    return jsonify({
        'code': 200,
        'data': record
    })


@data_bp.route('/api/job/favorite', methods=['POST'])
@token_required
def add_favorite():
    """收藏岗位"""
    data = request.get_json()
    if not data or 'job_id' not in data or 'data_source' not in data:
        return jsonify({'code': 400, 'msg': '缺少 job_id 或 data_source 参数'}), 400

    user_id = request.current_user['user_id']
    job_id = int(data['job_id'])
    data_source = data['data_source']

    conn = _get_db_conn()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT IGNORE INTO favorites (user_id, job_id, data_source) VALUES (%s, %s, %s)",
            (user_id, job_id, data_source)
        )
        conn.commit()
        inserted = cursor.rowcount > 0
        return jsonify({'code': 200, 'msg': '收藏成功' if inserted else '已收藏过', 'data': {'is_new': inserted}})
    except Exception as e:
        conn.rollback()
        return jsonify({'code': 500, 'msg': '收藏失败'}), 500
    finally:
        conn.close()


@data_bp.route('/api/job/favorite', methods=['DELETE'])
@token_required
def remove_favorite():
    """取消收藏岗位"""
    data = request.get_json()
    if not data or 'job_id' not in data or 'data_source' not in data:
        return jsonify({'code': 400, 'msg': '缺少 job_id 或 data_source 参数'}), 400

    user_id = request.current_user['user_id']
    job_id = int(data['job_id'])
    data_source = data['data_source']

    conn = _get_db_conn()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "DELETE FROM favorites WHERE user_id = %s AND job_id = %s AND data_source = %s",
            (user_id, job_id, data_source)
        )
        conn.commit()
        return jsonify({'code': 200, 'msg': '已取消收藏'})
    except Exception as e:
        conn.rollback()
        return jsonify({'code': 500, 'msg': '取消收藏失败'}), 500
    finally:
        conn.close()


@data_bp.route('/api/job/favorites', methods=['GET'])
@token_required
def get_favorites():
    """获取用户的收藏列表，关联岗位详情"""
    user_id = request.current_user['user_id']
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size

    conn = _get_db_conn()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    cursor.execute("""
        SELECT f.id AS favorite_id, f.job_id, f.data_source, f.created_at AS favorited_at,
               a.*, co.company_name
        FROM favorites f
        JOIN jobs_analysis a ON f.job_id = a.id AND f.data_source = a.source COLLATE utf8mb4_unicode_ci
        LEFT JOIN jobs_core jc ON a.id = jc.id AND a.source = jc.data_source
        LEFT JOIN jobs_company co ON jc.source_id = co.id AND jc.data_source = co.data_source
        WHERE f.user_id = %s
        ORDER BY f.created_at DESC
        LIMIT %s, %s
    """, (user_id, offset, size))

    records = cursor.fetchall()

    cursor.execute(
        "SELECT COUNT(*) as total FROM favorites WHERE user_id = %s",
        (user_id,)
    )
    total = cursor.fetchone()['total']

    conn.close()

    return jsonify({
        'code': 200,
        'data': records,
        'total': total,
        'page': page,
        'size': size
    })


@data_bp.route('/api/job/history', methods=['POST'])
@token_required
def record_history():
    """记录岗位浏览历史

    每次用户进入详情页时调用，自动去重（保留最新浏览时间）。
    """
    data = request.get_json()
    if not data or 'job_id' not in data or 'data_source' not in data:
        return jsonify({'code': 400, 'msg': '缺少 job_id 或 data_source 参数'}), 400

    user_id = request.current_user['user_id']
    job_id = int(data['job_id'])
    data_source = data['data_source']

    conn = _get_db_conn()
    cursor = conn.cursor()

    try:
        cursor.execute(
            "INSERT INTO job_view_history (user_id, job_id, data_source) VALUES (%s, %s, %s)",
            (user_id, job_id, data_source)
        )
        conn.commit()
        return jsonify({'code': 200, 'msg': '记录成功'})
    except Exception as e:
        conn.rollback()
        return jsonify({'code': 500, 'msg': '记录失败'}), 500
    finally:
        conn.close()


@data_bp.route('/api/job/history', methods=['GET'])
@token_required
def get_history():
    """获取用户的浏览历史列表"""
    user_id = request.current_user['user_id']
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 20))
    offset = (page - 1) * size

    conn = _get_db_conn()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    cursor.execute("""
        SELECT h.id AS history_id, h.job_id, h.data_source, h.viewed_at,
               a.*, co.company_name
        FROM job_view_history h
        JOIN jobs_analysis a ON h.job_id = a.id AND h.data_source = a.source COLLATE utf8mb4_unicode_ci
        LEFT JOIN jobs_core jc ON a.id = jc.id AND a.source = jc.data_source
        LEFT JOIN jobs_company co ON jc.source_id = co.id AND jc.data_source = co.data_source
        WHERE h.user_id = %s
        ORDER BY h.viewed_at DESC
        LIMIT %s, %s
    """, (user_id, offset, size))

    records = cursor.fetchall()

    cursor.execute(
        "SELECT COUNT(*) as total FROM (SELECT DISTINCT job_id, data_source FROM job_view_history WHERE user_id = %s) t",
        (user_id,)
    )
    total = cursor.fetchone()['total']

    conn.close()

    return jsonify({
        'code': 200,
        'data': records,
        'total': total,
        'page': page,
        'size': size
    })
