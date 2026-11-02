"""
智联招聘 Playwright 爬虫 v3（带分页）

通过浏览器自动化访问校园招聘 SPA 页面，
拦截 cgate.zhaopin.com API 响应获取职位数据，
自动翻页采集全部搜索结果。
"""
import sys
import os
import time
import json
import logging
import signal
import random
import copy

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
from pcwjj.normalized_db import save_to_normalized

import pymysql
from pymysql.cursors import DictCursor
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '.env'))

MYSQL_HOST = "127.0.0.1"
MYSQL_PORT = 3306
MYSQL_USER = os.environ.get("MYSQL_USER", "root")
MYSQL_PASSWORD = os.environ.get("MYSQL_PASSWORD")
MYSQL_DB = os.environ.get("MYSQL_DB", "yingjie_spider")

from playwright.sync_api import sync_playwright
from playwright_stealth import Stealth

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('zhaopin_pw')

running = True
MAX_PAGES = 5

def signal_handler(signum, frame):
    global running
    logger.info("收到停止信号，正在安全退出...")
    running = False

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)


def get_db():
    return pymysql.connect(
        host=MYSQL_HOST, port=MYSQL_PORT,
        user=MYSQL_USER, password=MYSQL_PASSWORD,
        database=MYSQL_DB, charset="utf8mb4",
        autocommit=False, cursorclass=DictCursor, connect_timeout=10
    )


def init_table():
    try:
        conn = get_db()
        c = conn.cursor()
        c.execute("""
            CREATE TABLE IF NOT EXISTS zhaopin_jobs (
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
                skill_tags JSON COMMENT '技能标签',
                benefits JSON COMMENT '福利标签',
                company_name VARCHAR(200) COMMENT '公司名称',
                industry VARCHAR(200) COMMENT '行业',
                company_size VARCHAR(50) COMMENT '公司规模',
                property VARCHAR(50) COMMENT '企业性质',
                financing_stage VARCHAR(50) COMMENT '融资阶段',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_position_id (position_id),
                INDEX idx_company_name (company_name),
                INDEX idx_city (city)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='智联招聘职位数据'
        """)
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

        skill_tags = job_data.get("技能", [])
        benefits = job_data.get("福利", [])
        skill_json = json.dumps(skill_tags, ensure_ascii=False) if isinstance(skill_tags, list) else "[]"
        benefit_json = json.dumps(benefits, ensure_ascii=False) if isinstance(benefits, list) else "[]"

        c.execute("""
            INSERT INTO zhaopin_jobs (
                position_id, position_name, salary, city, district,
                education, experience, work_type, recruit_number,
                job_desc, work_address, skill_tags, benefits,
                company_name, industry, company_size, property, financing_stage
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                position_name = VALUES(position_name),
                salary = VALUES(salary),
                city = VALUES(city),
                district = VALUES(district),
                updated_at = CURRENT_TIMESTAMP
        """, (
            job_data.get("职位ID"), job_data.get("职位名称"),
            job_data.get("薪资"), job_data.get("城市"),
            job_data.get("区"), job_data.get("学历"),
            job_data.get("经验"), job_data.get("工作性质"),
            job_data.get("招聘人数"), job_data.get("岗位描述"),
            job_data.get("地址"), skill_json, benefit_json,
            job_data.get("公司"), job_data.get("行业"),
            job_data.get("公司规模"), job_data.get("企业性质"),
            job_data.get("融资"),
        ))
        conn.commit()

        try:
            save_to_normalized(conn, 'zhaopin', job_data,
                               extra={'job_key': f"zhaopin_{job_data.get('职位ID', '')}"},
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


def extract_items(api_data: dict) -> list[dict]:
    items = []
    job_list = api_data.get("data", {}).get("list", [])
    if not job_list:
        return items

    for item in job_list:
        if not isinstance(item, dict):
            continue
        number = str(item.get("number", "") or "")
        if not number:
            continue

        financing = item.get("financingStage", {}) or {}
        financing_name = financing.get("name", "") if isinstance(financing, dict) else ""

        welfare = item.get("welfareTagList") or []
        welfare_list = [w for w in welfare if w] if isinstance(welfare, list) else []

        skills = item.get("jobSkillTags") or item.get("skillTags") or []
        skill_names = []
        if isinstance(skills, list):
            for s in skills:
                if isinstance(s, dict):
                    skill_names.append(s.get("name", ""))
                elif isinstance(s, str):
                    skill_names.append(s)

        company = item.get("company") or {}
        company_name = item.get("companyName", "") or company.get("name", "")
        industry = item.get("industryName", "") or company.get("industry", "")
        company_size = item.get("companySize", "") or company.get("size", "")
        company_property = item.get("property", "") or company.get("property", "")

        items.append({
            "职位ID": number,
            "职位名称": str(item.get("name", "") or ""),
            "薪资": str(item.get("salary60", "") or item.get("salary", "") or ""),
            "城市": str(item.get("workCity", "") or ""),
            "区": str(item.get("cityDistrict", "") or ""),
            "学历": str(item.get("education", "") or ""),
            "经验": str(item.get("workingExp", "") or ""),
            "工作性质": str(item.get("workType", "") or item.get("workTypeCode", "") or ""),
            "招聘人数": int(item.get("recruitNumber", 0) or 0),
            "岗位描述": str(item.get("jobSummary", "") or ""),
            "地址": str(item.get("workAddress", "") or ""),
            "公司": company_name,
            "行业": industry,
            "公司规模": company_size,
            "企业性质": company_property,
            "融资": financing_name,
            "福利": welfare_list,
            "技能": skill_names,
        })
    return items


def crawl_once(seen_ids: set) -> int:
    stealth = Stealth()
    collected = []
    first_api_url = None
    first_post_body = None

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/131.0.0.0 Safari/537.36",
                viewport={"width": 1920, "height": 1080},
            )
            page = context.new_page()
            stealth.apply_stealth_sync(page)
            page.set_default_timeout(45000)

            def on_response(response):
                nonlocal first_api_url, first_post_body
                if response.status != 200:
                    return
                url = response.url
                if "searchRecommendCampusForPc" not in url:
                    return
                try:
                    data = response.json()
                    items = extract_items(data)
                    if items:
                        collected.extend(items)
                        if not first_api_url:
                            first_api_url = url
                            first_post_body = response.request.post_data
                        logger.info(f"  [智联API] 捕获 {len(items)} 条")
                except:
                    pass

            page.on("response", on_response)

            logger.info("访问智联校园招聘页面...")
            page.goto("https://xiaoyuan.zhaopin.com/",
                      wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(10000)

            # 翻页采集
            if first_api_url and first_post_body:
                try:
                    base_body = json.loads(first_post_body)
                except:
                    base_body = {"eventScenario": "PCCampusHome", "pageIndex": 1, "pageSize": 12,
                                 "identity": "1", "filterMinSalary": 1, "version": "8.2.6",
                                 "resumeNumber": "", "S_SOU_WORK_CITY": "",
                                 "at": "", "rt": "", "channel": "xiaoyuan",
                                 "platform": "14", "d": ""}
                # 移除城市限制，确保采集全国数据
                base_body.pop("S_SOU_WORK_CITY", None)
                current_page = base_body.get("pageIndex", 1)
                page_size = base_body.get("pageSize", 12)
                logger.info(f"第一页获取 {len(collected)} 条，开始翻页采集...")

                for pg in range(current_page + 1, current_page + MAX_PAGES + 1):
                    if not running:
                        break
                    body = copy.deepcopy(base_body)
                    body["pageIndex"] = pg
                    body_json = json.dumps(body)
                    body_json_escaped = body_json.replace('\\', '\\\\').replace("'", "\\'").replace('"', '\\"')

                    logger.info(f"  翻页 {pg}/{current_page + MAX_PAGES}...")
                    try:
                        js_code = f"""
                            async () => {{
                                const r = await fetch("{first_api_url}", {{
                                    method: "POST",
                                    headers: {{"Content-Type": "application/json"}},
                                    body: '{body_json_escaped}'
                                }});
                                return await r.json();
                            }}
                        """
                        result = page.evaluate(js_code)
                        if result:
                            pg_items = extract_items(result)
                            if pg_items:
                                collected.extend(pg_items)
                                logger.info(f"  第{pg}页获取 {len(pg_items)} 条")
                            else:
                                logger.info(f"  第{pg}页无数据，停止翻页")
                                break
                        else:
                            logger.info(f"  第{pg}页API返回为空，停止翻页")
                            break
                    except Exception as e:
                        logger.warning(f"  第{pg}页请求失败: {e}")
                        break
                    page.wait_for_timeout(random.uniform(1500, 3000))
            else:
                logger.warning("未捕获到智联API，仅使用首页数据")

            browser.close()

    except Exception as e:
        logger.error(f"采集过程异常: {e}")

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
    logger.info("智联招聘 Playwright 爬虫 v3（带翻页）")
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
