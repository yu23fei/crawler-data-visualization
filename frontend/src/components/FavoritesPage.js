import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { dataAPI } from '../utils/api';
import { getUserRole } from '../utils/auth';

const FavoritesPage = () => {
    const navigate = useNavigate();
    const role = getUserRole();
    const basePath = role === 'admin' ? '/admin' : '/vip';

    const [data, setData] = useState([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const size = 20;

    const fetchFavorites = async () => {
        setLoading(true);
        try {
            const result = await dataAPI.getFavorites({ page, size });
            if (result.code === 200) {
                setData(result.data);
                setTotal(result.total);
            } else {
                setError(result.msg || '获取收藏列表失败');
            }
        } catch (err) {
            setError('网络错误，请检查后端服务是否启动');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchFavorites();
    }, [page]);

    const handleViewDetail = (row) => {
        navigate(`${basePath}/job-detail?id=${row.job_id}&source=${row.data_source}`);
    };

    const handleRemoveFavorite = async (row) => {
        try {
            await dataAPI.removeFavorite({ job_id: row.job_id, data_source: row.data_source });
            fetchFavorites();
        } catch (e) {
        }
    };

    const totalPages = Math.ceil(total / size);

    if (error) return <div style={styles.error}>{error}</div>;

    return (
        <div style={styles.container}>
            <h2 style={styles.pageTitle}>我的收藏</h2>

            <div style={styles.tableCard}>
                <div style={styles.tableHeader}>
                    <span>共 {total} 条收藏</span>
                    <span>第 {page} / {totalPages} 页</span>
                </div>

                {loading ? (
                    <div style={styles.loading}>加载中...</div>
                ) : data.length === 0 ? (
                    <div style={styles.empty}>暂无收藏的岗位</div>
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
                                    <th style={styles.th}>收藏时间</th>
                                    <th style={styles.th}>操作</th>
                                </tr>
                            </thead>
                            <tbody>
                                {data.map((row, index) => (
                                    <tr key={index} style={index % 2 === 0 ? styles.trEven : styles.trOdd}>
                                        <td style={styles.td}>
                                            <span style={styles.link} onClick={() => handleViewDetail(row)}>
                                                {row.position_name || '-'}
                                            </span>
                                        </td>
                                        <td style={styles.td}>{row.company_name || '-'}</td>
                                        <td style={styles.td}>{row.city || '-'}</td>
                                        <td style={styles.td}>{row.education_std || '-'}</td>
                                        <td style={styles.td}>{row.exp_range || '-'}</td>
                                        <td style={styles.td}>{row.salary_range || '-'}</td>
                                        <td style={styles.td}>{row.favorited_at || '-'}</td>
                                        <td style={styles.td}>
                                            <button
                                                style={styles.delBtn}
                                                onClick={() => handleRemoveFavorite(row)}
                                            >
                                                取消收藏
                                            </button>
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
    empty: { textAlign: 'center', padding: '50px', fontSize: '16px', color: '#999' },
    tableCard: { background: '#fff', borderRadius: '8px', boxShadow: '0 2px 8px rgba(0,0,0,0.1)' },
    tableHeader: { display: 'flex', justifyContent: 'space-between', padding: '16px 20px', borderBottom: '1px solid #f0f0f0', fontSize: '14px', color: '#666' },
    tableWrapper: { overflowX: 'auto' },
    table: { width: '100%', borderCollapse: 'collapse' },
    th: { padding: '12px 16px', textAlign: 'left', fontWeight: '600', color: '#262626', borderBottom: '2px solid #f0f0f0', whiteSpace: 'nowrap' },
    td: { padding: '12px 16px', borderBottom: '1px solid #f0f0f0', color: '#595959' },
    trEven: { background: '#fafafa' },
    trOdd: { background: '#fff' },
    link: { color: '#1890ff', cursor: 'pointer', textDecoration: 'none' },
    pagination: { display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '16px', padding: '16px' },
    pageBtn: { padding: '8px 16px', border: '1px solid #d9d9d9', borderRadius: '4px', background: '#fff', cursor: 'pointer', fontSize: '14px' },
    pageInfo: { fontSize: '14px', color: '#666' },
    delBtn: {
        padding: '4px 12px', border: '1px solid #ff4d4f', borderRadius: '4px',
        background: '#fff', color: '#ff4d4f', cursor: 'pointer', fontSize: '12px'
    }
};

export default FavoritesPage;
