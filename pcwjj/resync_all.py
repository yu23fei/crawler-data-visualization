"""全量重刷脚本：从原始表重建规范化表

用途：
  修复薪资解析 bug 后，从 jobs_51job / zhaopin_jobs / jobs 三张原始表
  重新解析并覆盖写入 jobs_core / jobs_analysis / jobs_company。

用法：
  python pcwjj/resync_all.py            # 只统计，不清空不写入（dry-run）
  python pcwjj/resync_all.py --apply    # 清空规范化表后全量重刷

风险提示：
  --apply 会 TRUNCATE 三张规范化表并重建，执行前请确认数据库可备份。
"""
import os
import sys
import json
import logging
import argparse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pymysql
from pymysql.cursors import DictCursor
from dotenv import load_dotenv

from pcwjj.normalized_db import save_to_normalized

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env'))

MYSQL_HOST = os.environ.get('DB_HOST', '127.0.0.1')
MYSQL_PORT = int(os.environ.get('DB_PORT', 3306))
MYSQL_USER = os.environ.get('DB_USER', 'root')
MYSQL_PASSWORD = os.environ.get('DB_PASSWORD') or os.environ.get('MYSQL_PASSWORD')
MYSQL_DB = os.environ.get('DB_NAME', 'yingjie_spider')

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger('resync_all')


def get_db():
    return pymysql.connect(
        host=MYSQL_HOST, port=MYSQL_PORT,
        user=MYSQL_USER, password=MYSQL_PASSWORD,
        database=MYSQL_DB, charset='utf8mb4',
        autocommit=False, cursorclass=DictCursor, connect_timeout=10,
    )


def _parse_benefits(raw):
    """把 JSON 字符串形式的福利字段解析成列表"""
    if not raw:
        return []
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        try:
            val = json.loads(raw)
            return val if isinstance(val, list) else []
        except Exception:
            return [x.strip() for x in raw.split(',') if x.strip()]
    return []


def build_data_dict(row, source):
    """把原始表行映射为 save_to_normalized 期望的中文字段字典"""
    return {
        '职位名称': row.get('position_name', '') or '',
        '薪资': row.get('salary', '') or '',
        '城市': row.get('city', '') or '',
        '区': row.get('district', '') or '',
        '学历': row.get('education', '') or '',
        '经验': row.get('experience', '') or '',
        '工作性质': row.get('work_type', '') or '',
        '招聘人数': row.get('recruit_number', 0) or 0,
        '岗位描述': row.get('job_desc', '') or '',
        '公司': row.get('company_name', '') or '',
        '行业': row.get('industry', '') or '',
        '公司规模': row.get('company_size', '') or '',
        '企业性质': row.get('property', '') or '',
        '融资': row.get('financing_stage', '') or '',
        '福利': _parse_benefits(row.get('benefits')),
    }


def resync_table(conn, table, source, id_col):
    """重刷单张原始表，返回 (成功数, 失败数)"""
    cur = conn.cursor()
    cur.execute(f'SELECT * FROM `{table}`')
    rows = cur.fetchall()
    cur.close()

    success = 0
    fail = 0
    for row in rows:
        data_dict = build_data_dict(row, source)
        rid = str(row.get(id_col, '') or '')
        if source == 'zhaopin':
            job_key = f'zhaopin_{rid}'
        elif table == 'jobs':
            job_key = f'51job_old_{rid}'   # 旧表用独立前缀，避免与新表 position_id 冲突
        else:
            job_key = f'51job_{rid}'

        result = save_to_normalized(
            conn, 'zhaopin' if source == 'zhaopin' else '51job',
            data_dict, extra={'job_key': job_key, 'jobid': rid}, log=logger,
        )
        if result is not None:
            success += 1
        else:
            fail += 1

    logger.info(f'[重刷] {table}({source}) 共 {len(rows)} 条：成功 {success}，失败 {fail}')
    return success, fail


def main():
    parser = argparse.ArgumentParser(description='全量重刷规范化表')
    parser.add_argument('--apply', action='store_true', help='清空规范化表并执行重刷（否则仅统计）')
    args = parser.parse_args()

    conn = get_db()
    try:
        if args.apply:
            logger.warning('即将清空 jobs_core / jobs_analysis / jobs_company 并重建！')
            cur = conn.cursor()
            for t in ('jobs_core', 'jobs_analysis', 'jobs_company', 'data_quality_log'):
                try:
                    cur.execute(f'TRUNCATE TABLE `{t}`')
                    logger.info(f'已清空表 {t}')
                except Exception as e:
                    logger.warning(f'清空 {t} 失败（可能不存在）: {e}')
            conn.commit()
            cur.close()

            total_s = total_f = 0
            total_s += resync_table(conn, 'jobs_51job', '51job', 'position_id')[0]
            total_s += resync_table(conn, 'zhaopin_jobs', 'zhaopin', 'position_id')[0]
            total_s += resync_table(conn, 'jobs', '51job', 'jobid')[0]

            # 统计重刷结果
            cur = conn.cursor()
            for t in ('jobs_core', 'jobs_analysis', 'jobs_company'):
                cur.execute(f'SELECT COUNT(*) FROM `{t}`')
                logger.info(f'重刷后 {t} 行数: {cur.fetchone()["COUNT(*)"]}')
            cur.execute("""
                SELECT salary_range, COUNT(*) FROM jobs_core
                GROUP BY salary_range ORDER BY COUNT(*) DESC
            """)
            logger.info('重刷后薪资区间分布:')
            for r in cur.fetchall():
                logger.info(f'  {r["salary_range"]!r}: {r["COUNT(*)"]}')
            cur.execute("""
                SELECT ROUND(AVG(CASE WHEN salary_avg>0 THEN salary_avg END),0) AS avg_sal,
                       SUM(salary_avg=0) AS zero_cnt
                FROM jobs_core
            """)
            row = cur.fetchone()
            logger.info(f'重刷后平均工资(非0): {row["avg_sal"]}，面议(0)条数: {row["zero_cnt"]}')
            cur.close()
        else:
            logger.info('dry-run 模式：仅统计原始表条数，不写入。加 --apply 执行真正重刷。')
            cur = conn.cursor()
            for t in ('jobs_51job', 'zhaopin_jobs', 'jobs'):
                cur.execute(f'SELECT COUNT(*) FROM `{t}`')
                logger.info(f'{t} 原始条数: {cur.fetchone()["COUNT(*)"]}')
            cur.close()
    finally:
        conn.close()


if __name__ == '__main__':
    main()
