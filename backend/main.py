# main.py - Flask应用入口
# 注册蓝图、配置跨域、初始化数据库，并包含遗留 API 和管理员数据库管理接口
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
import pymysql
import subprocess
import os
import signal
import datetime

from backend.api.v1.admin import admin_bp
from backend.api.v1.auth import auth_bp
from backend.api.v1.data import data_bp
from backend.core.config import Config
from backend.core.init_db import init_database
from backend.middleware.auth import token_required, role_required
from backend.utils.security import add_to_blacklist, audit_log

# React 构建输出目录（前后端同端口部署）
REACT_BUILD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'frontend', 'build')

app = Flask(__name__,
    template_folder=REACT_BUILD_DIR,
    static_folder=os.path.join(REACT_BUILD_DIR, 'static'),
    static_url_path='/static'
)
# Flask签名密钥（用于session、flash等内置功能）
app.secret_key = Config.SECRET_KEY
# 跨域配置：前后端同端口部署，无需跨域，保留为开发时兼容
CORS(app, supports_credentials=True)


# 安全HTTP响应头中间件 —— 每次响应后自动添加安全头
@app.after_request
def add_security_headers(response):
    # 禁止浏览器嗅探MIME类型
    response.headers['X-Content-Type-Options'] = 'nosniff'
    # 禁止页面被嵌入iframe（防止点击劫持）
    response.headers['X-Frame-Options'] = 'DENY'
    # 启用XSS过滤器
    response.headers['X-XSS-Protection'] = '1; mode=block'
    # 严格限制资源加载来源（CSP基础策略）
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; img-src 'self' data:"
    # 禁止浏览器自动检测HTTP请求的编码
    response.headers['X-Content-Type-Options'] = 'nosniff'
    # 禁用自动渲染（部分浏览器）
    response.headers['X-Download-Options'] = 'noopen'
    return response

# 注册蓝图
app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(data_bp)

# MySQL数据库配置
DB_CONFIG = {
    "host": Config.DB_HOST,
    "port": Config.DB_PORT,
    "user": Config.DB_USER,
    "password": Config.DB_PASSWORD,
    "database": Config.DB_NAME,
    "charset": "utf8mb4"
}

def get_db_conn():
    """获取数据库连接和 DictCursor 游标（用于遗留 API）"""
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor(cursor=pymysql.cursors.DictCursor)
    return conn, cursor

# 首页
@app.route('/')
def index():
    return render_template('index.html')

# 全量数据接口 - jobs表(前程无忧)，需登录后访问
@app.route('/api/jobData')
@token_required
def get_all_job():
    conn, cursor = get_db_conn()
    sql = "SELECT * FROM jobs;"
    cursor.execute(sql)
    data = cursor.fetchall()
    conn.close()
    return jsonify({"code":200,"msg":"success","data":data})

# 全量数据接口 - zhaopin_jobs表(智联招聘)，需登录后访问
@app.route('/api/zhaopin/jobData')
@token_required
def get_zhaopin_job():
    conn, cursor = get_db_conn()
    sql = "SELECT * FROM zhaopin_jobs;"
    cursor.execute(sql)
    data = cursor.fetchall()
    conn.close()
    return jsonify({"code":200,"msg":"success","data":data})

# 合并51job和zhaopin两张表的数据，需登录后访问
@app.route('/api/jobData/merged')
@token_required
def get_merged_job():
    conn, cursor = get_db_conn()
    
    sql1 = "SELECT *, '51job' as data_source FROM jobs;"
    cursor.execute(sql1)
    jobs_data = cursor.fetchall()
    
    sql2 = "SELECT *, 'zhaopin' as data_source FROM zhaopin_jobs;"
    cursor.execute(sql2)
    zhaopin_data = cursor.fetchall()
    
    conn.close()
    
    merged_data = jobs_data + zhaopin_data
    
    return jsonify({
        "code":200,
        "msg":"success",
        "data":merged_data,
        "qcw_count":len(jobs_data),
        "zhaopin_count":len(zhaopin_data),
        "total_count":len(merged_data)
    })

# 数据统计接口 - 支持指定数据源，需登录后访问
@app.route('/api/jobData/stats')
@token_required
def get_job_stats():
    source = request.args.get('source', 'all')
    conn, cursor = get_db_conn()
    
    stats = {}
    
    if source == 'all' or source == '51job':
        cursor.execute("SELECT COUNT(*) as count FROM jobs")
        stats['51job'] = cursor.fetchone()['count']
    
    if source == 'all' or source == 'zhaopin':
        cursor.execute("SELECT COUNT(*) as count FROM zhaopin_jobs")
        stats['zhaopin'] = cursor.fetchone()['count']
    
    if source == 'all':
        stats['total'] = stats.get('51job', 0) + stats.get('zhaopin', 0)
    
    conn.close()
    return jsonify({"code":200, "data":stats})

# 分页查询接口 - zhaopin_jobs表，需登录后访问
@app.route('/api/zhaopin/job/page')
@token_required
def zhaopin_job_page():
    return job_page_by_table('zhaopin_jobs')

# 通用分页查询函数
def job_page_by_table(table_name):
    page = int(request.args.get('page',1))
    size = int(request.args.get('size',200))
    offset = (page-1)*size
    conn,cursor = get_db_conn()
    sql = f"SELECT * FROM {table_name} LIMIT %s,%s;"
    cursor.execute(sql,(offset,size))
    records = cursor.fetchall()
    cursor.execute(f"SELECT COUNT(*) total FROM {table_name};")
    total = cursor.fetchone()['total']
    conn.close()
    return jsonify({
        "code":200,
        "data":records,
        "total":total,
        "page":page,
        "size":size,
        "table":table_name
    })

# 新增岗位，需管理员权限
@app.route('/api/job/add', methods=["POST"])
@role_required(['admin'])
def add_job():
    job = request.get_json()
    if not job:
        return jsonify({"code": 400, "msg": "请求数据为空"}), 400
    conn, cursor = get_db_conn()
    sql = """
    INSERT INTO jobs(job_id,major,education,experience,salary,company_name,company_nature,company_scale,work_city,job_name,update_time)
    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """
    try:
        # 校验必填字段，防止数据不完整
        required = ['job_id','major','education','experience','salary','company_name','company_nature','company_scale','work_city','job_name','update_time']
        for field in required:
            if field not in job:
                conn.close()
                return jsonify({"code": 400, "msg": f"缺少必填字段: {field}"}), 400
        cursor.execute(sql, (
            job["job_id"],job["major"],job["education"],job["experience"],job["salary"],
            job["company_name"],job["company_nature"],job["company_scale"],job["work_city"],job["job_name"],job["update_time"]
        ))
        conn.commit()
        # 记录审计日志
        audit_log(request.current_user['user_id'], 'add_job', f"新增岗位: {job.get('job_name', '')} (ID: {job.get('job_id', '')})", request.remote_addr)
        res = {"code":200,"msg":"新增成功"}
    except Exception:
        conn.rollback()
        # 不暴露内部错误细节，仅记录日志
        res = {"code":500,"msg":"新增失败，请稍后重试"}
    conn.close()
    return jsonify(res)


# 修改岗位，需管理员权限
@app.route('/api/job/update', methods=["PUT"])
@role_required(['admin'])
def update_job():
    job = request.get_json()
    if not job:
        return jsonify({"code": 400, "msg": "请求数据为空"}), 400
    conn, cursor = get_db_conn()
    sql = """
    UPDATE jobs SET major=%s,education=%s,experience=%s,salary=%s,company_name=%s,
    company_nature=%s,company_scale=%s,work_city=%s,job_name=%s,update_time=%s WHERE job_id=%s
    """
    try:
        cursor.execute(sql, (
            job["major"],job["education"],job["experience"],job["salary"],job["company_name"],
            job["company_nature"],job["company_scale"],job["work_city"],job["job_name"],job["update_time"],job["job_id"]
        ))
        conn.commit()
        # 记录审计日志
        audit_log(request.current_user['user_id'], 'update_job', f"修改岗位 ID: {job.get('job_id', '')}", request.remote_addr)
        res = {"code":200,"msg":"修改成功"}
    except Exception:
        conn.rollback()
        res = {"code":500,"msg":"修改失败，请稍后重试"}
    conn.close()
    return jsonify(res)


# 删除岗位，需管理员权限
@app.route('/api/job/del/<int:jid>', methods=["DELETE"])
@role_required(['admin'])
def del_job(jid):
    conn, cursor = get_db_conn()
    sql = "DELETE FROM jobs WHERE job_id=%s"
    try:
        cursor.execute(sql, (jid,))
        conn.commit()
        # 记录审计日志
        audit_log(request.current_user['user_id'], 'delete_job', f"删除岗位 ID: {jid}", request.remote_addr)
        res = {"code":200,"msg":"删除成功"}
    except Exception:
        conn.rollback()
        res = {"code":500,"msg":"删除失败，请稍后重试"}
    conn.close()
    return jsonify(res)


# =============================================
# 管理员API：爬虫管理（前程无忧 + 智联招聘）
# 维护两个爬虫的运行状态，支持独立启动/停止
# 通过 subprocess.Popen 启动真实的爬虫脚本
# =============================================

# 爬虫脚本配置字典
# 每个爬虫包含：脚本路径(script)、工作目录(workdir)、前端展示名称(display_name)
# 工作目录为相对于 backend 的上级目录，爬虫脚本位于独立的 pcwjj 项目中
CRAWLER_CONFIG = {
    '51job': {
        'script': 'pcwjj\\qcwypc\\yingjie_spider\\api_crawler.py',
        'workdir': os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'pcwjj', 'qcwypc', 'yingjie_spider'),
        'display_name': '前程无忧'
    },
    'zhaopin': {
        'script': 'pcwjj\\zlzppc\\web_crawler.py',
        'workdir': os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'pcwjj', 'zlzppc'),
        'display_name': '智联招聘'
    }
}

# 爬虫运行状态（内存中维护，服务重启后丢失）
# 每个爬虫包含：
#   status:       当前状态（running/stopped/error）
#   started_at:   本次启动时间
#   last_run:     上次运行结束时间
#   error:        错误信息（仅在error状态时有值）
#   total_fetched: 已抓取岗位数（预留字段）
#   _process:      subprocess.Popen对象（仅供内部使用，不对外暴露）
crawler_status = {
    '51job': {
        'status': 'stopped',        # running / stopped / error
        'started_at': None,
        'last_run': None,
        'error': None,
        'total_fetched': 0,
        '_process': None            # subprocess.Popen 对象（不返回给前端）
    },
    'zhaopin': {
        'status': 'stopped',
        'started_at': None,
        'last_run': None,
        'error': None,
        'total_fetched': 0,
        '_process': None
    }
}

def _strip_process_info(status_dict):
    """
    移除进程内部对象，生成安全的JSON返回数据
    过滤掉 _process（subprocess.Popen对象，不可序列化）字段
    避免将进程句柄暴露给前端
    """
    result = {}
    for key, value in status_dict.items():
        if key != '_process':
            result[key] = value
    return result


def _check_process_alive(source):
    """
    检查爬虫子进程是否还存活，自动更新状态
    通过 proc.poll() 检查进程退出码：
      - None → 进程仍在运行，不修改状态
      - 0    → 进程正常退出，标记为 stopped
      - 非0  → 进程异常退出，标记为 error 并记录错误信息
    同时清理 _process 引用，避免僵尸进程
    """
    info = crawler_status[source]
    proc = info.get('_process')
    if proc is None:
        return

    # poll() 返回 None 表示仍在运行，非 None 表示已退出
    retcode = proc.poll()
    if retcode is not None:
        # 进程已结束，清理引用
        info['_process'] = None
        info['status'] = 'stopped' if retcode == 0 else 'error'
        info['last_run'] = info['started_at']  # 记录实际运行时间
        info['started_at'] = None
        if retcode != 0:
            info['error'] = f'进程异常退出，返回码: {retcode}'
        else:
            info['error'] = None


def _terminate_process(source):
    """
    终止指定爬虫的子进程
    终止策略（两阶段）：
      1. 优雅终止：Windows → terminate() / Unix → SIGTERM，等待5秒
      2. 强制杀死：超时后调用 kill() 强制结束，等待3秒
      3. 兜底方案：异常时再次尝试 kill()
    确保进程最终被终止，避免僵尸进程残留
    """
    info = crawler_status[source]
    proc = info.get('_process')
    if proc is None:
        return False

    try:
        # 第一阶段：根据操作系统选择合适的优雅终止方式
        if os.name == 'nt':  # Windows系统
            proc.terminate()
        else:  # Linux/Mac系统
            proc.send_signal(signal.SIGTERM)

        # 等待5秒让进程自行退出并清理资源
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            # 第二阶段：超时后强制杀死进程
            proc.kill()
            proc.wait(timeout=3)
    except Exception as e:
        # 兜底：异常情况下强制杀死进程
        try:
            proc.kill()
        except:
            pass  # 进程可能已经退出

    info['_process'] = None
    return True


@app.route('/api/admin/crawler/<source>/start', methods=['POST'])
@role_required(['admin'])
def start_crawler(source):
    """
    启动指定爬虫（51job 或 zhaopin）
    流程：校验参数 → 检查状态 → 验证脚本存在 → 启动子进程
    返回启动结果和子进程PID
    """
    # 校验爬虫来源（仅支持51job和zhaopin）
    if source not in crawler_status:
        return jsonify({"code": 400, "msg": "无效的爬虫来源，仅支持 51job/zhaopin"}), 400

    # 先刷新进程状态（防止进程已自行退出但状态未更新）
    _check_process_alive(source)

    # 检查是否已在运行中（防止重复启动）
    if crawler_status[source]['status'] == 'running':
        return jsonify({"code": 400, "msg": "爬虫正在运行中"}), 400

    # 检查爬虫脚本文件是否存在
    config = CRAWLER_CONFIG[source]
    script_path = os.path.join(config['workdir'], os.path.basename(config['script']))
    if not os.path.exists(script_path):
        return jsonify({"code": 500, "msg": f"爬虫脚本 {config['display_name']} 不存在，请联系管理员"}), 500

    try:
        # 启动真实爬虫子进程
        # CREATE_NEW_PROCESS_GROUP（Windows）使子进程拥有独立的进程组，方便终止时不影响主进程
        proc = subprocess.Popen(
            ['python', os.path.basename(config['script'])],
            cwd=config['workdir'],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
        )

        # 更新内存中的状态信息
        crawler_status[source]['status'] = 'running'
        crawler_status[source]['started_at'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        crawler_status[source]['error'] = None
        crawler_status[source]['_process'] = proc

        # 记录审计日志
        audit_log(request.current_user['user_id'], 'start_crawler', f"启动{config['display_name']}爬虫 (PID: {proc.pid})", request.remote_addr)

        return jsonify({"code": 200, "msg": f"{config['display_name']}爬虫启动成功 (PID: {proc.pid})"})

    except Exception as e:
        crawler_status[source]['status'] = 'error'
        # 内部记录错误详情用于调试，但不返回给客户端
        crawler_status[source]['error'] = str(e)
        return jsonify({"code": 500, "msg": "启动爬虫失败，请稍后重试或联系管理员"}), 500


@app.route('/api/admin/crawler/<source>/stop', methods=['POST'])
@role_required(['admin'])
def stop_crawler(source):
    """停止指定爬虫"""
    if source not in crawler_status:
        return jsonify({"code": 400, "msg": "无效的爬虫来源"}), 400

    _check_process_alive(source)

    if crawler_status[source]['status'] != 'running':
        return jsonify({"code": 400, "msg": "爬虫未在运行"}), 400

    config = CRAWLER_CONFIG[source]
    _terminate_process(source)

    crawler_status[source]['status'] = 'stopped'
    crawler_status[source]['last_run'] = crawler_status[source]['started_at']
    crawler_status[source]['started_at'] = None

    # 记录审计日志
    audit_log(request.current_user['user_id'], 'stop_crawler', f"停止{config['display_name']}爬虫", request.remote_addr)

    return jsonify({"code": 200, "msg": f"{config['display_name']}爬虫已停止"})


@app.route('/api/admin/crawler/<source>/status', methods=['GET'])
@role_required(['admin'])
def crawler_source_status(source):
    """查询指定爬虫的状态"""
    if source not in crawler_status:
        return jsonify({"code": 400, "msg": "无效的爬虫来源"}), 400

    _check_process_alive(source)

    return jsonify({
        "code": 200,
        "data": _strip_process_info(crawler_status[source])
    })


@app.route('/api/admin/crawler/status', methods=['GET'])
@role_required(['admin'])
def crawler_all_status():
    """查询所有爬虫的状态"""
    for source in crawler_status:
        _check_process_alive(source)

    result = {}
    for source, info in crawler_status.items():
        result[source] = _strip_process_info(info)

    return jsonify({
        "code": 200,
        "data": result
    })


# =============================================
# 管理员API：数据库管理（查看表、增删改记录）
# 安全机制：
#   1. 表名白名单验证（SHOW TABLES 动态获取）
#   2. 删除接口只允许操作岗位相关表（JOB_TABLES 白名单）
#   3. 所有参数使用参数化查询，防止SQL注入
# =============================================
@app.route('/api/admin/database/tables', methods=['GET'])
@role_required(['admin'])
def get_tables():
    """获取数据库中所有表的列表"""
    conn, cursor = get_db_conn()
    cursor.execute("SHOW TABLES")
    tables = [row['Tables_in_' + Config.DB_NAME] for row in cursor.fetchall()]
    conn.close()
    return jsonify({"code": 200, "data": tables})


@app.route('/api/admin/database/table/<table_name>', methods=['GET'])
@role_required(['admin'])
def get_table_data(table_name):
    """
    获取指定表的分页数据、总记录数和字段列表
    安全措施：先通过 SHOW TABLES 获取白名单，验证 table_name 的合法性
    有效防止 SQL 注入攻击——任何不在数据库中的表名都会被拒绝
    """
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 100))
    offset = (page - 1) * size

    conn, cursor = get_db_conn()

    # 验证表名合法性（白名单方式防御 SQL 注入）
    # 动态获取数据库中真实存在的表名，拒绝所有伪造的表名
    cursor.execute("SHOW TABLES")
    tables = [row['Tables_in_' + Config.DB_NAME] for row in cursor.fetchall()]
    if table_name not in tables:
        conn.close()
        return jsonify({"code": 400, "msg": "无效的表名"}), 400
    
    # 查询分页数据
    sql = f"SELECT * FROM {table_name} LIMIT %s, %s"
    cursor.execute(sql, (offset, size))
    records = cursor.fetchall()
    
    # 查询总数
    cursor.execute(f"SELECT COUNT(*) as total FROM {table_name}")
    total = cursor.fetchone()['total']
    
    # 获取表结构（字段列表）
    cursor.execute(f"DESCRIBE {table_name}")
    columns = [row['Field'] for row in cursor.fetchall()]
    
    conn.close()
    
    return jsonify({
        "code": 200,
        "data": {
            "records": records,
            "total": total,
            "columns": columns,
            "page": page,
            "size": size
        }
    })


@app.route('/api/admin/database/record', methods=['POST'])
@role_required(['admin'])
def add_record():
    """
    向指定表添加一条新记录（仅限管理员操作）
    请求体需包含 table（目标表名）和 record（字段键值对）
    表名经白名单验证，列名经DESCRIBE获取的真实字段白名单验证，双重防SQL注入
    所有值通过参数化占位符 %s 传入
    """
    data = request.get_json()

    if 'table' not in data or 'record' not in data:
        return jsonify({"code": 400, "msg": "缺少表名或记录数据"}), 400

    table_name = data['table']
    record = data['record']

    if not isinstance(record, dict) or len(record) == 0:
        return jsonify({"code": 400, "msg": "记录数据不能为空"}), 400

    conn, cursor = get_db_conn()

    # 验证表名白名单（第一道防线：防止SQL注入）
    cursor.execute("SHOW TABLES")
    tables = [row['Tables_in_' + Config.DB_NAME] for row in cursor.fetchall()]
    if table_name not in tables:
        conn.close()
        return jsonify({"code": 400, "msg": "无效的表名"}), 400

    # 获取表结构（列名白名单），防止列名SQL注入
    cursor.execute(f"DESCRIBE {table_name}")
    valid_columns = [row['Field'] for row in cursor.fetchall()]

    # 过滤记录，只保留白名单内的列（第二道防线：列名校验）
    record = {k: v for k, v in record.items() if k in valid_columns}
    if len(record) == 0:
        conn.close()
        return jsonify({"code": 400, "msg": "没有有效的字段可插入"}), 400

    # 从经过白名单过滤后的record字典构建列名列表和占位符列表
    columns = ', '.join(record.keys())
    placeholders = ', '.join(['%s'] * len(record))

    sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"

    try:
        cursor.execute(sql, list(record.values()))
        conn.commit()
        record_id = cursor.lastrowid
        conn.close()
        # 记录审计日志
        audit_log(request.current_user['user_id'], 'db_add_record',
                  f"向表 {table_name} 添加记录 ID={record_id}", request.remote_addr)
        return jsonify({"code": 200, "msg": "记录添加成功", "data": {"id": record_id}})
    except Exception:
        conn.rollback()
        conn.close()
        return jsonify({"code": 500, "msg": "添加失败，请检查数据格式后重试"}), 500


@app.route('/api/admin/database/record', methods=['PUT'])
@role_required(['admin'])
def update_record():
    """
    更新指定表中的一条记录（仅限管理员操作）
    请求体需包含 table（目标表名）、record（要更新的字段键值对）、id（记录主键）
    所有数据值通过参数化占位符传入，表名经白名单验证，列名经DESCRIBE白名单验证
    """
    data = request.get_json()

    if 'table' not in data or 'record' not in data or 'id' not in data:
        return jsonify({"code": 400, "msg": "缺少表名、记录数据或ID"}), 400

    table_name = data['table']
    record = data['record']
    record_id = data['id']

    if not isinstance(record, dict) or len(record) == 0:
        return jsonify({"code": 400, "msg": "更新数据不能为空"}), 400

    conn, cursor = get_db_conn()

    # 验证表名白名单（第一道防线：防止SQL注入）
    cursor.execute("SHOW TABLES")
    tables = [row['Tables_in_' + Config.DB_NAME] for row in cursor.fetchall()]
    if table_name not in tables:
        conn.close()
        return jsonify({"code": 400, "msg": "无效的表名"}), 400

    # 获取表结构（列名白名单），防止列名SQL注入
    cursor.execute(f"DESCRIBE {table_name}")
    valid_columns = [row['Field'] for row in cursor.fetchall()]

    # 过滤记录，只保留白名单内的列（第二道防线：列名校验）
    record = {k: v for k, v in record.items() if k in valid_columns}
    if len(record) == 0:
        conn.close()
        return jsonify({"code": 400, "msg": "没有有效的字段可更新"}), 400

    # 动态拼接 UPDATE 语句（SET子句从经过白名单过滤后的record字典生成）
    set_clause = ', '.join([f"{k} = %s" for k in record.keys()])
    sql = f"UPDATE {table_name} SET {set_clause} WHERE id = %s"

    try:
        cursor.execute(sql, list(record.values()) + [record_id])
        conn.commit()
        conn.close()
        # 记录审计日志
        audit_log(request.current_user['user_id'], 'db_update_record',
                  f"更新表 {table_name} 中 ID={record_id} 的记录", request.remote_addr)
        return jsonify({"code": 200, "msg": "记录更新成功"})
    except Exception:
        conn.rollback()
        conn.close()
        return jsonify({"code": 500, "msg": "更新失败，请检查数据格式后重试"}), 500


@app.route('/api/admin/database/record/<int:record_id>', methods=['DELETE'])
@role_required(['admin'])
def delete_record(record_id):
    """
    删除指定表中的一条记录
    安全限制：只允许操作岗位相关表（jobs/zhaopin_jobs/jobs_core/jobs_analysis/jobs_company）
    """
    table_name = request.args.get('table')
    
    if not table_name:
        return jsonify({"code": 400, "msg": "缺少表名参数"}), 400
    
    # 只允许删除岗位相关表的数据（白名单限制）
    JOB_TABLES = ['jobs', 'zhaopin_jobs', 'jobs_core', 'jobs_analysis', 'jobs_company']
    if table_name not in JOB_TABLES:
        return jsonify({"code": 403, "msg": "只能删除岗位相关表的数据"}), 403
    
    conn, cursor = get_db_conn()
    
    # 验证表名（防止SQL注入）
    cursor.execute("SHOW TABLES")
    tables = [row['Tables_in_' + Config.DB_NAME] for row in cursor.fetchall()]
    if table_name not in tables:
        conn.close()
        return jsonify({"code": 400, "msg": "无效的表名"}), 400
    
    # 执行删除（按 id 删除单条记录）
    sql = f"DELETE FROM {table_name} WHERE id = %s"

    try:
        cursor.execute(sql, (record_id,))
        conn.commit()
        conn.close()
        # 记录审计日志
        audit_log(request.current_user['user_id'], 'db_delete_record',
                  f"从表 {table_name} 删除 ID={record_id} 的记录", request.remote_addr)
        return jsonify({"code": 200, "msg": "记录删除成功"})
    except Exception:
        conn.rollback()
        conn.close()
        return jsonify({"code": 500, "msg": "删除失败，请稍后重试"}), 500


# 最近入库数据接口（爬虫管理页面展示用）
@app.route('/api/admin/recent-jobs', methods=['GET'])
@role_required(['admin'])
def get_recent_jobs():
    """获取最近入库的岗位数据，支持按数据源筛选"""
    limit = int(request.args.get('limit', 10))
    source = request.args.get('source', 'all')
    conn, cursor = get_db_conn()

    results = []

    if source in ('all', '51job'):
        cursor.execute("""
            SELECT id, jobid as source_id, job_url, position_name, company_name, salary, city, created_at, '51job' as data_source
            FROM jobs ORDER BY created_at DESC LIMIT %s
        """, (limit,))
        results.extend(cursor.fetchall())

    if source in ('all', 'zhaopin'):
        cursor.execute("""
            SELECT id, position_id as source_id, job_url, position_name, company_name, salary, city, created_at, 'zhaopin' as data_source
            FROM zhaopin_jobs ORDER BY created_at DESC LIMIT %s
        """, (limit,))
        results.extend(cursor.fetchall())

    conn.close()

    results.sort(key=lambda x: x.get('created_at') or '', reverse=True)

    return jsonify({"code": 200, "data": results[:limit]})


# 用户登出接口 —— 将当前JWT令牌加入黑名单，使其立即失效
@app.route('/api/auth/logout', methods=['POST'])
@token_required
def logout():
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if token:
        add_to_blacklist(token)
    return jsonify({"code": 200, "msg": "已登出"})


# SPA catch-all 路由：所有非 /api/ 开头的路径返回 index.html
# 支持 React Router 的前端路由（如 /login, /admin 等）
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    if path.startswith('api/'):
        return jsonify({"code": 404, "msg": "接口不存在"}), 404
    return render_template('index.html')


if __name__ == '__main__':
    # ==================== 启动前安全校验 ====================
    # 验证所有必要环境变量是否已正确设置，防止以不安全状态启动
    config_errors = Config.validate()
    if config_errors:
        print("\n" + "=" * 60)
        print("配置错误 —— 应用无法启动")
        print("=" * 60)
        for err in config_errors:
            print(f"  [ERROR] {err}")
        print("=" * 60)
        print("请设置必要的环境变量后重新启动，参考 .env.example")
        print("示例：")
        print("  set DB_PASSWORD=你的数据库密码")
        print("  set JWT_SECRET=一个至少32位的随机字符串")
        print("=" * 60 + "\n")
        import sys
        sys.exit(1)
    # 启动前先初始化数据库表结构
    init_database()
    app.run(debug=False)
