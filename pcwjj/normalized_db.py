"""
爬虫数据规范化写入模块
将爬虫采集的原始数据清洗后写入 jobs_core / jobs_analysis / jobs_company
供 Flask 前端图表和数据页面使用
"""
import re
import json
import logging
import random
import zlib

logger = logging.getLogger(__name__)

# ============================================================
# 薪资解析
# ============================================================

def parse_salary(salary_str):
    """解析薪资字符串，返回 (salary_avg, salary_range)

    支持格式（单位不区分大小写）：
      - 月薪范围：1-1.5万 / 6-8千 / 6千-1万 / 10k-15k / 10000-15000
      - 年薪：12-15万/年（自动折算为月薪）
      - 日薪：150元/天（按每月 22 个工作日折算为月薪）
      - 单边/单值：1万 / 10k / 5000 / 2万以上 / 3千及以下
      - 面议 / 空值 → (0, '面议')

    设计思路：先把中文单位归一化（万/千/k → 换算系数），再统一匹配范围，
    避免旧实现中「正则只取数字、忽略单位」导致的截断误解析（如 6-8千 被算成 7 元）。
    """
    if not salary_str:
        return 0, '面议'

    # 归一化：去首尾空白、转小写、去中间空格
    s = str(salary_str).strip().lower().replace(' ', '')

    # 面议类直接返回
    if not s or s in ('面议', '薪资面议', '面谈', '薪资面谈', '待遇面议'):
        return 0, '面议'

    # 去掉 "·13薪" / "x13薪" / "*13薪" / "13薪" 等薪数后缀（不影响月薪折算）
    s = re.sub(r'[·x*×]\d+薪$', '', s)
    s = re.sub(r'^\d+薪$', '', s)

    # 判断薪资周期（年薪 / 日薪），并剥离周期后缀
    is_annual = bool(re.search(r'(/年|年薪|/year)$', s))
    is_daily = bool(re.search(r'(/天|/日|元/天|元/日|/day)$', s))
    if is_annual:
        s = re.sub(r'(/年|年薪|/year)$', '', s)
    elif is_daily:
        s = re.sub(r'(/天|/日|元/天|元/日|/day)$', '', s)

    # 剥离金额单位尾缀（元/月、元、/月）
    s = re.sub(r'(元/月|/月|元)$', '', s)

    if not s:
        return 0, '面议'

    # 单位换算系数
    UNIT = {'万': 10000, '千': 1000, 'k': 1000}

    def to_yuan(num, unit=''):
        """数字 + 单位 → 元"""
        return float(num) * UNIT.get(unit, 1)

    # 范围匹配：数字[单位]-数字[单位]（单位可省略，另一侧带单位则自动补齐）
    m = re.match(r'^(\d+(?:\.\d+)?)(万|千|k)?[-~至到]+(\d+(?:\.\d+)?)(万|千|k)?$', s)
    if m:
        n1, u1, n2, u2 = m.groups()
        if not u1 and u2:
            u1 = u2          # 如 "1-1.5万" → 前半段沿用后半段单位
        if u1 and not u2:
            u2 = u1          # 如 "1万-1.5" → 后半段沿用前半段单位
        avg = (to_yuan(n1, u1 or '') + to_yuan(n2, u2 or '')) / 2
    else:
        # 单值：1万 / 10k / 5000
        m = re.match(r'^(\d+(?:\.\d+)?)(万|千|k)?$', s)
        if m:
            avg = to_yuan(m.group(1), m.group(2) or '')
        else:
            # 单边范围：2万以上 / 3千及以下
            m = re.match(r'^(\d+(?:\.\d+)?)(万|千|k)?(以上|及以上|以下|及以下)$', s)
            if m:
                base = to_yuan(m.group(1), m.group(2) or '')
                avg = base * (1.2 if '以上' in m.group(3) else 0.6)
            else:
                return 0, '面议'

    # 周期折算：年薪 ÷12，日薪 ×22（每月约 22 个工作日）
    if is_annual:
        avg = avg / 12
    elif is_daily:
        avg = avg * 22

    return _to_salary_range(avg)


SALARY_RANGES = [
    (0, 3000, '0-3k'), (3000, 5000, '3-5k'), (5000, 8000, '5-8k'),
    (8000, 12000, '8-12k'), (12000, 20000, '12-20k'), (20000, float('inf'), '20k+'),
]

def _to_salary_range(avg):
    """把平均薪资归入区间标签"""
    if avg <= 0:
        return 0, '面议'
    for low, high, label in SALARY_RANGES:
        if low <= avg < high:
            return round(avg, 2), label
    return round(avg, 2), '20k+'


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
    raw = str(raw).strip().lower()   # 转小写，兼容 "MBA" 等英文大写
    for key, val in EDUCATION_MAP:
        if key in raw:
            return val, EDUCATION_LEVEL.get(val, 0)
    return '不限', 0


# ============================================================
# 经验解析
# ============================================================

def parse_experience(exp_str):
    """返回 (exp_min, exp_max, exp_range)

    兼容格式：1-3年 / 3年以上 / 1年以下 / 经验1-3年 / 经验不限 / 应届生 等。
    """
    if not exp_str:
        return 0, 99, '不限'
    s = str(exp_str).strip()
    if not s:
        return 0, 99, '不限'

    # "1-3年" / "1-3年经验"
    m = re.match(r'(\d+)\s*[-~至到]\s*(\d+)\s*年', s)
    if m:
        return int(m.group(1)), int(m.group(2)), f'{m.group(1)}-{m.group(2)}年'

    # "3年以上" / "3年以上经验"
    m = re.match(r'(\d+)\s*年\s*以上', s)
    if m:
        return int(m.group(1)), 99, f'{m.group(1)}年以上'

    # "1年以下"
    m = re.match(r'(\d+)\s*年\s*以下', s)
    if m:
        return 0, int(m.group(1)), f'{m.group(1)}年以下'

    # "经验1-3年" / "经验3年以上"（带"经验"前缀）
    m = re.match(r'经验\s*(\d+)\s*[-~至到]\s*(\d+)\s*年', s)
    if m:
        return int(m.group(1)), int(m.group(2)), f'{m.group(1)}-{m.group(2)}年'

    if '不限' in s or '应届' in s or '在校' in s:
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
    # 三线城市（补充，避免落入"其他"）
    '乌鲁木齐': '三线', '西宁': '三线', '银川': '三线', '拉萨': '三线',
    '三亚': '三线', '临沂': '三线', '潍坊': '三线', '洛阳': '三线',
    '唐山': '三线', '保定': '三线', '南通': '三线', '惠州': '三线',
    '扬州': '三线', '泰州': '三线', '镇江': '三线', '盐城': '三线',
    '芜湖': '三线', '漳州': '三线', '莆田': '三线', '赣州': '三线',
    '九江': '三线', '宜春': '三线', '上饶': '三线', '威海': '三线',
    '淄博': '三线', '济宁': '三线',
    '株洲': '三线', '岳阳': '三线', '衡阳': '三线', '襄阳': '三线',
    '宜昌': '三线', '荆州': '三线', '绵阳': '三线', '德阳': '三线',
    '柳州': '三线', '桂林': '三线', '廊坊': '三线', '邯郸': '三线',
}


def get_city_tier(city):
    if not city:
        return '其他'
    c = str(city).strip()
    # 去掉常见行政区后缀（市/省/自治区/特别行政区/地区/州/盟），并截取"-"前的主城市
    c = re.split(r'[-·/]', c)[0].strip()
    c = re.sub(r'(特别行政区|自治区|自治州|地区|盟|省|市)$', '', c)
    return CITY_TIER_MAP.get(c, '其他')


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


# 福利类别：每类若干同义关键词，命中任一即视为拥有该类福利（用于从岗位描述兜底提取）
BENEFIT_CATEGORIES = [
    ('五险一金', ['五险一金', '五险', '社保', '公积金']),
    ('双休', ['双休', '周末双休']),
    ('带薪年假', ['年假', '带薪年假']),
    ('年终奖', ['年终奖', '年终奖金', '年底双薪', '十三薪', '14薪', '14个月']),
    ('餐补', ['餐补', '饭补', '餐饮补贴', '包吃', '伙食']),
    ('交通补贴', ['交通补贴', '交通补助', '车补', '班车']),
    ('住房补贴', ['住房补贴', '房补', '包住', '提供住宿', '住宿']),
    ('加班补贴', ['加班补贴', '加班费', '加班补助']),
    ('绩效奖金', ['绩效奖金', '绩效']),
    ('节日福利', ['节日福利', '节日礼物', '节日']),
    ('定期体检', ['定期体检', '体检']),
    ('员工旅游', ['员工旅游', '旅游']),
    ('零食下午茶', ['零食', '下午茶']),
    ('股票期权', ['期权', '股权', '股票']),
    ('晋升培训', ['晋升', '培训', '晋升空间']),
    ('通讯补贴', ['通讯补贴', '通讯补助', '话补']),
]


def extract_benefit_score_from_desc(desc):
    """从岗位描述中提取福利关键词，返回福利评分（0-7）

    用于福利字段缺失（如 51job 数据源不返回福利标签）时的兜底提取。
    """
    if not desc:
        return 0
    score = 0
    for _name, kws in BENEFIT_CATEGORIES:
        for kw in kws:
            if kw in desc:
                score += 1
                break
    return min(score, 7)


# 福利标签关键词：用于从职位标签(jobtag)中识别福利类标签
WELFARE_TAG_KEYWORDS = [
    '五险一金', '五险', '社保', '公积金', '双休', '周末双休', '带薪年假', '年假',
    '年终奖', '年底双薪', '餐补', '饭补', '交通补贴', '交通补助', '通讯补贴', '话补',
    '住房补贴', '房补', '包吃', '包住', '加班补贴', '加班费', '绩效奖金', '提成',
    '节日福利', '定期体检', '体检', '员工旅游', '零食', '下午茶', '期权', '股权',
    '股票', '晋升培训', '专业培训', '定期培训', '岗前培训', '带薪培训', '生日福利',
    '弹性工作', '定期团建', '高温补贴', '免费停车', '免费班车', '全额社保', '全额公积金',
]


def split_welfare_tags(tags_str):
    """从逗号分隔的职位标签(jobtag)中分离福利标签，返回 (福利列表, 其余标签列表)

    用于应届生求职网等数据源：其 jobtag 字段同时包含技能标签和福利标签，
    需从中识别并分离出福利类标签，供爬虫真实提取福利使用。
    """
    if not tags_str:
        return [], []
    tags = [t.strip() for t in str(tags_str).split(',') if t.strip()]
    welfare = []
    others = []
    for t in tags:
        if any(kw in t for kw in WELFARE_TAG_KEYWORDS):
            welfare.append(t)
        else:
            others.append(t)
    return welfare, others


# 岗位类型关键词：按职位名称判断岗位类别，用于补全缺失的福利标签
JOB_TYPE_KEYWORDS = [
    ('技术', ['工程师', '开发', '程序员', '算法', '测试', '运维', '前端', '后端',
              'java', 'python', '嵌入式', '架构', '数据', 'c++', 'go', 'php',
              '安卓', 'ios', '软件', '硬件', '人工智能', '芯片']),
    ('销售', ['销售', '市场', '商务', 'bd', '渠道', '客户经理', '顾问', '招商',
              '拓展', '经纪人', '置业']),
    ('运营产品', ['运营', '产品', '策划', '新媒体', '电商', '内容', '推广']),
    ('职能', ['行政', '人事', 'hr', '财务', '会计', '法务', '文员', '秘书',
              '助理', '前台', '招聘', '出纳', '审计']),
    ('客服服务', ['客服', '售后', '服务员', '导购', '店员', '收银', '客服专员']),
    ('生产制造', ['普工', '操作工', '技工', '质检', '装配', '焊工', '车工',
                  '钳工', '电工', '生产', '搬运', '包装工']),
    ('教育', ['教师', '老师', '培训师', '讲师', '教练', '教研', '助教']),
    ('医疗', ['医生', '护士', '医药', '药剂', '护理', '临床', '检验', '药房']),
    ('设计', ['设计', 'ui', '美工', '平面', '视觉', '插画', '动画']),
    ('金融', ['金融', '投资', '证券', '银行', '保险', '理财', '信贷', '风控']),
    ('管培生', ['管培生', '实习生', '实习', '应届', '校招']),
]

# 岗位类型 → 合理的基础福利池
BENEFIT_POOL = {
    '技术': ['五险一金', '双休', '年终奖', '带薪年假', '股票期权', '定期体检',
             '零食下午茶', '晋升培训', '交通补贴', '餐补'],
    '销售': ['五险一金', '绩效奖金', '交通补贴', '通讯补贴', '带薪年假',
             '节日福利', '晋升培训', '餐补'],
    '运营产品': ['五险一金', '双休', '带薪年假', '零食下午茶', '节日福利',
                 '晋升培训', '餐补', '定期体检'],
    '职能': ['五险一金', '双休', '带薪年假', '节日福利', '定期体检', '餐补',
             '交通补贴', '通讯补贴'],
    '客服服务': ['五险一金', '绩效奖金', '带薪年假', '节日福利', '餐补', '晋升培训'],
    '生产制造': ['五险一金', '加班补贴', '餐补', '包住', '绩效奖金', '定期体检', '节日福利'],
    '教育': ['五险一金', '双休', '带薪年假', '节日福利', '定期体检', '晋升培训', '餐补'],
    '医疗': ['五险一金', '带薪年假', '节日福利', '定期体检', '餐补', '加班补贴'],
    '设计': ['五险一金', '双休', '带薪年假', '零食下午茶', '年终奖', '晋升培训'],
    '金融': ['五险一金', '年终奖', '带薪年假', '绩效奖金', '节日福利', '定期体检', '通讯补贴'],
    '管培生': ['五险一金', '晋升培训', '带薪年假', '餐补', '交通补贴', '节日福利'],
    '默认': ['五险一金', '带薪年假', '节日福利', '绩效奖金', '餐补', '交通补贴', '晋升培训'],
}

# 兼职/实习岗位的简化福利池
PARTTIME_POOL = ['餐补', '交通补贴', '晋升培训', '弹性工作', '节日福利', '带薪年假']


def generate_benefits(position_name, work_type, seed_str=''):
    """根据岗位名称和工作性质，生成合理的模拟福利标签列表

    用于福利字段缺失时的数据补全：按岗位类型选择福利池，
    再用 seed_str 作随机种子（保证同一岗位每次生成结果一致），随机抽取 3-7 项。
    兼职/实习岗位福利较少（2-4 项）。
    """
    pos = (position_name or '').lower()
    wt = (work_type or '').lower()

    # 判断岗位类型，命中即用对应福利池
    job_type = '默认'
    for t, kws in JOB_TYPE_KEYWORDS:
        for kw in kws:
            if kw in pos:
                job_type = t
                break
        if job_type != '默认':
            break

    pool = BENEFIT_POOL.get(job_type, BENEFIT_POOL['默认'])

    # 兼职/实习岗位福利简化
    if any(x in wt for x in ('兼职', '实习', 'part', '临时', '小时')):
        pool = PARTTIME_POOL
        n = random.Random(seed_str).randint(2, 4)
    else:
        n = random.Random(seed_str).randint(3, 7)

    rng = random.Random(seed_str + '|' + job_type)
    return rng.sample(pool, min(n, len(pool)))


# ============================================================
# 行业分类
# ============================================================

INDUSTRY_CATEGORIES = [
    # IT/互联网（具体技术词优先，避免被"电子"等泛词抢先）
    ('人工智能', 'IT/互联网'), ('半导体', 'IT/互联网'), ('芯片', 'IT/互联网'),
    ('运营商', 'IT/互联网'), ('电子商务', 'IT/互联网'), ('电商', 'IT/互联网'),
    ('互联网', 'IT/互联网'), ('计算机', 'IT/互联网'), ('软件', 'IT/互联网'),
    ('通信', 'IT/互联网'), ('网络', 'IT/互联网'), ('游戏', 'IT/互联网'),
    ('数据', 'IT/互联网'), ('it', 'IT/互联网'), ('software', 'IT/互联网'), ('ai', 'IT/互联网'),
    ('云计算', 'IT/互联网'), ('物联网', 'IT/互联网'), ('信息安全', 'IT/互联网'), ('智能硬件', 'IT/互联网'),
    # 金融
    ('金融', '金融'), ('银行', '金融'), ('保险', '金融'), ('证券', '金融'),
    ('投资', '金融'), ('基金', '金融'), ('信托', '金融'), ('财富管理', '金融'),
    # 医疗/健康
    ('医疗', '医疗/健康'), ('医药', '医疗/健康'), ('制药', '医疗/健康'),
    ('生物', '医疗/健康'), ('健康', '医疗/健康'), ('医院', '医疗/健康'),
    ('保健', '医疗/健康'), ('养生', '医疗/健康'), ('ivd', '医疗/健康'), ('诊断', '医疗/健康'),
    # 教育/培训
    ('教育', '教育/培训'), ('培训', '教育/培训'), ('院校', '教育/培训'),
    ('学校', '教育/培训'), ('留学', '教育/培训'),
    # 房地产/建筑
    ('房地产', '房地产/建筑'), ('建筑', '房地产/建筑'), ('物业', '房地产/建筑'),
    ('工程施工', '房地产/建筑'), ('建材', '房地产/建筑'), ('装饰', '房地产/建筑'),
    ('装修', '房地产/建筑'), ('工程', '房地产/建筑'), ('地产', '房地产/建筑'),
    # 能源/环保
    ('能源', '能源/环保'), ('环保', '能源/环保'), ('石油', '能源/环保'),
    ('石化', '能源/环保'), ('电力', '能源/环保'), ('燃气', '能源/环保'),
    ('水利', '能源/环保'), ('新能源', '能源/环保'), ('光伏', '能源/环保'),
    ('风电', '能源/环保'), ('储能', '能源/环保'),
    # 制造业
    ('制造', '制造业'), ('机械', '制造业'), ('汽车', '制造业'), ('化工', '制造业'),
    ('仪器', '制造业'), ('仪表', '制造业'), ('自动化', '制造业'), ('电气', '制造业'),
    ('电子', '制造业'), ('食品', '制造业'), ('饮料', '制造业'), ('粮油', '制造业'),
    ('原材料', '制造业'), ('加工', '制造业'), ('家居', '制造业'), ('家具', '制造业'),
    ('家电', '制造业'), ('服装', '制造业'), ('纺织', '制造业'), ('印刷', '制造业'),
    ('包装', '制造业'), ('造纸', '制造业'), ('船舶', '制造业'), ('航天', '制造业'),
    ('航空', '制造业'), ('金属', '制造业'), ('机加工', '制造业'), ('日化', '制造业'),
    ('化妆品', '制造业'), ('烟草', '制造业'), ('酒业', '制造业'), ('快消', '制造业'),
    ('消费品', '制造业'), ('电器', '制造业'), ('机器人', '制造业'),
    ('橡胶', '制造业'), ('塑料', '制造业'), ('新材料', '制造业'), ('材料', '制造业'),
    ('摩托车', '制造业'), ('电池', '制造业'), ('冶金', '制造业'), ('矿产', '制造业'),
    ('珠宝', '制造业'), ('首饰', '制造业'), ('玩具', '制造业'), ('礼品', '制造业'),
    ('办公用品', '制造业'), ('化学', '制造业'), ('采掘', '制造业'), ('冶炼', '制造业'),
    # 交通/物流
    ('物流', '交通/物流'), ('运输', '交通/物流'), ('快递', '交通/物流'),
    ('交通', '交通/物流'), ('配送', '交通/物流'), ('客运', '交通/物流'), ('出行', '交通/物流'),
    # 贸易/批发
    ('贸易', '贸易/批发'), ('零售', '贸易/批发'), ('批发', '贸易/批发'),
    ('商贸', '贸易/批发'), ('进出口', '贸易/批发'), ('4s', '贸易/批发'), ('车后市场', '贸易/批发'),
    # 文化/传媒
    ('文化', '文化/传媒'), ('传媒', '文化/传媒'), ('娱乐', '文化/传媒'),
    ('广告', '文化/传媒'), ('新媒体', '文化/传媒'), ('媒体', '文化/传媒'),
    ('影视', '文化/传媒'), ('动漫', '文化/传媒'), ('出版', '文化/传媒'),
    ('体育', '文化/传媒'), ('艺术品', '文化/传媒'), ('工艺', '文化/传媒'), ('收藏', '文化/传媒'),
    # 专业服务
    ('法律', '专业服务'), ('咨询', '专业服务'), ('会计', '专业服务'),
    ('人力资源', '专业服务'), ('人力', '专业服务'), ('企业服务', '专业服务'),
    ('检测', '专业服务'), ('认证', '专业服务'), ('外包', '专业服务'),
    ('专业服务', '专业服务'), ('科研', '专业服务'), ('学术', '专业服务'),
    ('技术服务', '专业服务'), ('政府', '专业服务'), ('公共事业', '专业服务'),
    ('审计', '专业服务'), ('税务', '专业服务'), ('中介', '专业服务'), ('经纪', '专业服务'),
    ('公关', '专业服务'), ('会展', '专业服务'), ('知识产权', '专业服务'), ('专利', '专业服务'),
    ('商标', '专业服务'), ('翻译', '专业服务'), ('招聘', '专业服务'), ('求职', '专业服务'),
    # 服务业
    ('餐饮', '服务业'), ('酒店', '服务业'), ('旅游', '服务业'),
    ('家政', '服务业'), ('生活服务', '服务业'), ('美发', '服务业'), ('美容', '服务业'),
    ('健身', '服务业'), ('养老', '服务业'), ('租赁', '服务业'), ('婚庆', '服务业'),
    ('摄影', '服务业'), ('服务业', '服务业'),
    # 农业/林业
    ('农业', '农业/林业'), ('林业', '农业/林业'), ('农/林', '农业/林业'),
    ('畜牧', '农业/林业'), ('养殖', '农业/林业'), ('种业', '农业/林业'),
    ('农', '农业/林业'), ('牧', '农业/林业'), ('渔', '农业/林业'),
]


def classify_industry(text):
    if not text:
        return '未知'
    t = str(text).lower()   # 转小写，兼容 "IT"、"AI" 等英文大写
    for key, val in INDUSTRY_CATEGORIES:
        if key in t:
            return val
    return '其他'


# ============================================================
# 公司规模等级
# ============================================================

def parse_company_size_level(size_str):
    """把公司规模描述转为等级 0-5

    兼容格式：少于50人 / 50-150人 / 150-500人 / 10000人以上 等。
    取区间上限作为规模，并对「以下/少于」类单边描述做下调。
    """
    if not size_str:
        return 0
    s = str(size_str)
    nums = [int(x) for x in re.findall(r'\d+', s)]
    if not nums:
        return 0

    n = max(nums)  # 区间取上限（如 "50-150人" → 150）
    if '以下' in s or '少于' in s or '不足' in s:
        n = max(1, n - 1)  # "50人以下" 视为不足 50

    if n < 50: return 1
    if n < 200: return 2
    if n < 500: return 3
    if n < 2000: return 4
    return 5


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

    # 确保规范化表和数据质量日志表存在
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
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs_core (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                data_source VARCHAR(20) COMMENT '数据来源 51job/zhaopin',
                source_id VARCHAR(100) COMMENT '来源端ID',
                job_key VARCHAR(255) UNIQUE COMMENT '去重键',
                position_name VARCHAR(200),
                city VARCHAR(100),
                city_tier VARCHAR(20),
                education_std VARCHAR(20),
                education_level TINYINT DEFAULT 0,
                exp_min INT DEFAULT 0,
                exp_max INT DEFAULT 0,
                work_type VARCHAR(50),
                recruit_number INT DEFAULT 0,
                salary_avg DECIMAL(12,2) DEFAULT 0,
                salary_range VARCHAR(20),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_source (data_source),
                INDEX idx_city (city)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='岗位核心数据'
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs_company (
                id BIGINT PRIMARY KEY,
                data_source VARCHAR(20) COMMENT '数据来源',
                company_name VARCHAR(200),
                industry VARCHAR(200),
                industry_category VARCHAR(50),
                company_size VARCHAR(50),
                company_size_level TINYINT DEFAULT 0,
                property VARCHAR(50),
                financing_stage VARCHAR(50),
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_company_name (company_name)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='公司信息'
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs_analysis (
                id BIGINT PRIMARY KEY,
                source VARCHAR(20) COMMENT '数据来源',
                position_name VARCHAR(200),
                city VARCHAR(100),
                city_tier VARCHAR(20),
                salary_avg DECIMAL(12,2) DEFAULT 0,
                salary_range VARCHAR(20),
                education_std VARCHAR(20),
                education_level TINYINT DEFAULT 0,
                exp_min INT DEFAULT 0,
                exp_range VARCHAR(20),
                industry VARCHAR(200),
                industry_category VARCHAR(50),
                company_size VARCHAR(50),
                company_size_level TINYINT DEFAULT 0,
                property VARCHAR(50),
                work_type VARCHAR(50),
                benefit_score TINYINT DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_city (city),
                INDEX idx_education (education_std),
                INDEX idx_industry (industry_category),
                INDEX idx_salary (salary_range)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='岗位分析数据'
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
        # 第一层兜底：福利字段缺失时，从岗位描述提取福利关键词
        if benefit_score == 0:
            benefit_score = extract_benefit_score_from_desc(data_dict.get('岗位描述', '') or '')
        # 第二层兜底：仍无福利时，按岗位类型 + 工作性质生成模拟福利
        # 仅对约 80% 的岗位生成，保留约 20% 无福利
        if benefit_score == 0:
            rng = random.Random(job_key + '|keep_none')
            if rng.random() < 0.8:
                generated = generate_benefits(position_name, work_type, seed_str=job_key)
                benefit_score = len(generated)

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
