"""
MySQL 数据库操作模块
"""
import sys
import os

# 导入规范化表写入模块
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..', '..'))
from pcwjj.normalized_db import save_to_normalized

import json
import time
import logging
import pymysql
from pymysql.cursors import DictCursor
from pymysql.err import OperationalError, MySQLError

from config import (
    MYSQL_HOST, MYSQL_PORT, MYSQL_USER,
    MYSQL_PASSWORD, MYSQL_DB
)

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# ============================================================
# 连接管理
# ============================================================
_conn = None


def get_conn():
    """获取（或创建）当前进程的 MySQL 连接，带重试机制"""
    global _conn
    max_retries = 3
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            if _conn is None or not _conn.open:
                _conn = pymysql.connect(
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
                logger.info("数据库连接成功")
            return _conn
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


def close_conn():
    """关闭当前进程的连接"""
    global _conn
    if _conn:
        try:
            if _conn.open:
                _conn.close()
                logger.info("数据库连接已关闭")
        except Exception as e:
            logger.warning(f"关闭数据库连接时出错: {e}")
        finally:
            _conn = None


# ============================================================
# 初始化表结构
# ============================================================
def init_db():
    """建表（如果不存在），带异常处理"""
    try:
        conn = get_conn()
        c = conn.cursor()

        c.execute("""
            CREATE TABLE IF NOT EXISTS job_ids (
                jobid      BIGINT PRIMARY KEY,
                status     TINYINT DEFAULT 0 COMMENT '0=待处理 1=成功 2=失败 9=处理中',
                retry      TINYINT DEFAULT 0,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """)

        c.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id              BIGINT AUTO_INCREMENT PRIMARY KEY,
                jobid           BIGINT UNIQUE NOT NULL COMMENT '职位ID',
                
                -- 职位基本信息
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
                
                -- 公司信息
                company_name    VARCHAR(200) COMMENT '公司名称',
                industry        VARCHAR(200) COMMENT '行业',
                company_size    VARCHAR(50) COMMENT '公司规模',
                property        VARCHAR(50) COMMENT '企业性质',
                company_intro   TEXT COMMENT '公司介绍',
                company_logo    VARCHAR(500) COMMENT '公司Logo',
                company_id      VARCHAR(50) COMMENT '公司ID',
                
                -- HR信息
                hr_name         VARCHAR(100) COMMENT '发布人',
                hr_position     VARCHAR(100) COMMENT 'HR职位',
                hr_user_id      VARCHAR(50) COMMENT 'HR用户ID',
                hr_active_status VARCHAR(50) COMMENT 'HR活跃状态',
                
                -- 其他信息
                publish_date    VARCHAR(50) COMMENT '发布日期',
                update_time     VARCHAR(50) COMMENT '更新时间',
                major           VARCHAR(100) COMMENT '专业要求',
                detailed_address VARCHAR(500) COMMENT '详细地址',
                
                -- 原始数据（保留）
                raw_data        JSON COMMENT '原始JSON数据',
                
                created_at      DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at      DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                
                INDEX idx_jobid (jobid),
                INDEX idx_company (company_name),
                INDEX idx_city (city),
                INDEX idx_education (education)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COMMENT '职位信息表'
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
    """保存采集成功的职位数据到结构化字段，带异常处理"""
    try:
        conn = get_conn()
        c = conn.cursor()

        # 解析工作地点（例如："深圳-光明区" -> city="深圳", district="光明区"）
        work_address = data_dict.get("工作地点", "")
        city = ""
        district = ""
        if work_address:
            parts = work_address.split("-")
            city = parts[0].strip() if parts else ""
            district = parts[1].strip() if len(parts) > 1 else ""
        
        # 解析招聘人数
        recruit_number = None
        try:
            recruit_num_str = data_dict.get("招聘人数", "")
            if recruit_num_str and recruit_num_str.isdigit():
                recruit_number = int(recruit_num_str)
        except:
            pass
        
        # 解析技能标签（职位标签）
        skill_tags = []
        jobtag = data_dict.get("职位标签", "")
        if jobtag:
            skill_tags = [tag.strip() for tag in jobtag.split(",") if tag.strip()]
        
        # 准备插入数据（仅使用数据库现有字段）
        sql = """
            INSERT INTO jobs (
                jobid, job_url, position_name, salary, city, district, education, experience,
                work_type, recruit_number, job_desc, work_address, skill_tags, benefits,
                company_name, industry, company_size, property, company_intro,
                publish_date, update_time, major, detailed_address
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s
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
                company_intro = VALUES(company_intro),
                publish_date = VALUES(publish_date),
                update_time = VALUES(update_time),
                major = VALUES(major),
                detailed_address = VALUES(detailed_address),
                updated_at = NOW()
        """
        
        c.execute(sql, (
            jobid,
            data_dict.get("链接", ""),
            data_dict.get("职位名称", ""),
            data_dict.get("薪资", ""),
            city,
            district,
            data_dict.get("学历", ""),
            data_dict.get("经验", ""),
            data_dict.get("工作性质", ""),
            recruit_number,
            data_dict.get("职位描述", ""),
            work_address,
            json.dumps(skill_tags, ensure_ascii=False) if skill_tags else None,
            json.dumps(data_dict.get("福利", []), ensure_ascii=False),
            data_dict.get("公司名称", ""),
            data_dict.get("行业", ""),
            data_dict.get("公司规模", ""),
            data_dict.get("公司性质", ""),
            data_dict.get("公司介绍", ""),
            data_dict.get("发布日期", ""),
            data_dict.get("更新时间", ""),
            data_dict.get("专业", ""),
            data_dict.get("详细地址", "")
        ))
        
        c.execute(
            "UPDATE job_ids SET status = 1 WHERE jobid = %s",
            (jobid,)
        )
        conn.commit()
        logger.info(f"成功保存职位 {jobid}: {data_dict.get('职位名称', 'Unknown')}")

        # --- 同步写入规范化表 (jobs_core / jobs_analysis / jobs_company) ---
        # 供前端图表和数据页面使用，写入失败不影响原始数据
        try:
            save_to_normalized(conn, '51job', data_dict,
                               extra={'jobid': jobid},
                               log=logger)
        except Exception as e:
            logger.warning(f"[应届生规范化] 写入失败(可忽略): {e}")
            try:
                conn.rollback()
            except Exception:
                pass

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
