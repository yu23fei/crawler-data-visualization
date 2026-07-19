// FilterPage.js - 岗位筛选页面（VIP 角色专用）
// 支持按城市、学历、公司规模、行业、公司性质多维度筛选
import React, { useState, useEffect } from 'react';
import { dataAPI } from '../../utils/api';

const FilterPage = () => {
    // 筛选条件输入框状态
    const [filters, setFilters] = useState({
        city: '',
        education: '',
        company_size: '',
        industry: '',
        company_type: ''
    });
    // 已生效的筛选参数（用于分页时保留筛选条件）
    const [activeFilters, setActiveFilters] = useState({});
    const [data, setData] = useState([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState(null);
    const size = 20;

    // 统一查询函数：page 和 activeFilters 任一变化时重新请求数据
    const fetchData = async (currentPage, currentFilters) => {
        setLoading(true);
        setError(null);
        try {
            const params = { page: currentPage, size };
            Object.keys(currentFilters).forEach(key => {
                if (currentFilters[key]) params[key] = currentFilters[key];
            });
            const result = await dataAPI.filterJobs(params);
            if (result.code === 200) {
                setData(result.data);
                setTotal(result.total);
            } else {
                setError(result.msg || '查询失败');
            }
        } catch (err) {
            setError('网络错误，请检查后端服务是否启动');
        } finally {
            setLoading(false);
        }
    };

    // 执行筛选：将当前筛选条件提交为生效条件，重置到第一页
    const handleFilter = () => {
        const params = {};
        Object.keys(filters).forEach(key => {
            if (filters[key]) params[key] = filters[key];
        });
        setActiveFilters(params);
        setPage(1);
    };

    // 分页或筛选条件变化时重新加载数据
    useEffect(() => {
        fetchData(page, activeFilters);
    }, [page, activeFilters]);

    const totalPages = Math.ceil(total / size);

    const inputStyle = {
        padding: '8px 12px',
        border: '1px solid #d9d9d9',
        borderRadius: '4px',
        fontSize: '14px',
        minWidth: '150px'
    };

    const btnStyle = {
        padding: '8px 24px',
        background: '#1890ff',
        color: '#fff',
        border: 'none',
        borderRadius: '4px',
        cursor: 'pointer',
        fontSize: '14px'
    };

    const resetBtnStyle = {
        padding: '8px 24px',
        background: '#fff',
        color: '#666',
        border: '1px solid #d9d9d9',
        borderRadius: '4px',
        cursor: 'pointer',
        fontSize: '14px'
    };

    return (
        <div style={styles.container}>
            <h2 style={styles.pageTitle}>岗位筛选</h2>
            
            {/* 筛选条件卡片 */}
            <div style={styles.filterCard}>
                <div style={styles.filterRow}>
                    <div style={styles.filterItem}>
                        <label style={styles.label}>城市</label>
                        <input 
                            style={inputStyle}
                            value={filters.city}
                            onChange={e => setFilters({ ...filters, city: e.target.value })}
                            placeholder="请输入城市"
                        />
                    </div>
                    <div style={styles.filterItem}>
                        <label style={styles.label}>学历</label>
                        <input 
                            style={inputStyle}
                            value={filters.education}
                            onChange={e => setFilters({ ...filters, education: e.target.value })}
                            placeholder="请输入学历"
                        />
                    </div>
                    <div style={styles.filterItem}>
                        <label style={styles.label}>公司规模</label>
                        <input 
                            style={inputStyle}
                            value={filters.company_size}
                            onChange={e => setFilters({ ...filters, company_size: e.target.value })}
                            placeholder="请输入公司规模"
                        />
                    </div>
                    <div style={styles.filterItem}>
                        <label style={styles.label}>行业</label>
                        <input 
                            style={inputStyle}
                            value={filters.industry}
                            onChange={e => setFilters({ ...filters, industry: e.target.value })}
                            placeholder="请输入行业"
                        />
                    </div>
                    <div style={styles.filterItem}>
                        <label style={styles.label}>公司性质</label>
                        <input 
                            style={inputStyle}
                            value={filters.company_type}
                            onChange={e => setFilters({ ...filters, company_type: e.target.value })}
                            placeholder="请输入公司性质"
                        />
                    </div>
                    <div style={styles.filterItem}>
                        <button style={btnStyle} onClick={handleFilter}>筛选</button>
                        <button 
                            style={resetBtnStyle} 
                            onClick={() => {
                                setFilters({ city: '', education: '', company_size: '', industry: '', company_type: '' });
                                setActiveFilters({});
                                setPage(1);
                            }}
                        >
                            重置
                        </button>
                    </div>
                </div>
            </div>

            {/* 筛选结果表格 */}
            <div style={styles.tableCard}>
                <div style={styles.tableHeader}>
                    <span>共 {total} 条记录</span>
                    <span>第 {page} / {totalPages} 页</span>
                </div>
                
                {loading ? (
                    <div style={styles.loading}>加载中...</div>
                ) : error ? (
                    <div style={styles.error}>{error}</div>
                ) : (
                    <div style={styles.tableWrapper}>
                        <table style={styles.table}>
                            <thead>
                                <tr>
                                    <th style={styles.th}>岗位名称</th>
                                    <th style={styles.th}>公司名称</th>
                                    <th style={styles.th}>城市</th>
                                    <th style={styles.th}>学历</th>
                                    <th style={styles.th}>经验</th>
                                    <th style={styles.th}>薪资</th>
                                    <th style={styles.th}>公司规模</th>
                                    <th style={styles.th}>行业</th>
                                </tr>
                            </thead>
                            <tbody>
                                {data.map((row, index) => (
                                    <tr key={index} style={index % 2 === 0 ? styles.trEven : styles.trOdd}>
                                        <td style={styles.td}>{row.position_name || row.job_name || '-'}</td>
                                        <td style={styles.td}>{row.company_name || '-'}</td>
                                        <td style={styles.td}>{row.city || '-'}</td>
                                        <td style={styles.td}>{row.education_std || '-'}</td>
                                        <td style={styles.td}>{row.exp_range || '-'}</td>
                                        <td style={styles.td}>{row.salary_range || '-'}</td>
                                        <td style={styles.td}>{row.company_size || '-'}</td>
                                        <td style={styles.td}>{row.industry_category || '-'}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
                
                <div style={styles.pagination}>
                    <button 
                        style={styles.pageBtn}
                        disabled={page <= 1}
                        onClick={() => setPage(p => p - 1)}
                    >
                        上一页
                    </button>
                    <span style={styles.pageInfo}>第 {page} 页 / 共 {totalPages} 页</span>
                    <button 
                        style={styles.pageBtn}
                        disabled={page >= totalPages}
                        onClick={() => setPage(p => p + 1)}
                    >
                        下一页
                    </button>
                </div>
            </div>
        </div>
    );
};

const styles = {
    container: { padding: '20px' },
    pageTitle: { fontSize: '24px', fontWeight: 'bold', marginBottom: '24px', color: '#262626' },
    loading: { textAlign: 'center', padding: '50px', fontSize: '16px', color: '#999' },
    error: { textAlign: 'center', padding: '50px', fontSize: '16px', color: '#ff4d4f' },
    filterCard: { background: '#fff', borderRadius: '8px', padding: '20px', marginBottom: '20px', boxShadow: '0 2px 8px rgba(0,0,0,0.1)' },
    filterRow: { display: 'flex', flexWrap: 'wrap', gap: '16px', alignItems: 'flex-end' },
    filterItem: { display: 'flex', flexDirection: 'column', gap: '4px' },
    label: { fontSize: '14px', color: '#666' },
    tableCard: { background: '#fff', borderRadius: '8px', boxShadow: '0 2px 8px rgba(0,0,0,0.1)' },
    tableHeader: { display: 'flex', justifyContent: 'space-between', padding: '16px 20px', borderBottom: '1px solid #f0f0f0', fontSize: '14px', color: '#666' },
    tableWrapper: { overflowX: 'auto' },
    table: { width: '100%', borderCollapse: 'collapse' },
    th: { padding: '12px 16px', textAlign: 'left', fontWeight: '600', color: '#262626', borderBottom: '2px solid #f0f0f0', whiteSpace: 'nowrap' },
    td: { padding: '12px 16px', borderBottom: '1px solid #f0f0f0', color: '#595959' },
    trEven: { background: '#fafafa' },
    trOdd: { background: '#fff' },
    pagination: { display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '16px', padding: '16px' },
    pageBtn: { padding: '8px 16px', border: '1px solid #d9d9d9', borderRadius: '4px', background: '#fff', cursor: 'pointer', fontSize: '14px' },
    pageInfo: { fontSize: '14px', color: '#666' }
};

export default FilterPage;
