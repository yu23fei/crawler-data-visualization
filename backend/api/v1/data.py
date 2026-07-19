# data.py - 数据接口模块
# 提供岗位数据的分析、分页查询、筛选等接口
# 核心数据链路：jobs_analysis（分析宽表）→ jobs_core（标准格式）→ jobs_company（公司详情）
# 通过两步JOIN关联实现完整数据展示

import pymysql
from flask import Blueprint, request, jsonify

from backend.core.config import Config
from backend.middleware.auth import token_required, permission_required

data_bp = Blueprint('data', __name__)


def get_db_conn():
    """
    获取数据库连接（通用方法）
    返回 pymysql 连接对象，调用方需自行关闭
    """
    conn = pymysql.connect(
        host=Config.DB_HOST,
        port=Config.DB_PORT,
        user=Config.DB_USER,
        password=Config.DB_PASSWORD,
        database=Config.DB_NAME,
        charset='utf8mb4'
    )
    return conn


@data_bp.route('/api/v2/analysis', methods=['GET'])
@token_required
def get_v2_analysis():
    """
    聚合分析数据接口（v2版本）
    返回15个维度的统计数据，供前端ECharts图表展示：
      1.总览统计  2.城市分布TOP15  3.学历分布  4.薪资等级分布
      5.经验要求分布  6.公司规模分布  7.公司性质分布  8.行业分类统计
      9.城市等级分布  10.城市等级-薪资对比  11.经验-薪资关系
      12.福利评分分布  13.工作类型分布  14.学历-薪资热力图  15.公司交叉统计
    """
    conn = get_db_conn()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    try:
        result = {}

        # 1. 总览统计数据（岗位总数、平均薪资）
        cursor.execute("SELECT COUNT(*) as total, ROUND(COALESCE(AVG(salary_avg), 0), 0) as avg_salary FROM jobs_core")
        row = cursor.fetchone()
        result['overview'] = {
            'total_jobs': row['total'],
            'avg_salary': float(row['avg_salary']) if row['avg_salary'] else 0
        }

        # 获取去重后的公司总数
        cursor.execute("SELECT COUNT(DISTINCT company_name) as cnt FROM jobs_company")
        result['overview']['total_companies'] = cursor.fetchone()['cnt']

        # 获取去重后的城市总数
        cursor.execute("SELECT COUNT(DISTINCT city) as cnt FROM jobs_analysis")
        result['overview']['total_cities'] = cursor.fetchone()['cnt']

        # 2. 城市分布 TOP15（按岗位数降序）
        cursor.execute("SELECT city, COUNT(*) as cnt FROM jobs_analysis GROUP BY city ORDER BY cnt DESC LIMIT 15")
        result['city_distribution'] = [{'name': r['city'], 'value': r['cnt']} for r in cursor.fetchall()]

        # 3. 学历分布（按岗位数降序）
        cursor.execute("SELECT education_std, COUNT(*) as cnt FROM jobs_analysis GROUP BY education_std ORDER BY cnt DESC")
        result['education_distribution'] = [{'name': r['education_std'], 'value': r['cnt']} for r in cursor.fetchall()]

        # 4. 薪资等级分布（使用FIELD函数自定义排序，从低到高排列）
        cursor.execute("SELECT salary_range, COUNT(*) as cnt FROM jobs_analysis GROUP BY salary_range ORDER BY FIELD(salary_range, '0-3k','3-5k','5-8k','8-12k','12-20k','20k+','面议'), cnt DESC")
        result['salary_distribution'] = [{'name': r['salary_range'] or '面议', 'value': r['cnt']} for r in cursor.fetchall()]

        # 5. 经验要求分布
        cursor.execute("SELECT exp_range, COUNT(*) as cnt FROM jobs_analysis GROUP BY exp_range ORDER BY cnt DESC")
        result['experience_distribution'] = [{'name': r['exp_range'] or '未知', 'value': r['cnt']} for r in cursor.fetchall()]

        # 6. 公司规模分布
        cursor.execute("SELECT company_size, COUNT(*) as cnt FROM jobs_analysis GROUP BY company_size ORDER BY cnt DESC")
        result['company_size_distribution'] = [{'name': r['company_size'] or '未知', 'value': r['cnt']} for r in cursor.fetchall()]

        # 7. 公司性质分布 TOP15（国企/私企/外资等）
        cursor.execute("SELECT property, COUNT(*) as cnt FROM jobs_analysis GROUP BY property ORDER BY cnt DESC LIMIT 15")
        result['company_type_distribution'] = [{'name': r['property'] or '未知', 'value': r['cnt']} for r in cursor.fetchall()]

        # 8. 行业分类统计 TOP15
        cursor.execute("SELECT industry_category, COUNT(*) as cnt FROM jobs_analysis GROUP BY industry_category ORDER BY cnt DESC LIMIT 15")
        result['industry_distribution'] = [{'name': r['industry_category'] or '未知', 'value': r['cnt']} for r in cursor.fetchall()]

        # 9. 城市等级分布（一线/新一线/二线/三线/四线）
        cursor.execute("SELECT city_tier, COUNT(*) as cnt FROM jobs_analysis GROUP BY city_tier ORDER BY cnt DESC")
        result['city_tier_distribution'] = [{'name': r['city_tier'], 'value': r['cnt']} for r in cursor.fetchall()]

        # 10. 城市等级-平均薪资对比（过滤薪资为0的无效数据）
        cursor.execute("SELECT city_tier, ROUND(AVG(salary_avg),0) as avg_sal FROM jobs_analysis WHERE salary_avg > 0 GROUP BY city_tier ORDER BY avg_sal DESC")
        result['city_tier_salary'] = [{'name': r['city_tier'], 'value': float(r['avg_sal'])} for r in cursor.fetchall()]

        # 11. 经验要求-平均薪资关系（展示经验与薪资的正相关性）
        cursor.execute("SELECT exp_range, ROUND(AVG(salary_avg),0) as avg_sal FROM jobs_analysis WHERE salary_avg > 0 AND exp_range IS NOT NULL GROUP BY exp_range ORDER BY avg_sal DESC")
        result['experience_salary'] = [{'name': r['exp_range'], 'value': float(r['avg_sal'])} for r in cursor.fetchall()]

        # 12. 福利评分分布（0-7项福利的占比，使用子查询计算总岗位数作为分母）
        cursor.execute("""
        SELECT benefit_score, COUNT(*) as cnt,
            ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM jobs_analysis), 1) as pct
        FROM jobs_analysis
        GROUP BY benefit_score
        ORDER BY benefit_score
        """)
        # 福利评分的可读标签映射
        benefit_labels = {
            0: "无福利", 1: "1项", 2: "2项", 3: "3项",
            4: "4项", 5: "5项", 6: "6项", 7: "7项"
        }
        # 福利评分详细说明
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
                "pct": float(r["pct"]),            # 占比百分比
                "score": score,                     # 原始分值
                "desc": benefit_desc.get(score, "未知")
            })

        # 13. 工作类型分布（全职/兼职/实习等）
        cursor.execute("SELECT work_type, COUNT(*) as cnt FROM jobs_analysis GROUP BY work_type ORDER BY cnt DESC")
        result['work_type_distribution'] = [{'name': r['work_type'] or '未知', 'value': r['cnt']} for r in cursor.fetchall()]

        # 14. 学历-薪资交叉热力图数据（用于ECharts热力图展示，展示各学历层次在不同薪资区间的分布密度）
        cursor.execute("SELECT education_std, salary_range, COUNT(*) as cnt FROM jobs_analysis WHERE salary_range IS NOT NULL GROUP BY education_std, salary_range")
        heatmap = {}       # 存储 "学历|薪资区间" → 岗位数 的映射
        edu_set = set()    # 收集所有出现的学历值（作为X轴）
        sal_set = set()    # 收集所有出现的薪资区间（作为Y轴）
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

        # 15. 公司规模-公司性质交叉统计（用于桑基图或交叉表展示）
        cursor.execute("SELECT company_size, property, COUNT(*) as cnt FROM jobs_analysis GROUP BY company_size, property")
        cross_size_type = {}
        for r in cursor.fetchall():
            key = f"{r['company_size']}|{r['property']}"
            cross_size_type[key] = r['cnt']
        result['company_cross'] = cross_size_type

        return jsonify({"code": 200, "msg": "success", "data": result})
    except Exception as e:
        return jsonify({"code": 500, "msg": "数据查询失败，请稍后重试"})
    finally:
        conn.close()  # 确保无论成功或失败都会关闭连接


@data_bp.route('/api/job/page', methods=['GET'])
@permission_required('view_data')
def job_page():
    """
    分页查询岗位数据
    关联路径：jobs_analysis → jobs_core → jobs_company（两步JOIN获取完整数据）
      - jobs_analysis.id = jobs_core.id（分析表与核心表同ID关联）
      - jobs_core.source_id = jobs_company.id（通过source_id获取公司名称）
    需要 view_data 权限
    """
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 200))
    offset = (page - 1) * size

    conn = get_db_conn()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    # 两步JOIN：先关联jobs_core获取source_id和data_source，再关联jobs_company获取公司名称
    sql = """
        SELECT a.*, co.company_name
        FROM jobs_analysis a
        JOIN jobs_core jc ON a.id = jc.id AND a.source = jc.data_source
        LEFT JOIN jobs_company co ON jc.source_id = co.id AND jc.data_source = co.data_source
        ORDER BY a.id
        LIMIT %s, %s
    """
    cursor.execute(sql, (offset, size))
    records = cursor.fetchall()

    # 查询总记录数（分页计算用）
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
    """
    筛选岗位数据
    支持多维度组合筛选：城市(city)、学历(education)、公司规模(company_size)、行业(industry)、公司性质(company_type)
    筛选条件动态拼接SQL，支持任意条件组合（全部为空时返回所有数据）
    需要 filter_jobs 权限
    """
    # 获取所有筛选参数（均为可选）
    city = request.args.get('city')
    education = request.args.get('education')
    company_size = request.args.get('company_size')
    industry = request.args.get('industry')
    company_type = request.args.get('company_type')
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 200))
    offset = (page - 1) * size

    conn = get_db_conn()
    cursor = conn.cursor(pymysql.cursors.DictCursor)

    # 动态构建WHERE条件：非空参数才加入筛选条件
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

    # 无筛选条件时使用 1=1 作为占位，确保SQL语法正确
    where_clause = " AND ".join(conditions) if conditions else "1=1"

    # 查询数据（通过 jobs_core 中转关联 jobs_company 获取公司名称）
    sql = f"""
        SELECT a.*, co.company_name
        FROM jobs_analysis a
        JOIN jobs_core jc ON a.id = jc.id AND a.source = jc.data_source
        LEFT JOIN jobs_company co ON jc.source_id = co.id AND jc.data_source = co.data_source
        WHERE {where_clause}
        LIMIT %s, %s
    """
    cursor.execute(sql, params + [offset, size])
    records = cursor.fetchall()

    # 查询满足条件的总数（用于前端分页组件）
    count_sql = f"SELECT COUNT(*) as total FROM jobs_analysis a WHERE {where_clause}"
    cursor.execute(count_sql, params)
    total = cursor.fetchone()['total']

    conn.close()

    return jsonify({
        "code": 200,
        "data": records,
        "total": total,
        "page": page,
        "size": size
    })
