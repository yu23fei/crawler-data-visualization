"""前程无忧 API 拦截采集器（最终稳定版）

51job 受阿里云WAF保护，必须通过浏览器渲染JS才能调通API。
每城市独立上下文，崩溃自动恢复。
"""
import sys, os, time, json, logging, signal, random

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from playwright.sync_api import sync_playwright
from db import init_db, save_job, close_conn

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('yingjie_crawler')

running = True

def signal_handler(signum, frame):
    global running
    logger.info("收到停止信号，正在退出...")
    running = False

signal.signal(signal.SIGTERM, signal_handler)
signal.signal(signal.SIGINT, signal_handler)

CITY_CODES = [
    '010000', '020000', '030200', '040000', '050000',
    '060000', '070200', '070300', '080200', '090200',
    '100200', '110200', '120200', '120300', '130200',
    '140200', '150200', '160200', '170200', '180200',
    '190200', '200200', '210200', '220200', '230200',
    '240200', '250200', '260200', '270200', '280200',
]
CITY_NAMES = [
    '北京', '上海', '广州', '深圳', '天津',
    '武汉', '成都', '重庆', '南京', '杭州',
    '苏州', '西安', '长沙', '郑州', '沈阳',
    '青岛', '大连', '济南', '厦门', '福州',
    '哈尔滨', '合肥', '昆明', '太原', '南昌',
    '南宁', '贵阳', '海口', '兰州', '长春',
]

PAGE_WAIT = 4


def extract_item(item):
    return {
        '职位名称': item.get('jobname', ''),
        '薪资': item.get('providesalary', ''),
        '学历': item.get('degree', ''),
        '经验': item.get('workyear', ''),
        '工作性质': item.get('jobterm', ''),
        '招聘人数': str(item.get('jobnum', 0) or 0),
        '职位描述': item.get('jobdescribe', ''),
        '职位标签': item.get('jobtag', ''),
        '福利': [],
        '公司名称': item.get('coname', ''),
        '行业': item.get('indtype', '') or item.get('coIndustryText', '') or '',
        '公司规模': item.get('cosize', ''),
        '公司性质': item.get('cotype', ''),
        '发布日期': item.get('issuedate', ''),
        '工作地点': item.get('jobarea', ''),
        '公司介绍': '', '更新时间': '', '专业': '', '详细地址': '',
        '链接': f'https://www.yingjiesheng.com/job/{item.get("jobid", "")}',
    }


def crawl_city(playwright, city_code, city_name, seen_ids):
    """使用独立浏览器+上下文采集单个城市"""
    browser = playwright.chromium.launch(
        headless=True,
        args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-blink-features=AutomationControlled'],
    )
    context = browser.new_context(
        viewport={'width': 1400, 'height': 900},
        locale='zh-CN',
        user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36',
    )
    page = context.new_page()
    queue = []
    new_count = 0

    def on_response(response):
        if '/open/noauth/job-v2/recommend' not in response.url:
            return
        if response.status != 200:
            return
        try:
            body = response.json()
            queue.append(body)
        except Exception:
            pass

    page.on('response', on_response)

    try:
        url = f'https://q.yingjiesheng.com/?jobarea={city_code}'
        page.goto(url, wait_until='domcontentloaded', timeout=30000)
        page.wait_for_timeout(PAGE_WAIT * 1000)

        for body in queue:
            items = body.get('resultbody', {}).get('joblist', {}).get('items', [])
            for item in items:
                jobid = item.get('jobid', '')
                if not jobid or jobid in seen_ids:
                    continue
                seen_ids.add(jobid)
                try:
                    save_job(jobid, extract_item(item))
                    new_count += 1
                except Exception as e:
                    logger.warning(f"    [{jobid}] 保存失败: {e}")
    except Exception as e:
        if 'crashed' not in str(e).lower():
            logger.warning(f"  [{city_name}] 异常: {e}")

    try:
        page.close()
    except Exception:
        pass
    try:
        context.close()
    except Exception:
        pass
    try:
        browser.close()
    except Exception:
        pass

    return new_count


def main():
    global running
    logger.info("=" * 60)
    logger.info("前程无忧 API 拦截采集器启动（最终版）")
    logger.info("受阿里云WAF保护，使用独立浏览器采集每个城市")
    logger.info("=" * 60)

    init_db()
    total = 0
    seen_ids = set()

    playwright = sync_playwright().start()

    round_num = 0
    while running:
        round_num += 1
        logger.info(f"\n第 {round_num} 轮（{len(CITY_CODES)} 城市）\n{'='*50}")

        for i, city in enumerate(CITY_CODES):
            if not running:
                break
            city_name = CITY_NAMES[i] if i < len(CITY_NAMES) else city
            logger.info(f"\n[{city_name}] ...")
            n = crawl_city(playwright, city, city_name, seen_ids)
            if n > 0:
                total += n
                logger.info(f"  [{city_name}] ✓ 新增 {n} 条（累计 {total}）")
            else:
                logger.info(f"  [{city_name}] 无新增")
            time.sleep(random.uniform(0.5, 1.5))

        if not running:
            break
        logger.info(f"\n--- 第 {round_num} 轮完成，共 {total} 条，休息 5 秒 ---")
        time.sleep(5)

    try:
        playwright.stop()
    except Exception:
        pass
    close_conn()
    logger.info(f"爬虫退出，共 {total} 条")


if __name__ == '__main__':
    main()