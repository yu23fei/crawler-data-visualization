"""Flask 应用入口

注册蓝图、配置跨域、初始化数据库，并包含遗留 API 和管理员数据库管理接口。
"""

import datetime
import os
import signal
import subprocess

import pymysql
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS

from backend.api.v1.admin import admin_bp
from backend.api.v1.auth import auth_bp
from backend.api.v1.data import data_bp
from backend.core.config import Config
from backend.core.init_db import init_database
from backend.middleware.auth import token_required, role_required
from backend.utils.security import add_to_blacklist, audit_log

REACT_BUILD_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)), '..', 'frontend', 'build'
)

app = Flask(__name__,
    template_folder=REACT_BUILD_DIR,
    static_folder=os.path.join(REACT_BUILD_DIR, 'static'),
    static_url_path='/static'
)
app.secret_key = Config.SECRET_KEY
CORS(app, supports_credentials=True)


@app.after_request
def add_security_headers(response):
    """安全HTTP响应头中间件——每次响应后自动添加安全头"""
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; img-src 'self' data:"
    )
    response.headers['X-Download-Options'] = 'noopen'
    return response


app.register_blueprint(auth_bp)
app.register_blueprint(admin_bp)
app.register_blueprint(data_bp)

DB_CONFIG = {
    "host": Config.DB_HOST,
    "port": Config.DB_PORT,
    "user": Config.DB_USER,
    "password": Config.DB_PASSWORD,
    "database": Config.DB_NAME,
    "charset": "utf8mb4"
}


def _get_db_conn():
    """获取数据库连接和游标"""
    conn = pymysql.connect(**DB_CONFIG)
    cursor = conn.cursor(cursor=pymysql.cursors.DictCursor)
    return conn, cursor


@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/jobData')
@token_required
def get_all_job():
    conn, cursor = _get_db_conn()
    cursor.execute("SELECT * FROM jobs_51job")
    data = cursor.fetchall()
    conn.close()
    return jsonify({"code": 200, "msg": "success", "data": data})


@app.route('/api/zhaopin/jobData')
@token_required
def get_zhaopin_job():
    conn, cursor = _get_db_conn()
    cursor.execute("SELECT * FROM zhaopin_jobs")
    data = cursor.fetchall()
    conn.close()
    return jsonify({"code": 200, "msg": "success", "data": data})


@app.route('/api/jobData/merged')
@token_required
def get_merged_job():
    conn, cursor = _get_db_conn()
    cursor.execute("SELECT *, '51job' as data_source FROM jobs_51job")
    jobs_data = cursor.fetchall()
    cursor.execute("SELECT *, 'zhaopin' as data_source FROM zhaopin_jobs")
    zhaopin_data = cursor.fetchall()
    conn.close()
    merged_data = jobs_data + zhaopin_data
    return jsonify({
        "code": 200, "msg": "success", "data": merged_data,
        "qcw_count": len(jobs_data),
        "zhaopin_count": len(zhaopin_data),
        "total_count": len(merged_data)
    })


@app.route('/api/jobData/stats')
@token_required
def get_job_stats():
    source = request.args.get('source', 'all')
    conn, cursor = _get_db_conn()
    stats = {}
    if source in ('all', '51job'):
        cursor.execute("SELECT COUNT(*) as count FROM jobs_51job")
        stats['51job'] = cursor.fetchone()['count']
    if source in ('all', 'zhaopin'):
        cursor.execute("SELECT COUNT(*) as count FROM zhaopin_jobs")
        stats['zhaopin'] = cursor.fetchone()['count']
    if source == 'all':
        stats['total'] = stats.get('51job', 0) + stats.get('zhaopin', 0)
    conn.close()
    return jsonify({"code": 200, "data": stats})


@app.route('/api/zhaopin/job/page')
@token_required
def zhaopin_job_page():
    return _job_page_by_table('zhaopin_jobs')

@app.route('/api/51job/job/page')
@token_required
def job_51job_page():
    return _job_page_by_table('jobs_51job')


def _job_page_by_table(table_name):
    """通用分页查询函数"""
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 200))
    offset = (page - 1) * size
    conn, cursor = _get_db_conn()
    cursor.execute(f"SELECT * FROM {table_name} LIMIT %s, %s", (offset, size))
    records = cursor.fetchall()
    cursor.execute(f"SELECT COUNT(*) total FROM {table_name}")
    total = cursor.fetchone()['total']
    conn.close()
    return jsonify({
        "code": 200, "data": records, "total": total,
        "page": page, "size": size, "table": table_name
    })


@app.route('/api/job/add', methods=["POST"])
@role_required(['admin'])
def add_job():
    job = request.get_json()
    if not job:
        return jsonify({"code": 400, "msg": "请求数据为空"}), 400
    conn, cursor = _get_db_conn()
    sql = """
        INSERT INTO jobs(job_id,major,education,experience,salary,company_name,
        company_nature,company_scale,work_city,job_name,update_time)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    """
    try:
        required = [
            'job_id', 'major', 'education', 'experience', 'salary',
            'company_name', 'company_nature', 'company_scale',
            'work_city', 'job_name', 'update_time'
        ]
        for field in required:
            if field not in job:
                conn.close()
                return jsonify({"code": 400, "msg": f"缺少必填字段: {field}"}), 400
        cursor.execute(sql, (
            job["job_id"], job["major"], job["education"], job["experience"],
            job["salary"], job["company_name"], job["company_nature"],
            job["company_scale"], job["work_city"], job["job_name"],
            job["update_time"]
        ))
        conn.commit()
        audit_log(
            request.current_user['user_id'], 'add_job',
            f"新增岗位: {job.get('job_name', '')} (ID: {job.get('job_id', '')})",
            request.remote_addr
        )
        res = {"code": 200, "msg": "新增成功"}
    except Exception:
        conn.rollback()
        res = {"code": 500, "msg": "新增失败，请稍后重试"}
    conn.close()
    return jsonify(res)


@app.route('/api/job/update', methods=["PUT"])
@role_required(['admin'])
def update_job():
    job = request.get_json()
    if not job:
        return jsonify({"code": 400, "msg": "请求数据为空"}), 400
    conn, cursor = _get_db_conn()
    sql = """
        UPDATE jobs SET major=%s,education=%s,experience=%s,salary=%s,
        company_name=%s,company_nature=%s,company_scale=%s,work_city=%s,
        job_name=%s,update_time=%s WHERE job_id=%s
    """
    try:
        cursor.execute(sql, (
            job["major"], job["education"], job["experience"], job["salary"],
            job["company_name"], job["company_nature"], job["company_scale"],
            job["work_city"], job["job_name"], job["update_time"], job["job_id"]
        ))
        conn.commit()
        audit_log(
            request.current_user['user_id'], 'update_job',
            f"修改岗位 ID: {job.get('job_id', '')}", request.remote_addr
        )
        res = {"code": 200, "msg": "修改成功"}
    except Exception:
        conn.rollback()
        res = {"code": 500, "msg": "修改失败，请稍后重试"}
    conn.close()
    return jsonify(res)


@app.route('/api/job/del/<int:jid>', methods=["DELETE"])
@role_required(['admin'])
def del_job(jid):
    conn, cursor = _get_db_conn()
    sql = "DELETE FROM jobs WHERE job_id=%s"
    try:
        cursor.execute(sql, (jid,))
        conn.commit()
        audit_log(
            request.current_user['user_id'], 'delete_job',
            f"删除岗位 ID: {jid}", request.remote_addr
        )
        res = {"code": 200, "msg": "删除成功"}
    except Exception:
        conn.rollback()
        res = {"code": 500, "msg": "删除失败，请稍后重试"}
    conn.close()
    return jsonify(res)


CRAWLER_CONFIG = {
    '51job': {
        'script': 'crawler_pw.py',
        'workdir': os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '..', 'pcwjj', 'qcwypc', 'yingjie_spider'
        ),
        'display_name': '前程无忧'
    },
    'zhaopin': {
        'script': 'crawler_pw.py',
        'workdir': os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '..', 'pcwjj', 'zlzppc'
        ),
        'display_name': '智联招聘'
    }
}

crawler_status = {
    '51job': {
        'status': 'stopped', 'started_at': None, 'last_run': None,
        'error': None, 'total_fetched': 0, '_process': None
    },
    'zhaopin': {
        'status': 'stopped', 'started_at': None, 'last_run': None,
        'error': None, 'total_fetched': 0, '_process': None
    }
}


def _strip_process_info(status_dict):
    """移除进程内部对象，生成安全的JSON返回数据"""
    return {k: v for k, v in status_dict.items() if k != '_process'}


def _check_process_alive(source):
    """检查爬虫子进程是否还存活，自动更新状态"""
    info = crawler_status[source]
    proc = info.get('_process')
    if proc is None:
        return
    retcode = proc.poll()
    if retcode is not None:
        info['_process'] = None
        info['status'] = 'stopped' if retcode == 0 else 'error'
        info['last_run'] = info['started_at']
        info['started_at'] = None
        if retcode != 0:
            info['error'] = f'进程异常退出，返回码: {retcode}'
        else:
            info['error'] = None


def _terminate_process(source):
    """终止指定爬虫的子进程（两阶段终止策略）"""
    info = crawler_status[source]
    proc = info.get('_process')
    if proc is None:
        return False
    try:
        if os.name == 'nt':
            proc.terminate()
        else:
            proc.send_signal(signal.SIGTERM)
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=3)
    except Exception:
        try:
            proc.kill()
        except Exception:
            pass
    info['_process'] = None
    return True


@app.route('/api/admin/crawler/<source>/start', methods=['POST'])
@role_required(['admin'])
def start_crawler(source):
    """启动指定爬虫（51job 或 zhaopin）"""
    if source not in crawler_status:
        return jsonify({"code": 400, "msg": "无效的爬虫来源，仅支持 51job/zhaopin"}), 400

    _check_process_alive(source)

    if crawler_status[source]['status'] == 'running':
        return jsonify({"code": 400, "msg": "爬虫正在运行中"}), 400

    config = CRAWLER_CONFIG[source]
    script_path = os.path.join(config['workdir'], os.path.basename(config['script']))
    if not os.path.exists(script_path):
        return jsonify({
            "code": 500,
            "msg": f"爬虫脚本 {config['display_name']} 不存在，请联系管理员"
        }), 500

    log_dir = os.path.join(config['workdir'], 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f'{source}_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    stdout_f = open(log_file, 'w', encoding='utf-8')
    stderr_f = open(log_file, 'w', encoding='utf-8')

    try:
        proc = subprocess.Popen(
            ['python', os.path.basename(config['script'])],
            cwd=config['workdir'],
            stdout=stdout_f,
            stderr=subprocess.STDOUT,
            shell=False,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if os.name == 'nt' else 0
        )
        stdout_f.close()

        crawler_status[source]['status'] = 'running'
        crawler_status[source]['started_at'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        crawler_status[source]['error'] = None
        crawler_status[source]['_process'] = proc

        audit_log(
            request.current_user['user_id'], 'start_crawler',
            f"启动{config['display_name']}爬虫 (PID: {proc.pid})",
            request.remote_addr
        )

        return jsonify({
            "code": 200,
            "msg": f"{config['display_name']}爬虫启动成功 (PID: {proc.pid})"
        })
    except Exception as e:
        crawler_status[source]['status'] = 'error'
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

    audit_log(
        request.current_user['user_id'], 'stop_crawler',
        f"停止{config['display_name']}爬虫", request.remote_addr
    )

    return jsonify({"code": 200, "msg": f"{config['display_name']}爬虫已停止"})


@app.route('/api/admin/crawler/<source>/status', methods=['GET'])
@role_required(['admin'])
def crawler_source_status(source):
    """查询指定爬虫的状态"""
    if source not in crawler_status:
        return jsonify({"code": 400, "msg": "无效的爬虫来源"}), 400
    _check_process_alive(source)
    return jsonify({"code": 200, "data": _strip_process_info(crawler_status[source])})


@app.route('/api/admin/crawler/status', methods=['GET'])
@role_required(['admin'])
def crawler_all_status():
    """查询所有爬虫的状态"""
    for source in crawler_status:
        _check_process_alive(source)
    result = {source: _strip_process_info(info) for source, info in crawler_status.items()}
    return jsonify({"code": 200, "data": result})


JOB_TABLES = ['jobs', 'jobs_51job', 'zhaopin_jobs', 'jobs_core', 'jobs_analysis', 'jobs_company']


@app.route('/api/admin/database/tables', methods=['GET'])
@role_required(['admin'])
def get_tables():
    """获取数据库中所有表的列表"""
    conn, cursor = _get_db_conn()
    cursor.execute("SHOW TABLES")
    tables = [row['Tables_in_' + Config.DB_NAME] for row in cursor.fetchall()]
    conn.close()
    return jsonify({"code": 200, "data": tables})


def _validate_table_name(table_name, cursor):
    """验证表名合法性（白名单方式防御 SQL 注入）"""
    cursor.execute("SHOW TABLES")
    tables = [row['Tables_in_' + Config.DB_NAME] for row in cursor.fetchall()]
    return table_name in tables


@app.route('/api/admin/database/table/<table_name>', methods=['GET'])
@role_required(['admin'])
def get_table_data(table_name):
    """获取指定表的分页数据、总记录数和字段列表"""
    page = int(request.args.get('page', 1))
    size = int(request.args.get('size', 100))
    offset = (page - 1) * size

    conn, cursor = _get_db_conn()

    if not _validate_table_name(table_name, cursor):
        conn.close()
        return jsonify({"code": 400, "msg": "无效的表名"}), 400

    cursor.execute(f"SELECT * FROM {table_name} LIMIT %s, %s", (offset, size))
    records = cursor.fetchall()

    cursor.execute(f"SELECT COUNT(*) as total FROM {table_name}")
    total = cursor.fetchone()['total']

    cursor.execute(f"DESCRIBE {table_name}")
    columns = [row['Field'] for row in cursor.fetchall()]

    conn.close()

    return jsonify({
        "code": 200, "data": {
            "records": records, "total": total,
            "columns": columns, "page": page, "size": size
        }
    })


@app.route('/api/admin/database/record', methods=['POST'])
@role_required(['admin'])
def add_record():
    """向指定表添加一条新记录（仅限管理员操作）"""
    data = request.get_json()
    if 'table' not in data or 'record' not in data:
        return jsonify({"code": 400, "msg": "缺少表名或记录数据"}), 400

    table_name = data['table']
    record = data['record']

    if not isinstance(record, dict) or len(record) == 0:
        return jsonify({"code": 400, "msg": "记录数据不能为空"}), 400

    conn, cursor = _get_db_conn()

    if not _validate_table_name(table_name, cursor):
        conn.close()
        return jsonify({"code": 400, "msg": "无效的表名"}), 400

    cursor.execute(f"DESCRIBE {table_name}")
    valid_columns = [row['Field'] for row in cursor.fetchall()]
    record = {k: v for k, v in record.items() if k in valid_columns}
    if len(record) == 0:
        conn.close()
        return jsonify({"code": 400, "msg": "没有有效的字段可插入"}), 400

    columns = ', '.join(record.keys())
    placeholders = ', '.join(['%s'] * len(record))
    sql = f"INSERT INTO {table_name} ({columns}) VALUES ({placeholders})"

    try:
        cursor.execute(sql, list(record.values()))
        conn.commit()
        record_id = cursor.lastrowid
        conn.close()
        audit_log(
            request.current_user['user_id'], 'db_add_record',
            f"向表 {table_name} 添加记录 ID={record_id}", request.remote_addr
        )
        return jsonify({"code": 200, "msg": "记录添加成功", "data": {"id": record_id}})
    except Exception:
        conn.rollback()
        conn.close()
        return jsonify({"code": 500, "msg": "添加失败，请检查数据格式后重试"}), 500


@app.route('/api/admin/database/record', methods=['PUT'])
@role_required(['admin'])
def update_record():
    """更新指定表中的一条记录（仅限管理员操作）"""
    data = request.get_json()
    if 'table' not in data or 'record' not in data or 'id' not in data:
        return jsonify({"code": 400, "msg": "缺少表名、记录数据或ID"}), 400

    table_name = data['table']
    record = data['record']
    record_id = data['id']

    if not isinstance(record, dict) or len(record) == 0:
        return jsonify({"code": 400, "msg": "更新数据不能为空"}), 400

    conn, cursor = _get_db_conn()

    if not _validate_table_name(table_name, cursor):
        conn.close()
        return jsonify({"code": 400, "msg": "无效的表名"}), 400

    cursor.execute(f"DESCRIBE {table_name}")
    valid_columns = [row['Field'] for row in cursor.fetchall()]
    record = {k: v for k, v in record.items() if k in valid_columns}
    if len(record) == 0:
        conn.close()
        return jsonify({"code": 400, "msg": "没有有效的字段可更新"}), 400

    set_clause = ', '.join([f"{k} = %s" for k in record.keys()])
    sql = f"UPDATE {table_name} SET {set_clause} WHERE id = %s"

    try:
        cursor.execute(sql, list(record.values()) + [record_id])
        conn.commit()
        conn.close()
        audit_log(
            request.current_user['user_id'], 'db_update_record',
            f"更新表 {table_name} 中 ID={record_id} 的记录", request.remote_addr
        )
        return jsonify({"code": 200, "msg": "记录更新成功"})
    except Exception:
        conn.rollback()
        conn.close()
        return jsonify({"code": 500, "msg": "更新失败，请检查数据格式后重试"}), 500


@app.route('/api/admin/database/record/<int:record_id>', methods=['DELETE'])
@role_required(['admin'])
def delete_record(record_id):
    """删除指定表中的一条记录（仅允许操作岗位相关表）"""
    table_name = request.args.get('table')
    if not table_name:
        return jsonify({"code": 400, "msg": "缺少表名参数"}), 400
    if table_name not in JOB_TABLES:
        return jsonify({"code": 403, "msg": "只能删除岗位相关表的数据"}), 403

    conn, cursor = _get_db_conn()
    if not _validate_table_name(table_name, cursor):
        conn.close()
        return jsonify({"code": 400, "msg": "无效的表名"}), 400

    sql = f"DELETE FROM {table_name} WHERE id = %s"
    try:
        cursor.execute(sql, (record_id,))
        conn.commit()
        conn.close()
        audit_log(
            request.current_user['user_id'], 'db_delete_record',
            f"从表 {table_name} 删除 ID={record_id} 的记录", request.remote_addr
        )
        return jsonify({"code": 200, "msg": "记录删除成功"})
    except Exception:
        conn.rollback()
        conn.close()
        return jsonify({"code": 500, "msg": "删除失败，请稍后重试"}), 500


@app.route('/api/admin/recent-jobs', methods=['GET'])
@role_required(['admin'])
def get_recent_jobs():
    """获取最近入库的岗位数据，支持按数据源筛选"""
    limit = int(request.args.get('limit', 10))
    source = request.args.get('source', 'all')
    conn, cursor = _get_db_conn()

    results = []
    if source in ('all', '51job'):
        cursor.execute("""
            SELECT id, position_id as source_id, '' as job_url, position_name,
                   company_name, salary, city, created_at, '51job' as data_source
            FROM jobs_51job ORDER BY created_at DESC LIMIT %s
        """, (limit,))
        results.extend(cursor.fetchall())
    if source in ('all', 'zhaopin'):
        cursor.execute("""
            SELECT id, position_id as source_id, job_url, position_name,
                   company_name, salary, city, created_at, 'zhaopin' as data_source
            FROM zhaopin_jobs ORDER BY created_at DESC LIMIT %s
        """, (limit,))
        results.extend(cursor.fetchall())

    conn.close()
    results.sort(key=lambda x: x.get('created_at') or '', reverse=True)
    return jsonify({"code": 200, "data": results[:limit]})


@app.route('/api/auth/logout', methods=['POST'])
@token_required
def logout():
    """用户登出接口——将当前JWT令牌加入黑名单"""
    token = request.headers.get('Authorization', '').replace('Bearer ', '')
    if token:
        add_to_blacklist(token)
    return jsonify({"code": 200, "msg": "已登出"})


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
    """SPA catch-all 路由：所有非 /api/ 开头的路径返回 index.html"""
    if path.startswith('api/'):
        return jsonify({"code": 404, "msg": "接口不存在"}), 404
    return render_template('index.html')


if __name__ == '__main__':
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
    init_database()
    app.run(debug=False)
