"""
前程无忧(应届生) Playwright 爬虫 v4

通过浏览器自动化访问应届生求职网搜索页，
拦截 youngapi.yingjiesheng.com 搜索 API，
采集应届生/校招职位数据。
"""
import sys
import os
import time
import json
import logging
import signal
import random
import threading
import re

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
from pcwjj.normalized_db import save_to_normalized, split_welfare_tags

import pymysql
from pymysql.cursors import DictCursor
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..', '.env'))

MYSQL_HOST = "127.0.0.1"
MYSQL_PORT = 3306
MYSQL_USER = os.environ.get("MYSQL_USER", "root")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD")
MYSQL_DB = os.environ.get("MYSQL_DB", "yingjie_spider")

DB_LOCK = threading.Lock()

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('51job_pw')

running = True

def signal_handler(signum, frame):
    global running
    logger.info("收到停止信号，正在安全退出...")
    running = False

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

SEARCH_KEYWORDS = [
    "python", "java", "前端", "后端", "产品经理", "数据分析",
    "测试", "运维", "算法", "嵌入式", "C++", "Go",
    "销售", "市场", "行政", "财务", "人力资源", "设计",
    "机械", "电气", "化工", "教师", "新媒体", "运营",
    "管培生", "银行", "医药", "建筑", "法律", "翻译",
]


def get_db():
    conn = pymysql.connect(
        host=MYSQL_HOST, port=MYSQL_PORT,
        user=MYSQL_USER, password=MYSQL_PASSWORD,
        database=MYSQL_DB, charset="utf8mb4",
        autocommit=False, cursorclass=DictCursor, connect_timeout=10
    )
    return conn


def init_table():
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS jobs_51job (
                id BIGINT AUTO_INCREMENT PRIMARY KEY,
                position_id VARCHAR(50) UNIQUE COMMENT '职位ID',
                position_name VARCHAR(200) COMMENT '职位名称',
                salary VARCHAR(100) COMMENT '薪资',
                city VARCHAR(100) COMMENT '城市',
                district VARCHAR(100) COMMENT '区',
                education VARCHAR(50) COMMENT '学历',
                experience VARCHAR(50) COMMENT '经验',
                work_type VARCHAR(50) COMMENT '工作性质',
                recruit_number INT COMMENT '招聘人数',
                job_desc TEXT COMMENT '岗位描述',
                work_address VARCHAR(500) COMMENT '工作地址',
                benefits JSON COMMENT '福利标签',
                company_name VARCHAR(200) COMMENT '公司名称',
                industry VARCHAR(200) COMMENT '行业',
                company_size VARCHAR(50) COMMENT '公司规模',
                property VARCHAR(50) COMMENT '企业性质',
                publish_date VARCHAR(50) COMMENT '发布日期',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_position_id (position_id),
                INDEX idx_company (company_name),
                INDEX idx_city (city)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='前程无忧职位数据'
        """)
        # 兼容旧表：如果 benefits 列不存在则自动添加
        try:
            c.execute("ALTER TABLE jobs_51job ADD COLUMN benefits JSON COMMENT '福利标签' AFTER work_address")
            logger.info("已为 jobs_51job 表添加 benefits 列")
        except Exception:
            pass  # 列已存在，忽略
        conn.commit()
        conn.close()
        logger.info("数据库表初始化完成")
    except Exception as e:
        logger.error(f"初始化数据库表失败: {e}")


def save_job(job_data: dict):
    conn = None
    c = None
    try:
        conn = get_db()
        c = conn.cursor()
        welfare = job_data.get("福利", [])
        benefit_json = json.dumps(welfare, ensure_ascii=False) if isinstance(welfare, list) else "[]"
        c.execute("""
            INSERT INTO jobs_51job (
                position_id, position_name, salary, city, district,
                education, experience, work_type, recruit_number,
                job_desc, work_address, benefits, company_name, industry,
                company_size, property, publish_date
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                position_name = VALUES(position_name),
                salary = VALUES(salary), city = VALUES(city),
                benefits = VALUES(benefits),
                updated_at = CURRENT_TIMESTAMP
        """, (
            job_data.get("职位ID"), job_data.get("职位名称"),
            job_data.get("薪资"), job_data.get("城市"),
            job_data.get("区"), job_data.get("学历"),
            job_data.get("经验"), job_data.get("工作性质"),
            job_data.get("招聘人数"), job_data.get("岗位描述"),
            job_data.get("地址"), benefit_json, job_data.get("公司"),
            job_data.get("行业"), job_data.get("公司规模"),
            job_data.get("企业性质"), job_data.get("日期"),
        ))
        conn.commit()

        try:
            save_to_normalized(conn, '51job', job_data,
                               extra={'job_key': f"51job_{job_data.get('职位ID', '')}"},
                               log=logger)
        except Exception as e:
            logger.warning(f"[规范化] 写入失败(可忽略): {e}")
            try: conn.rollback()
            except: pass

        return True
    except Exception as e:
        logger.error(f"保存失败 {job_data.get('职位ID')}: {e}")
        if conn:
            try: conn.rollback()
            except: pass
        return False
    finally:
        if c:
            try: c.close()
            except: pass
        if conn:
            try: conn.close()
            except: pass


def extract_item_from_search(job: dict) -> dict:
    """从应届生搜索API的职位对象中提取标准化字段"""
    area_str = str(job.get("jobarea", "") or "")
    city = area_str
    district = ""
    if "-" in area_str:
        parts = area_str.split("-")
        city = parts[0].strip()
        district = parts[1].strip() if len(parts) > 1 else ""
    elif "·" in area_str:
        parts = area_str.split("·")
        city = parts[0].strip()
        district = parts[1].strip() if len(parts) > 1 else ""

    salary = str(job.get("providesalary", "") or "")

    # 解析招聘人数（从 "招1人" 中提取数字）
    recruit_text = str(job.get("jobRecruitCountText", "") or "")
    recruit_num = 0
    if recruit_text:
        m = re.search(r'(\d+)', recruit_text)
        if m:
            recruit_num = int(m.group(1))

    # 从职位标签(jobtag)中分离福利标签和技能标签（真实提取，非生成）
    jobtag = str(job.get("jobtag", "") or "")
    welfare, skills = split_welfare_tags(jobtag)

    return {
        "职位ID": str(job.get("jobid", "") or ""),
        "职位名称": str(job.get("jobname", "") or ""),
        "薪资": salary,
        "城市": city,
        "区": district,
        "学历": str(job.get("degree", "") or ""),
        "经验": str(job.get("workyear", "") or ""),
        "工作性质": str(job.get("jobterm", "") or ""),
        "招聘人数": recruit_num,
        "岗位描述": str(job.get("jobDescribe", "") or ""),
        "地址": str(job.get("workAddress", "") or ""),
        "公司": str(job.get("coname", "") or ""),
        "行业": str(job.get("coIndustryAllText", "") or job.get("coIndustryText", "") or job.get("indtype", "") or ""),
        "公司规模": str(job.get("cosize", "") or ""),
        "企业性质": str(job.get("cotype", "") or ""),
        "日期": str(job.get("issuedate", "") or ""),
        "福利": welfare,
        "技能": skills,
    }


def extract_items(api_data: dict) -> list[dict]:
    """从应届生搜索API响应中提取标准化职位数据"""
    items = []
    rb = api_data.get("resultbody", {})
    if not rb:
        return items

    # 应届生搜索API格式: resultbody.searchData.joblist.items
    search_data = rb.get("searchData", {})
    joblist = search_data.get("joblist", {})
    raw_list = joblist.get("items") or []
    for raw in raw_list:
        if not raw or not isinstance(raw, dict):
            continue
        item = extract_item_from_search(raw)
        if item and item.get("职位ID"):
            items.append(item)

    return items


def crawl_once(seen_ids: set) -> int:
    """执行一次采集"""
    stealth = Stealth()
    collected = []
    page = None
    context = None
    browser = None

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True, args=["--disable-blink-features=AutomationControlled"])
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
            )
            page = context.new_page()
            stealth.apply_stealth_sync(page)
            page.set_default_timeout(60000)

            def on_response(response):
                if response.status != 200:
                    return
                url = response.url
                if "open/noauth/job/search" not in url:
                    return
                try:
                    data = response.json()
                    if data.get("status") != "1":
                        return
                    items = extract_items(data)
                    if items:
                        collected.extend(items)
                        logger.info(f"  捕获 {len(items)} 条职位")
                except:
                    pass

            page.on("response", on_response)

            keyword = random.choice(SEARCH_KEYWORDS)
            logger.info(f"访问应届生求职网搜索页，关键词: {keyword}")

            search_url = f"https://q.yingjiesheng.com/jobs/search/{keyword}"
            page.goto(search_url, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(10000)

            if collected:
                logger.info(f"关键词 '{keyword}' 采集 {len(collected)} 条")
            else:
                logger.warning(f"关键词 '{keyword}' 未捕获到数据")

            browser.close()
            browser = None

    except Exception as e:
        logger.error(f"采集过程异常: {e}")
        if browser:
            try: browser.close()
            except: pass

    new_count = 0
    for item in collected:
        jid = item.get("职位ID", "")
        if not jid or jid in seen_ids:
            continue
        seen_ids.add(jid)
        if save_job(item):
            new_count += 1

    logger.info(f"本次获取 {len(collected)} 条，新增 {new_count} 条")
    return new_count


def main():
    global running
    logger.info("=" * 60)
    logger.info("前程无忧(应届生) Playwright 爬虫 v4")
    logger.info("=" * 60)

    init_table()

    total = 0
    seen_ids: set[str] = set()
    round_num = 0

    while running:
        round_num += 1
        logger.info(f"\n第 {round_num} 轮开始（累计 {total} 条）")
        n = crawl_once(seen_ids)
        total += n
        logger.info(f"第 {round_num} 轮完成，新增 {n}，累计 {total}")

        if not running:
            break
        wait = random.uniform(30, 60)
        logger.info(f"休息 {wait:.0f} 秒...")
        time.sleep(wait)

    logger.info(f"爬虫退出，共采集 {total} 条")


if __name__ == "__main__":
    main()
