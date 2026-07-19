"""
智联招聘数据库操作模块（多线程安全版本）
"""
import json
import time
import logging
import sys
import os
import pymysql
from pymysql.cursors import DictCursor
from pymysql.err import OperationalError, MySQLError

from config import (
    MYSQL_HOST, MYSQL_PORT, MYSQL_USER,
    MYSQL_PASSWORD, MYSQL_DB
)

# 导入规范化表写入模块
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))
from pcwjj.normalized_db import save_to_normalized

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ============================================================
# 连接管理（线程安全）
# ============================================================
import threading
_local = threading.local()


def get_conn():
    """获取（或创建）当前线程的 MySQL 连接，带重试机制"""
    max_retries = 3
    retry_delay = 2
    
    # 检查当前线程是否已有连接
    if not hasattr(_local, 'conn') or _local.conn is None or not _local.conn.open:
        # 如果连接存在但已关闭，先清理
        if hasattr(_local, 'conn') and _local.conn is not None:
            try:
                _local.conn.close()
            except Exception:
                pass
            _local.conn = None
        
        for attempt in range(max_retries):
            try:
                _local.conn = pymysql.connect(
                    host=MYSQL_HOST,
                    port=MYSQL_PORT,
                    user=MYSQL_USER,
                    password=MYSQL_PASSWORD,
                    database=MYSQL_DB,
                    charset="utf8mb4",
                    autocommit=False,
                    cursorclass=DictCursor,
                    connect_timeout=10
                )
                logger.debug(f"线程 {threading.current_thread().name} 数据库连接成功")
                break
            except OperationalError as e:
                logger.warning(f"数据库连接失败 (尝试 {attempt + 1}/{max_retries}): {e}")
                if attempt < max_retries - 1:
                    time.sleep(retry_delay * (attempt + 1))
                else:
                    logger.error(f"数据库连接失败，已达到最大重试次数: {e}")
                    raise
            except MySQLError as e:
                logger.error(f"数据库错误: {e}")
                raise
            except Exception as e:
                logger.error(f"未知数据库错误: {e}")
                raise
    
    return _local.conn


def close_conn():
    """关闭当前线程的连接"""
    if hasattr(_local, 'conn') and _local.conn:
        try:
            if _local.conn.open:
                _local.conn.close()
                logger.debug(f"线程 {threading.current_thread().name} 数据库连接已关闭")
        except Exception as e:
            logger.warning(f"关闭数据库连接时出错: {e}")
        finally:
            _local.conn = None


# ============================================================
# 初始化表结构
# ============================================================
def init_zlp_db():
    """创建智联招聘数据表和任务队列（如果不存在）"""
    try:
        conn = get_conn()
        c = conn.cursor()

        # 创建任务队列表
        c.execute("""
            CREATE TABLE IF NOT EXISTS zlzp_job_ids (
                id          BIGINT AUTO_INCREMENT PRIMARY KEY,
                jobid       VARCHAR(50) UNIQUE COMMENT '职位ID（含CCL前缀）',
                job_type    TINYINT DEFAULT 0 COMMENT '职位类型：0=社会招聘 1=校园招聘',
                status      TINYINT DEFAULT 0 COMMENT '0=待处理 1=成功 2=失败 9=处理中',
                retry       TINYINT DEFAULT 0,
                created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='智联招聘任务队列'
        """)

        # 创建职位数据表
        c.execute("""
            CREATE TABLE IF NOT EXISTS zhaopin_jobs (
                id              BIGINT AUTO_INCREMENT PRIMARY KEY,
                position_id     VARCHAR(50) UNIQUE COMMENT '职位ID',
                job_type        TINYINT DEFAULT 0 COMMENT '职位类型：0=社会招聘 1=校园招聘',
                position_name   VARCHAR(200) COMMENT '职位名称',
                salary          VARCHAR(100) COMMENT '薪资',
                city            VARCHAR(100) COMMENT '城市',
                district        VARCHAR(100) COMMENT '区',
                education       VARCHAR(50) COMMENT '学历要求',
                experience      VARCHAR(50) COMMENT '工作经验',
                work_type       VARCHAR(50) COMMENT '工作性质',
                recruit_number  INT COMMENT '招聘人数',
                job_desc        TEXT COMMENT '岗位描述',
                work_address    VARCHAR(500) COMMENT '工作地址',
                skill_tags      JSON COMMENT '技能标签',
                benefits        JSON COMMENT '公司福利',
                company_name    VARCHAR(200) COMMENT '公司名称',
                industry        VARCHAR(200) COMMENT '行业',
                company_size    VARCHAR(50) COMMENT '公司规模',
                property        VARCHAR(50) COMMENT '企业性质',
                financing_stage VARCHAR(50) COMMENT '融资阶段',
                created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_position_id (position_id),
                INDEX idx_job_type (job_type),
                INDEX idx_company_name (company_name),
                INDEX idx_city (city)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT='智联招聘职位数据'
        """)

        conn.commit()
        logger.info("数据库表初始化完成")
    except MySQLError as e:
        logger.error(f"初始化数据库表失败: {e}")
        raise
    except Exception as e:
        logger.error(f"初始化数据库时发生未知错误: {e}")
        raise


# ============================================================
# 任务队列操作（当前爬虫使用 API 拦截实时保存模式）
# ============================================================
def save_job(jobid, data_dict):
    """保存采集成功的职位数据"""
    conn = None
    c = None
    try:
        conn = get_conn()
        c = conn.cursor()

        # 处理JSON字段
        skill_tags = data_dict.get("技能")
        if isinstance(skill_tags, list):
            skill_tags = json.dumps(skill_tags, ensure_ascii=False)
        
        benefits = data_dict.get("福利")
        if isinstance(benefits, list):
            benefits = json.dumps(benefits, ensure_ascii=False)

        c.execute("""
            INSERT INTO zhaopin_jobs (
                position_id, job_url, position_name, salary, city, district,
                education, experience, work_type, recruit_number,
                job_desc, work_address, skill_tags, benefits,
                company_name, industry, company_size, property, financing_stage
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            ON DUPLICATE KEY UPDATE
                job_url = VALUES(job_url),
                position_name = VALUES(position_name),
                salary = VALUES(salary),
                city = VALUES(city),
                district = VALUES(district),
                education = VALUES(education),
                experience = VALUES(experience),
                work_type = VALUES(work_type),
                recruit_number = VALUES(recruit_number),
                job_desc = VALUES(job_desc),
                work_address = VALUES(work_address),
                skill_tags = VALUES(skill_tags),
                benefits = VALUES(benefits),
                company_name = VALUES(company_name),
                industry = VALUES(industry),
                company_size = VALUES(company_size),
                property = VALUES(property),
                financing_stage = VALUES(financing_stage),
                updated_at = CURRENT_TIMESTAMP
        """, (
            data_dict.get("职位ID"),
            data_dict.get("链接"),
            data_dict.get("职位名称"),
            data_dict.get("薪资"),
            data_dict.get("城市"),
            data_dict.get("区"),
            data_dict.get("学历"),
            data_dict.get("经验"),
            data_dict.get("工作性质"),
            data_dict.get("招聘人数"),
            data_dict.get("岗位描述"),
            data_dict.get("地址"),
            skill_tags,
            benefits,
            data_dict.get("公司"),
            data_dict.get("行业"),
            data_dict.get("公司规模"),
            data_dict.get("企业性质"),
            data_dict.get("融资")
        ))
        
        c.execute(
            "UPDATE zlzp_job_ids SET status = 1 WHERE jobid = %s",
            (jobid,)
        )
        conn.commit()

        # --- 同步写入规范化表 (jobs_core / jobs_analysis / jobs_company) ---
        # 供前端图表和数据页面使用，写入失败不影响原始数据
        try:
            save_to_normalized(conn, 'zhaopin', data_dict,
                               extra={
                                   'job_key': jobid,
                                   'position_id': data_dict.get('职位ID'),
                               },
                               log=logger)
        except Exception as e:
            logger.warning(f"[智联规范化] 写入失败(可忽略): {e}")
            try:
                conn.rollback()
            except Exception:
                pass

        return True
        
    except MySQLError as e:
        logger.error(f"保存 jobid {jobid} 数据失败: {e}")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        raise
    except Exception as e:
        logger.error(f"保存 jobid 数据时发生未知错误: {e}")
        if conn:
            try:
                conn.rollback()
            except Exception:
                pass
        raise
    finally:
        # 释放游标
        if c:
            try:
                c.close()
            except Exception:
                pass



