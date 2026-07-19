// DatabasePage.js - 岗位数据管理页面（管理员专用）
// 仅可浏览和删除岗位相关表（jobs/zhaopin_jobs/jobs_core/jobs_analysis/jobs_company）中的单条记录
import React, { useState, useEffect } from 'react';
import { databaseAPI } from '../../utils/api';

const DatabasePage = () => {
    const [tables, setTables] = useState([]);
    const [selectedTable, setSelectedTable] = useState('');
    const [records, setRecords] = useState([]);
    const [columns, setColumns] = useState([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const [success, setSuccess] = useState(null);
    const [deleteConfirm, setDeleteConfirm] = useState(null);
    const size = 20;

    // 只允许操作的岗位相关表（白名单）
    const JOB_TABLES = ['jobs', 'zhaopin_jobs', 'jobs_core', 'jobs_analysis', 'jobs_company'];

    // 表名中文映射
    const getTableLabel = (name) => {
        const map = {
            'jobs': '前程无忧岗位',
            'zhaopin_jobs': '智联招聘岗位',
            'jobs_core': '岗位核心数据',
            'jobs_analysis': '岗位分析数据',
            'jobs_company': '公司信息'
        };
        return map[name] || name;
    };

    // 不显示的字段（ID、jobid 等内部主键）
    const HIDDEN_FIELDS = ['id', 'jobid', 'source_id'];

    // 字段名中文映射（用于表头展示，提升可读性）
    const getFieldLabel = (field) => {
        const map = {
            'position_name': '岗位名称',
            'position_id': '职位ID',
            'city': '城市',
            'district': '区',
            'city_tier': '城市等级',
            'salary': '薪资',
            'salary_avg': '平均薪资',
            'salary_range': '薪资范围',
            'education': '学历',
            'education_std': '学历要求',
            'experience': '经验',
            'exp_range': '经验要求',
            'work_type': '工作类型',
            'recruit_number': '招聘人数',
            'job_desc': '岗位描述',
            'job_type': '招聘类型',
            'work_address': '工作地址',
            'detailed_address': '详细地址',
            'skill_tags': '技能标签',
            'benefits': '福利',
            'benefit_score': '福利评分',
            'company_name': '公司名称',
            'company_intro': '公司介绍',
            'industry': '行业',
            'industry_category': '行业分类',
            'company_size': '公司规模',
            'property': '企业性质',
            'financing_stage': '融资阶段',
            'job_url': '链接',
            'publish_date': '发布日期',
            'update_time': '更新时间',
            'major': '专业要求',
            'position_name_en': '英文名称',
            'job_function': '职能',
            'job_category': '类别',
            'source': '数据来源',
            'data_source': '数据来源',
            'username': '用户名',
            'email': '邮箱',
            'phone': '手机号',
            'status': '状态',
            'name': '名称',
            'description': '描述',
            'created_at': '创建时间',
            'updated_at': '更新时间'
        };
        return map[field] || field;
    };

    // 格式化显示值（null/undefined 显示"-"，对象转 JSON）
    // 添加HTML实体转义，防止存储型XSS攻击
    const escapeHtml = (str) => {
        const div = document.createElement('div');
        div.appendChild(document.createTextNode(str));
        return div.innerHTML;
    };

    const formatValue = (value) => {
        if (value === null || value === undefined) return '-';
        if (typeof value === 'object') {
            try {
                return escapeHtml(JSON.stringify(value));
            } catch {
                return escapeHtml(String(value));
            }
        }
        return escapeHtml(String(value));
    };

    // 加载表列表（只保留岗位相关表）
    useEffect(() => {
        const fetchTables = async () => {
            try {
                const result = await databaseAPI.getTables();
                if (result.code === 200) {
                    const jobTables = result.data.filter(t => JOB_TABLES.includes(t));
                    setTables(jobTables);
                    if (jobTables.length > 0) {
                        setSelectedTable(jobTables[0]);
                    }
                }
            } catch (err) {
                setError('获取表列表失败');
            }
        };
        fetchTables();
    }, []);

    // 切换表或翻页时加载对应数据
    useEffect(() => {
        if (!selectedTable) return;
        const fetchData = async () => {
            setLoading(true);
            setError(null);
            try {
                const result = await databaseAPI.getTableData(selectedTable, { page, size });
                if (result.code === 200) {
                    setRecords(result.data.records);
                    setColumns(result.data.columns);
                    setTotal(result.data.total);
                }
            } catch (err) {
                setError('获取数据失败');
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, [selectedTable, page]);

    // 删除单条记录，删除后自动刷新当前页数据
    const handleDelete = async (recordId) => {
        try {
            const result = await databaseAPI.deleteRecord(recordId, selectedTable);
            if (result.code === 200) {
                setDeleteConfirm(null);
                setSuccess('删除成功');
                setTimeout(() => setSuccess(null), 3000);
                // 刷新当前页数据（保持分页不变）
                const refreshResult = await databaseAPI.getTableData(selectedTable, { page, size });
                if (refreshResult.code === 200) {
                    setRecords(refreshResult.data.records);
                    setTotal(refreshResult.data.total);
                }
            }
        } catch (err) {
            setError(err.response?.data?.msg || '删除失败');
        }
    };

    const totalPages = Math.ceil(total / size);

    return (
        <div style={styles.container}>
            <h2 style={styles.pageTitle}>岗位数据管理</h2>
            <p style={styles.subtitle}>仅可浏览和删除岗位相关数据，每条记录单独删除</p>

            {/* 提示信息 */}
            {error && <div style={styles.errorMsg}>{error}<span style={styles.closeBtn} onClick={() => setError(null)}>×</span></div>}
            {success && <div style={styles.successMsg}>{success}</div>}

            {/* 表选择器 */}
            <div style={styles.tableSelector}>
                <label style={styles.label}>选择数据表：</label>
                <select
                    style={styles.select}
                    value={selectedTable}
                    onChange={e => { setSelectedTable(e.target.value); setPage(1); }}
                >
                    {tables.map(t => (
                        <option key={t} value={t}>{getTableLabel(t)} ({t})</option>
                    ))}
                </select>
                <span style={styles.recordCount}>共 {total} 条记录</span>
            </div>

            {/* 数据表格 */}
            {loading ? (
                <div style={styles.loading}>加载中...</div>
            ) : (
                <div style={styles.tableCard}>
                    {records.length === 0 ? (
                        <div style={styles.empty}>该表暂无数据</div>
                    ) : (
                        <>
                            <div style={styles.tableWrapper}>
                                    <table style={styles.table}>
                                        <thead>
                                            <tr>
                                                {columns.filter(col => !HIDDEN_FIELDS.includes(col)).map(col => (
                                                    <th key={col} style={styles.th}>{getFieldLabel(col)}</th>
                                                ))}
                                                <th style={{ ...styles.th, textAlign: 'center' }}>操作</th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {records.map((row, rowIndex) => (
                                                <tr key={row.id || rowIndex} style={rowIndex % 2 === 0 ? styles.trEven : styles.trOdd}>
                                                    {columns.filter(col => !HIDDEN_FIELDS.includes(col)).map(col => (
                                                        <td key={col} style={styles.td} title={formatValue(row[col])}>
                                                            <div style={styles.cellContent}>
                                                                {formatValue(row[col])}
                                                            </div>
                                                        </td>
                                                    ))}
                                                    <td style={{ ...styles.td, textAlign: 'center' }}>
                                                        <button style={styles.deleteBtn} onClick={() => setDeleteConfirm(row)}>删除</button>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                            </div>

                            {/* 分页控件 */}
                            {totalPages > 1 && (
                                <div style={styles.pagination}>
                                    <button style={styles.pageBtn} disabled={page <= 1} onClick={() => setPage(p => p - 1)}>上一页</button>
                                    <span style={styles.pageInfo}>第 {page} 页 / 共 {totalPages} 页</span>
                                    <button style={styles.pageBtn} disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>下一页</button>
                                </div>
                            )}
                        </>
                    )}
                </div>
            )}

            {/* 删除确认弹窗 */}
            {deleteConfirm && (
                <div style={styles.modalOverlay}>
                    <div style={styles.modal}>
                        <h3 style={styles.modalTitle}>确认删除</h3>
                        <p style={styles.confirmText}>
                            确定要删除 {selectedTable} 表中 ID={deleteConfirm.id} 的记录吗？此操作不可恢复。
                        </p>
                        <div style={styles.modalFooter}>
                            <button style={styles.cancelBtn} onClick={() => setDeleteConfirm(null)}>取消</button>
                            <button style={styles.confirmBtn} onClick={() => handleDelete(deleteConfirm.id)}>确认删除</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

const styles = {
    container: { padding: '20px' },
    pageTitle: { fontSize: '24px', fontWeight: 'bold', marginBottom: '8px', color: '#262626' },
    subtitle: { fontSize: '14px', color: '#999', marginBottom: '20px' },
    loading: { textAlign: 'center', padding: '50px', fontSize: '16px', color: '#999' },
    errorMsg: { background: '#fff2f0', border: '1px solid #ffccc7', color: '#ff4d4f', padding: '10px 16px', borderRadius: '6px', marginBottom: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
    successMsg: { background: '#f6ffed', border: '1px solid #b7eb8f', color: '#52c41a', padding: '10px 16px', borderRadius: '6px', marginBottom: '16px' },
    closeBtn: { cursor: 'pointer', fontSize: '18px', fontWeight: 'bold' },
    tableSelector: { display: 'flex', alignItems: 'center', gap: '12px', marginBottom: '16px', background: '#fff', padding: '16px', borderRadius: '8px', boxShadow: '0 2px 8px rgba(0,0,0,0.1)' },
    label: { fontSize: '14px', fontWeight: '500', color: '#333' },
    select: { padding: '8px 12px', border: '1px solid #d9d9d9', borderRadius: '4px', fontSize: '14px', minWidth: '200px' },
    recordCount: { color: '#666', fontSize: '14px', marginLeft: 'auto' },
    tableCard: { background: '#fff', borderRadius: '8px', boxShadow: '0 2px 8px rgba(0,0,0,0.1)' },
    tableWrapper: { overflowX: 'auto' },
    table: { width: '100%', borderCollapse: 'collapse' },
    th: { padding: '12px 16px', textAlign: 'left', fontWeight: '600', color: '#262626', borderBottom: '2px solid #f0f0f0', whiteSpace: 'nowrap', background: '#fafafa', fontSize: '13px' },
    td: { padding: '10px 16px', borderBottom: '1px solid #f0f0f0', color: '#595959', fontSize: '13px' },
    trEven: { background: '#fafafa' },
    trOdd: { background: '#fff' },
    cellContent: { maxWidth: '200px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' },
    deleteBtn: { padding: '4px 12px', background: '#fff2f0', color: '#ff4d4f', border: '1px solid #ffccc7', borderRadius: '4px', cursor: 'pointer', fontSize: '12px' },
    empty: { textAlign: 'center', padding: '50px', color: '#999' },
    pagination: { display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '16px', padding: '16px' },
    pageBtn: { padding: '6px 14px', border: '1px solid #d9d9d9', borderRadius: '4px', background: '#fff', cursor: 'pointer', fontSize: '13px' },
    pageInfo: { fontSize: '13px', color: '#666' },
    modalOverlay: { position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 },
    modal: { background: '#fff', borderRadius: '8px', padding: '24px', width: '400px', maxWidth: '90vw' },
    modalTitle: { fontSize: '18px', fontWeight: '600', marginBottom: '16px', color: '#262626' },
    confirmText: { fontSize: '14px', color: '#666', lineHeight: '1.6' },
    modalFooter: { display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '20px' },
    cancelBtn: { padding: '8px 16px', background: '#fff', color: '#666', border: '1px solid #d9d9d9', borderRadius: '4px', cursor: 'pointer', fontSize: '14px' },
    confirmBtn: { padding: '8px 16px', background: '#ff4d4f', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '14px' }
};

export default DatabasePage;
