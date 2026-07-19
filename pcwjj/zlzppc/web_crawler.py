"""智联招聘 Playwright 自动爬虫（持续运行版）

通过 Playwright 浏览器自动访问智联校园招聘官网，自动浏览不同分类页面，
拦截页面自身发出的 API 请求，采集职位推荐数据。

浏览器可见，支持人工验证，持续运行直到被手动停止。
"""
import sys, os, time, json, logging, random, signal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from playwright.sync_api import sync_playwright
from zlzp_db import init_zlp_db, save_job, close_conn

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('zhaopin_crawler')

running = True

def signal_handler(signum, frame):
    global running
    logger.info("收到停止信号，正在退出...")
    running = False

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

CAPTCHA_KEYWORDS = ['验证码', 'captcha', '验证', '人机验证', '安全验证', '滑动验证', '请完成验证']


def check_captcha(page) -> bool:
    """检查是否出现验证码"""
    try:
        body = page.inner_text('body').lower()
        for kw in CAPTCHA_KEYWORDS:
            if kw.lower() in body:
                return True
        selectors = [
            'iframe[src*=captcha]', 'iframe[src*=verify]',
            'div[class*=captcha]', 'div[class*=verify]',
            '#captcha', '.captcha-container', '.geetest_panel',
        ]
        for sel in selectors:
            if page.query_selector(sel):
                return True
    except:
        pass
    return False


def wait_captcha(page):
    """检测到验证码时暂停，等待人工处理"""
    logger.warning("=" * 60)
    logger.warning("检测到验证码！请在浏览器窗口中完成验证")
    logger.warning("验证通过后爬虫将自动继续运行")
    logger.warning("=" * 60)
    try:
        page.evaluate("""
            document.querySelectorAll('body > *').forEach(el => {
                el.style.outline = '3px solid red';
            });
        """)
    except:
        pass
    while running:
        time.sleep(2)
        try:
            if not check_captcha(page):
                logger.info("验证码已通过，继续采集")
                return True
        except:
            return False
    return False


def extract_job(item):
    """从 API item 提取数据字典"""
    financing = item.get("financingStage", {}) or {}
    financing_name = financing.get("name", "") if isinstance(financing, dict) else str(financing) if financing else ""

    welfare = item.get("welfareTagList") or []
    welfare_list = [w for w in welfare if w] if isinstance(welfare, list) else []

    skills = item.get("jobSkillTags") or []
    skill_names = [s.get("name", "") for s in skills if isinstance(s, dict)] if isinstance(skills, list) else []

    number = item.get("number", "")
    return {
        "职位ID": number,
        "职位名称": item.get("name", ""),
        "薪资": item.get("salary60", ""),
        "城市": item.get("workCity", ""),
        "区": item.get("cityDistrict", ""),
        "学历": item.get("education", ""),
        "经验": item.get("workingExp", ""),
        "工作性质": item.get("workType", ""),
        "招聘人数": item.get("recruitNumber", 0) or 0,
        "岗位描述": item.get("jobSummary", ""),
        "技能": skill_names,
        "福利": welfare_list,
        "公司": item.get("companyName", ""),
        "行业": item.get("industryName", ""),
        "公司规模": item.get("companySize", ""),
        "企业性质": item.get("property", ""),
        "融资": financing_name,
        "链接": f'https://xiaoyuan.zhaopin.com/job/{number}',
    }


def main():
    global running
    logger.info("=" * 60)
    logger.info("智联招聘 Playwright 自动爬虫启动")
    logger.info("浏览器已打开，如遇验证码请在浏览器中完成验证")
    logger.info("=" * 60)

    init_zlp_db()
    total = 0
    seen_ids = set()

    playwright = sync_playwright().start()
    browser = playwright.chromium.launch(
        headless=False,
        args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-blink-features=AutomationControlled'],
    )
    context = browser.new_context(
        viewport={'width': 1400, 'height': 900},
        locale='zh-CN',
        timezone_id='Asia/Shanghai',
    )
    page = context.new_page()

    response_queue = []

    def on_response(response):
        if not running:
            return
        url = response.url
        if 'zhaopin' in url and 'searchRecommendCampus' in url:
            if response.status != 200:
                return
            try:
                body = response.json()
                items = body.get('data', {}).get('list', [])
                if items:
                    response_queue.append(body)
                    logger.info(f"  [拦截] {len(items)} 条")
            except Exception:
                pass

    page.on('response', on_response)

    def process_queue(label=""):
        nonlocal total, seen_ids
        for body in response_queue:
            items = body.get('data', {}).get('list', [])
            saved = 0
            for item in items:
                number = item.get('number', '')
                if not number or number in seen_ids:
                    continue
                seen_ids.add(number)
                data_dict = extract_job(item)
                try:
                    save_job(number, data_dict)
                    saved += 1
                    total += 1
                except Exception as e:
                    logger.warning(f"  [{number}] 保存失败: {e}")
            if items:
                logger.info(f"  ✓ {label} 保存 {saved}/{len(items)} 条 (累计 {total})")

    def safe_goto(url, label, retries=2):
        for attempt in range(retries):
            if not running:
                return False
            try:
                page.goto(url, wait_until='domcontentloaded', timeout=30000)
                page.wait_for_timeout(2000)
                if check_captcha(page):
                    wait_captcha(page)
                return True
            except Exception as e:
                logger.warning(f"  [{label}] 导航失败(尝试{attempt+1}): {e}")
                time.sleep(1)
        return False

    try:
        while running:
            logger.info("\n--- 开始新一轮采集 ---")

            # 访问首页
            response_queue.clear()
            if safe_goto('https://xiaoyuan.zhaopin.com/', '首页'):
                process_queue('首页')

            if not running:
                break

            # 尝试点击分类标签（如果存在）
            for tab_name, selector in [('按职位筛选', 'div.job-menu__tab-cluster')]:
                if not running:
                    break
                try:
                    tab = page.query_selector(selector)
                    if tab and tab.is_visible():
                        response_queue.clear()
                        logger.info(f"\n[标签] {tab_name}")
                        tab.click()
                        page.wait_for_timeout(4000)
                        if check_captcha(page):
                            wait_captcha(page)
                        process_queue(tab_name)
                except Exception as e:
                    logger.warning(f"  [{tab_name}] 点击失败: {e}")

            # 刷新多轮获取更多推荐
            for round_num in range(5):
                if not running:
                    break
                response_queue.clear()
                label = f"刷新-第{round_num+1}轮"
                if safe_goto('https://xiaoyuan.zhaopin.com/', label):
                    process_queue(label)
                time.sleep(0.3)

            if not running:
                break
            logger.info(f"\n--- 完成一轮采集 (累计 {total} 条)，5 秒后继续 ---")
            time.sleep(5)

    finally:
        logger.info("正在关闭浏览器...")
        try:
            page.close()
        except:
            pass
        try:
            context.close()
        except:
            pass
        browser.close()
        playwright.stop()
        close_conn()
        logger.info(f"爬虫已退出，本轮共采集 {total} 条")


if __name__ == '__main__':
    main()
