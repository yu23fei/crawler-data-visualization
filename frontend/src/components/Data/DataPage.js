// DataPage.js - 岗位数据查看页面（普通用户可用）
// 分页展示全部岗位信息，数据来自 /api/job/page 接口
import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { dataAPI } from '../../utils/api';
import { getUserRole } from '../../utils/auth';

const DataPage = () => {
    const navigate = useNavigate();
    const role = getUserRole();
    const basePath = role === 'admin' ? '/admin' : role === 'vip' ? '/vip' : '/guest';

    const [data, setData] = useState([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const size = 20;

    // 切换页码时重新拉取数据
    useEffect(() => {
        const fetchData = async () => {
            setLoading(true);
            try {
                const result = await dataAPI.getJobPage({ page, size });
                if (result.code === 200) {
                    setData(result.data);
                    setTotal(result.total);
                } else {
                    setError(result.msg || '获取数据失败');
                }
            } catch (err) {
                setError('网络错误，请检查后端服务是否启动');
            } finally {
                setLoading(false);
            }
        };
        fetchData();
    }, [page]);

    const totalPages = Math.ceil(total / size);

    if (error) return <div style={styles.error}>{error}</div>;

    return (
        <div style={styles.container}>
            <h2 style={styles.pageTitle}>岗位数据查看</h2>
            
            <div style={styles.tableCard}>
                <div style={styles.tableHeader}>
                    <span>共 {total} 条记录</span>
                    <span>第 {page} / {totalPages} 页</span>
                </div>
                
                {loading ? (
                    <div style={styles.loading}>加载中...</div>
                ) : (
                    <div style={styles.tableWrapper}>
                        <table style={styles.table}>
                            <thead>
                                <tr>
                                    <th style={styles.th}>岗位名称</th>
                                    <th style={styles.th}>公司名称</th>
                                    <th style={styles.th}>工作城市</th>
                                    <th style={styles.th}>学历要求</th>
                                    <th style={styles.th}>经验要求</th>
                                    <th style={styles.th}>薪资</th>
                                    <th style={styles.th}>公司规模</th>
                                    <th style={styles.th}>公司性质</th>
                                    <th style={styles.th}>操作</th>
                                </tr>
                            </thead>
                            <tbody>
                                {data.map((row, index) => (
                                    <tr key={index} style={index % 2 === 0 ? styles.trEven : styles.trOdd}>
                                        {/* 字段名兼容：保留 fallback 以兼容不同数据源的命名差异 */}
                                        <td style={styles.td}>
                                            <span style={styles.link} onClick={() => navigate(`${basePath}/job-detail?id=${row.id}&source=${row.source}`)}>
                                                {row.position_name || row.job_name || '-'}
                                            </span>
                                        </td>
                                        <td style={styles.td}>{row.company_name || '-'}</td>
                                        <td style={styles.td}>{row.city || '-'}</td>
                                        <td style={styles.td}>{row.education_std || row.education || '-'}</td>
                                        <td style={styles.td}>{row.exp_range || row.experience || '-'}</td>
                                        <td style={styles.td}>{row.salary_range || row.salary_avg || '-'}</td>
                                        <td style={styles.td}>{row.company_size || row.company_scale || '-'}</td>
                                        <td style={styles.td}>{row.property || row.company_nature || '-'}</td>
                                        <td style={styles.td}>
                                            <span style={styles.link} onClick={() => navigate(`${basePath}/job-detail?id=${row.id}&source=${row.source}`)}>
                                                详情
                                            </span>
                                        </td>
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
    pageInfo: { fontSize: '14px', color: '#666' },
    link: { color: '#1890ff', cursor: 'pointer', textDecoration: 'none' }
};

export default DataPage;
