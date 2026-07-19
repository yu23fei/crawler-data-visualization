"""
爬虫数据规范化写入模块
将爬虫采集的原始数据清洗后写入 jobs_core / jobs_analysis / jobs_company
供 Flask 前端图表和数据页面使用
"""
import re
import json
import logging
import zlib

logger = logging.getLogger(__name__)

# ============================================================
# 薪资解析
# ============================================================

def parse_salary(salary_str):
    """解析薪资字符串，返回 (salary_avg, salary_range)"""
    if not salary_str:
        return 0, '面议'
    s = str(salary_str).strip().lower().replace(' ', '')
    if not s or s in ('面议', '薪资面议', ''):
        return 0, '面议'

    # "10k-15k" / "8K-12K"
    m = re.match(r'(\d+(?:\.\d+)?)\s*k\s*[-~至到]\s*(\d+(?:\.\d+)?)\s*k', s)
    if m:
        avg = (float(m.group(1)) + float(m.group(2))) / 2 * 1000
        return _to_salary_range(avg)

    # "1万-1.5万"
    m = re.match(r'(\d+(?:\.\d+)?)\s*万\s*[-~至到]\s*(\d+(?:\.\d+)?)\s*万', s)
    if m:
        avg = (float(m.group(1)) + float(m.group(2))) / 2 * 10000
        return _to_salary_range(avg)

    # "2万以下"
    m = re.match(r'(\d+(?:\.\d+)?)\s*万\s*以下', s)
    if m:
        return _to_salary_range(float(m.group(1)) * 10000 * 0.6)

    # "2万以上"
    m = re.match(r'(\d+(?:\.\d+)?)\s*万\s*以上', s)
    if m:
        return _to_salary_range(float(m.group(1)) * 10000 * 1.2)

    # "10k"
    m = re.match(r'(\d+(?:\.\d+)?)\s*k', s)
    if m:
        return _to_salary_range(float(m.group(1)) * 1000)

    # "1万"
    m = re.match(r'(\d+(?:\.\d+)?)\s*万', s)
    if m:
        return _to_salary_range(float(m.group(1)) * 10000)

    # "10000-15000" 纯数字范围（元）
    m = re.match(r'(\d+)\s*[-~至到]\s*(\d+)', s)
    if m:
        avg = (float(m.group(1)) + float(m.group(2))) / 2
        return _to_salary_range(avg)

    # 单个纯数字（元）
    m = re.match(r'^(\d+)$', s)
    if m:
        return _to_salary_range(float(m.group(1)))

    return 0, '面议'


SALARY_RANGES = [
    (0, 3000, '0-3k'), (3000, 5000, '3-5k'), (5000, 8000, '5-8k'),
    (8000, 12000, '8-12k'), (12000, 20000, '12-20k'), (20000, float('inf'), '20k+'),
]

def _to_salary_range(avg):
    for low, high, label in SALARY_RANGES:
        if low <= avg < high:
            return round(avg, 2), label
    return round(avg, 2), '面议'


# ============================================================
# 学历标准化
# ============================================================

EDUCATION_MAP = [
    ('博士', '博士'), ('博士后', '博士'),
    ('硕士', '硕士'), ('研究生', '硕士'), ('mba', '硕士'),
    ('本科', '本科'), ('学士', '本科'),
    ('大专', '大专'), ('专科', '大专'),
    ('高中', '高中及以下'), ('中专', '高中及以下'), ('中技', '高中及以下'),
    ('初中', '高中及以下'), ('不限', '不限'), ('无', '不限'),
]

EDUCATION_LEVEL = {'博士': 5, '硕士': 4, '本科': 3, '大专': 2, '高中及以下': 1, '不限': 0}


def standardize_education(raw):
    if not raw:
        return '不限', 0
    raw = str(raw).strip()
    for key, val in EDUCATION_MAP:
        if key in raw:
            return val, EDUCATION_LEVEL.get(val, 0)
    return '不限', 0


# ============================================================
# 经验解析
# ============================================================

def parse_experience(exp_str):
    """返回 (exp_min, exp_max, exp_range)"""
    if not exp_str:
        return 0, 99, '不限'
    s = str(exp_str).strip()

    m = re.match(r'(\d+)\s*[-~至到]\s*(\d+)\s*年', s)
    if m:
        return int(m.group(1)), int(m.group(2)), f'{m.group(1)}-{m.group(2)}年'

    m = re.match(r'(\d+)\s*年\s*以下', s)
    if m:
        return 0, int(m.group(1)), f'{m.group(1)}年以下'

    m = re.match(r'(\d+)\s*年\s*以上', s)
    if m:
        return int(m.group(1)), 99, f'{m.group(1)}年以上'

    if '不限' in s or '应届' in s:
        return 0, 0, '应届/不限'

    return 0, 99, '不限'


# ============================================================
# 城市等级
# ============================================================

CITY_TIER_MAP = {
    '北京': '一线', '上海': '一线', '广州': '一线', '深圳': '一线',
    '成都': '新一线', '杭州': '新一线', '重庆': '新一线', '武汉': '新一线',
    '西安': '新一线', '苏州': '新一线', '天津': '新一线', '南京': '新一线',
    '长沙': '新一线', '郑州': '新一线', '东莞': '新一线', '青岛': '新一线',
    '沈阳': '新一线', '宁波': '新一线', '昆明': '新一线',
    '合肥': '二线', '福州': '二线', '哈尔滨': '二线', '济南': '二线',
    '大连': '二线', '厦门': '二线', '长春': '二线', '太原': '二线',
    '贵阳': '二线', '南昌': '二线', '南宁': '二线', '兰州': '二线',
    '石家庄': '二线', '无锡': '二线', '常州': '二线', '佛山': '二线',
    '呼和浩特': '二线', '海口': '二线', '珠海': '二线', '中山': '二线',
    '温州': '二线', '绍兴': '二线', '嘉兴': '二线', '泉州': '二线',
    '徐州': '二线', '烟台': '二线', '金华': '二线',
}


def get_city_tier(city):
    if not city:
        return '其他'
    return CITY_TIER_MAP.get(str(city).strip().rstrip('市'), '其他')


# ============================================================
# 福利评分
# ============================================================

def calc_benefit_score(benefits):
    if not benefits:
        return 0
    if isinstance(benefits, list):
        return min(len(benefits), 7)
    if isinstance(benefits, str):
        items = [x.strip() for x in benefits.split(',') if x.strip()]
        return min(len(items), 7)
    return 0


# ============================================================
# 行业分类
# ============================================================

INDUSTRY_CATEGORIES = [
    ('互联网', 'IT/互联网'), ('电子商务', 'IT/互联网'), ('计算机', 'IT/互联网'),
    ('软件', 'IT/互联网'), ('通信', 'IT/互联网'), ('网络', 'IT/互联网'),
    ('电子', 'IT/互联网'), ('游戏', 'IT/互联网'), ('数据', 'IT/互联网'),
    ('金融', '金融'), ('银行', '金融'), ('保险', '金融'), ('证券', '金融'), ('投资', '金融'),
    ('房地产', '房地产/建筑'), ('建筑', '房地产/建筑'), ('物业', '房地产/建筑'),
    ('教育', '教育/培训'), ('培训', '教育/培训'),
    ('医疗', '医疗/健康'), ('医药', '医疗/健康'), ('制药', '医疗/健康'), ('生物', '医疗/健康'),
    ('制造', '制造业'), ('机械', '制造业'), ('汽车', '制造业'), ('化工', '制造业'),
    ('能源', '能源/环保'), ('环保', '能源/环保'),
    ('贸易', '贸易/批发'), ('零售', '贸易/批发'),
    ('物流', '交通/物流'), ('运输', '交通/物流'), ('快递', '交通/物流'),
    ('餐饮', '服务业'), ('酒店', '服务业'), ('旅游', '服务业'),
    ('文化', '文化/传媒'), ('传媒', '文化/传媒'), ('娱乐', '文化/传媒'), ('广告', '文化/传媒'),
    ('法律', '专业服务'), ('咨询', '专业服务'), ('会计', '专业服务'),
    ('农业', '农业/林业'), ('林业', '农业/林业'),
]


def classify_industry(text):
    if not text:
        return '未知'
    t = str(text)
    for key, val in INDUSTRY_CATEGORIES:
        if key in t:
            return val
    return '其他'


# ============================================================
# 公司规模等级
# ============================================================

def parse_company_size_level(size_str):
    if not size_str:
        return 0
    m = re.search(r'(\d+)', str(size_str))
    if m:
        n = int(m.group(1))
        if n < 50: return 1
        if n < 200: return 2
        if n < 500: return 3
        if n < 2000: return 4
        return 5
    return 0


# ============================================================
# 公司 ID 生成
# ============================================================

def make_company_id(name, data_source):
    """根据公司名+数据源生成稳定的数字公司ID"""
    key = f"{name}_{data_source}"
    return (zlib.crc32(key.encode('utf-8')) & 0x7FFFFFFF) % 9000000 + 1000000


# ============================================================
# 写入规范化表（主入口）
# ============================================================

def save_to_normalized(conn, data_source, data_dict, extra=None, log=None):
    """
    将爬虫数据写入规范化表

    参数:
        conn: MySQL 连接
        data_source: '51job' 或 'zhaopin'
        data_dict: 爬虫解析的原始数据字典
        extra: 附加信息，如 {'position_id': 'xx'}
        log: 日志记录器

    返回:
        core_id (成功) 或 None (失败)
    """
    log = log or logger
    cursor = conn.cursor()

    # 确保数据质量日志表存在
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS data_quality_log (
                id INT AUTO_INCREMENT PRIMARY KEY,
                table_name VARCHAR(100),
                record_id VARCHAR(100),
                issue_type VARCHAR(50),
                issue_desc TEXT,
                raw_data TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)
        conn.commit()
    except Exception:
        conn.rollback()

    # ---- 构建 job_key（去重用） ----
    job_key = ''
    if extra:
        job_key = extra.get('job_key', '') or extra.get('position_id', '') or extra.get('jobid', '') or ''
    if not job_key and data_source == '51job':
        # 前程无忧：用 source_id + position_name 做 key
        job_key = f"51job_{data_dict.get('职位名称', '')}_{data_dict.get('公司名称', '')}"
    if not job_key:
        # 兜底：用随机数（不会去重）
        import random
        job_key = f"auto_{random.randint(100000, 999999)}"

    try:
        # ---- 提取公共字段 ----
        position_name = data_dict.get('职位名称', '') or ''
        salary_raw = data_dict.get('薪资', '') or ''
        salary_avg, salary_range = parse_salary(salary_raw)

        city_raw = data_dict.get('城市', '') or data_dict.get('工作地点', '') or ''
        if '-' in city_raw and not data_dict.get('区'):
            city = city_raw.split('-')[0].strip()
        else:
            city = city_raw

        city_tier = get_city_tier(city)

        education_raw = data_dict.get('学历', '') or ''
        education_std, education_level = standardize_education(education_raw)

        experience_raw = data_dict.get('经验', '') or ''
        exp_min, exp_max, exp_range = parse_experience(experience_raw)

        company_name = data_dict.get('公司', '') or data_dict.get('公司名称', '') or ''
        industry = data_dict.get('行业', '') or ''
        industry_category = classify_industry(industry)

        company_size = data_dict.get('公司规模', '') or ''
        company_size_level = parse_company_size_level(company_size)

        property_val = data_dict.get('企业性质', '') or data_dict.get('公司性质', '') or ''

        work_type = data_dict.get('工作性质', '') or ''

        benefits_raw = data_dict.get('福利', '') or []
        benefit_score = calc_benefit_score(benefits_raw)

        recruit_number = data_dict.get('招聘人数', 0) or 0

        financing_stage = data_dict.get('融资', '') or ''

        # ---- 生成公司 ID ----
        company_id = make_company_id(company_name or position_name, data_source)

        # ---- 写入 jobs_company ----
        cursor.execute("""
            INSERT INTO jobs_company (id, data_source, company_name, industry, industry_category,
                                      company_size, company_size_level, property, financing_stage)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                company_name = VALUES(company_name),
                industry = VALUES(industry),
                industry_category = VALUES(industry_category),
                company_size = VALUES(company_size),
                company_size_level = VALUES(company_size_level),
                property = VALUES(property),
                financing_stage = VALUES(financing_stage)
        """, (company_id, data_source, company_name, industry, industry_category,
              company_size, company_size_level, property_val, financing_stage))

        # ---- 写入 jobs_core（含去重） ----
        cursor.execute("""
            INSERT INTO jobs_core (data_source, source_id, job_key, position_name, city, city_tier,
                                   education_std, education_level, exp_min, exp_max,
                                   work_type, recruit_number, salary_avg, salary_range)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                position_name = VALUES(position_name),
                city = VALUES(city),
                city_tier = VALUES(city_tier),
                education_std = VALUES(education_std),
                education_level = VALUES(education_level),
                exp_min = VALUES(exp_min),
                exp_max = VALUES(exp_max),
                work_type = VALUES(work_type),
                recruit_number = VALUES(recruit_number),
                salary_avg = VALUES(salary_avg),
                salary_range = VALUES(salary_range),
                updated_at = CURRENT_TIMESTAMP
        """, (data_source, company_id, job_key, position_name, city, city_tier,
              education_std, education_level, exp_min, exp_max,
              work_type, recruit_number, salary_avg, salary_range))

        core_id = cursor.lastrowid
        if core_id == 0:
            # ON DUPLICATE KEY UPDATE 后 lastrowid=0，重新查询
            cursor.execute("SELECT id FROM jobs_core WHERE job_key = %s", (job_key,))
            row = cursor.fetchone()
            if row:
                core_id = row[0]

        # ---- 写入 jobs_analysis（含去重） ----
        cursor.execute("""
            INSERT INTO jobs_analysis (id, source, position_name, city, city_tier,
                                       salary_avg, salary_range,
                                       education_std, education_level,
                                       exp_min, exp_range,
                                       industry, industry_category,
                                       company_size, company_size_level,
                                       property, work_type, benefit_score)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                source = VALUES(source),
                position_name = VALUES(position_name),
                city = VALUES(city),
                city_tier = VALUES(city_tier),
                salary_avg = VALUES(salary_avg),
                salary_range = VALUES(salary_range),
                education_std = VALUES(education_std),
                education_level = VALUES(education_level),
                exp_min = VALUES(exp_min),
                exp_range = VALUES(exp_range),
                industry = VALUES(industry),
                industry_category = VALUES(industry_category),
                company_size = VALUES(company_size),
                company_size_level = VALUES(company_size_level),
                property = VALUES(property),
                work_type = VALUES(work_type),
                benefit_score = VALUES(benefit_score)
        """, (core_id, data_source, position_name, city, city_tier,
              salary_avg, salary_range,
              education_std, education_level,
              exp_min, exp_range,
              industry, industry_category,
              company_size, company_size_level,
              property_val, work_type, benefit_score))

        conn.commit()
        log.info(f"[规范化] 写入成功 data_source={data_source} company={company_name} core_id={core_id}")
        return core_id

    except Exception as e:
        try:
            conn.rollback()
        except Exception:
            pass
        log.error(f"[规范化] 写入失败 data_source={data_source}: {e}")
        # 写入数据质量日志
        try:
            c2 = conn.cursor()
            c2.execute("""
                INSERT INTO data_quality_log (table_name, record_id, issue_type, issue_desc, raw_data)
                VALUES (%s, %s, %s, %s, %s)
            """, ('jobs_core', str(extra.get('jobid', '')), 'normalize_error',
                  str(e)[:500], json.dumps(data_dict, ensure_ascii=False)[:1000]))
            conn.commit()
            c2.close()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
        return None
    finally:
        try:
            cursor.close()
        except Exception:
            pass


# ============================================================
# 数据修复工具：从源表重新同步到规范化表
# ============================================================

def resync_from_source(conn, table_name, data_source, log=None):
    """
    从原始数据表重新同步到规范化表
    用于数据出错后的修复

    参数:
        conn: MySQL 连接
        table_name: 源表名 ('jobs' 或 'zhaopin_jobs')
        data_source: '51job' 或 'zhaopin'
        log: 日志记录器

    返回:
        (成功数, 失败数)
    """
    log = log or logger
    cursor = conn.cursor()

    if table_name == 'jobs':
        cursor.execute("SELECT * FROM jobs")
    elif table_name == 'zhaopin_jobs':
        cursor.execute("SELECT * FROM zhaopin_jobs")
    else:
        log.error(f"不支持的表: {table_name}")
        return 0, 0

    rows = cursor.fetchall()
    columns = [desc[0] for desc in cursor.description]
    log.info(f"[修复] 从 {table_name} 读取到 {len(rows)} 条记录")

    success = 0
    fail = 0

    for row in rows:
        row_dict = dict(zip(columns, row))

        if table_name == 'jobs':
            data_dict = {
                '职位名称': row_dict.get('position_name', ''),
                '薪资': row_dict.get('salary', ''),
                '城市': row_dict.get('city', ''),
                '学历': row_dict.get('education', ''),
                '经验': row_dict.get('experience', ''),
                '工作性质': row_dict.get('work_type', ''),
                '招聘人数': row_dict.get('recruit_number', 0),
                '福利': json.loads(row_dict.get('benefits', '[]')) if row_dict.get('benefits') else [],
                '公司名称': row_dict.get('company_name', ''),
                '行业': row_dict.get('industry', ''),
                '公司规模': row_dict.get('company_size', ''),
                '公司性质': row_dict.get('property', ''),
                '公司名称': row_dict.get('company_name', ''),
            }
            jobid = row_dict.get('id', '')
        else:  # zhaopin_jobs
            data_dict = {
                '职位名称': row_dict.get('position_name', ''),
                '薪资': row_dict.get('salary', ''),
                '城市': row_dict.get('city', ''),
                '学历': row_dict.get('education', ''),
                '经验': row_dict.get('experience', ''),
                '工作性质': row_dict.get('work_type', ''),
                '招聘人数': row_dict.get('recruit_number', 0),
                '福利': json.loads(row_dict.get('benefits', '[]')) if row_dict.get('benefits') else [],
                '公司': row_dict.get('company_name', ''),
                '行业': row_dict.get('industry', ''),
                '公司规模': row_dict.get('company_size', ''),
                '企业性质': row_dict.get('property', ''),
            }
            jobid = row_dict.get('position_id', '')

        result = save_to_normalized(conn, data_source, data_dict,
                                    extra={'jobid': jobid}, log=log)
        if result is not None:
            success += 1
        else:
            fail += 1

    cursor.close()
    log.info(f"[修复] 完成: 成功={success}, 失败={fail}")
    return success, fail
