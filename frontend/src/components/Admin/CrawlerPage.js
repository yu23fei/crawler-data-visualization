// CrawlerPage.js - 爬虫管理页面（管理员专用）
// 独立控制 前程无忧 和 智联招聘 两个爬虫的启动/停止，实时查看运行状态
import React, { useState, useEffect, useCallback } from 'react';
import { crawlerAPI } from '../../utils/api';

// 数据源显示名映射
const SOURCE_LABELS = { '51job': '前程无忧', zhaopin: '智联招聘' };
const SOURCE_COLORS = { '51job': '#1677ff', zhaopin: '#52c41a' };

const CrawlerPage = () => {
    // 爬虫状态数据
    const [crawlers, setCrawlers] = useState({
        '51job': { status: 'stopped', started_at: null, last_run: null, error: null, total_fetched: 0 },
        zhaopin: { status: 'stopped', started_at: null, last_run: null, error: null, total_fetched: 0 }
    });
    const [loading, setLoading] = useState(true);
    const [actionLoading, setActionLoading] = useState({ '51job': false, zhaopin: false });
    const [recentJobs, setRecentJobs] = useState([]);
    const [recentJobsLoading, setRecentJobsLoading] = useState(false);

    // 获取所有爬虫状态
    const fetchStatus = useCallback(async () => {
        try {
            const result = await crawlerAPI.getAllStatus();
            if (result.code === 200) {
                setCrawlers(result.data);
            }
        } catch (err) {
            console.error('获取爬虫状态失败');
        } finally {
            setLoading(false);
        }
    }, []);

    // 获取最近入库数据
    const fetchRecentJobs = useCallback(async (source) => {
        setRecentJobsLoading(true);
        try {
            const result = await crawlerAPI.getRecentJobs({ limit: 10, source: source || 'all' });
            if (result.code === 200) {
                setRecentJobs(result.data);
            }
        } catch (err) {
            console.error('获取最近入库数据失败');
        } finally {
            setRecentJobsLoading(false);
        }
    }, []);

    // 定时轮询状态（每 3 秒刷新一次）
    useEffect(() => {
        fetchStatus();
        fetchRecentJobs();
        const interval = setInterval(() => {
            fetchStatus();
            fetchRecentJobs();
        }, 3000);
        return () => clearInterval(interval);
    }, [fetchStatus, fetchRecentJobs]);

    // 启动爬虫
    const handleStart = async (source) => {
        setActionLoading(prev => ({ ...prev, [source]: true }));
        try {
            const result = await crawlerAPI.start(source);
            if (result.code === 200) {
                await fetchStatus();
            }
        } catch (err) {
            console.error('启动失败', err);
        } finally {
            setActionLoading(prev => ({ ...prev, [source]: false }));
        }
    };

    // 停止爬虫
    const handleStop = async (source) => {
        setActionLoading(prev => ({ ...prev, [source]: true }));
        try {
            const result = await crawlerAPI.stop(source);
            if (result.code === 200) {
                await fetchStatus();
            }
        } catch (err) {
            console.error('停止失败', err);
        } finally {
            setActionLoading(prev => ({ ...prev, [source]: false }));
        }
    };

    // 爬虫配置元信息
    const crawlerMeta = {
        '51job': {
            name: '前程无忧',
            icon: '🔵',
            color: '#1677ff',
            bgColor: '#e6f4ff',
            borderColor: '#91caff',
            dbTable: 'jobs',
            description: '采集 前程无忧 平台招聘数据'
        },
        zhaopin: {
            name: '智联招聘',
            icon: '🟢',
            color: '#52c41a',
            bgColor: '#f6ffed',
            borderColor: '#b7eb8f',
            dbTable: 'zhaopin_jobs',
            description: '采集 智联招聘 平台招聘数据'
        }
    };

    // 状态显示
    const renderStatus = (status) => {
        const statusMap = {
            running: { text: '运行中', color: '#52c41a', bg: '#f6ffed' },
            stopped: { text: '已停止', color: '#999', bg: '#fafafa' },
            error: { text: '异常', color: '#ff4d4f', bg: '#fff2f0' }
        };
        const info = statusMap[status] || statusMap.stopped;
        return <span style={{ ...styles.statusBadge, color: info.color, background: info.bg }}>{info.text}</span>;
    };

    if (loading) return <div style={styles.loading}>加载中...</div>;

    return (
        <div style={styles.container}>
            <h2 style={styles.pageTitle}>爬虫管理</h2>
            <p style={styles.subtitle}>独立控制 前程无忧和智联招聘两个爬虫的启动与停止</p>

            <div style={styles.crawlerGrid}>
                {Object.entries(crawlerMeta).map(([source, meta]) => {
                    const crawler = crawlers[source] || { status: 'stopped' };
                    const isRunning = crawler.status === 'running';

                    return (
                        <div key={source} style={{ ...styles.crawlerCard, borderColor: meta.borderColor }}>
                            {/* 爬虫头部 */}
                            <div style={{ ...styles.cardHeader, background: meta.bgColor, borderBottom: `1px solid ${meta.borderColor}` }}>
                                <span style={styles.cardIcon}>{meta.icon}</span>
                                <span style={styles.cardTitle}>{meta.name}</span>
                                {renderStatus(crawler.status)}
                            </div>

                            {/* 爬虫详情 */}
                            <div style={styles.cardBody}>
                                <div style={styles.infoRow}>
                                    <span style={styles.infoLabel}>数据表</span>
                                    <span style={styles.infoValue}>{meta.dbTable}</span>
                                </div>
                                <div style={styles.infoRow}>
                                    <span style={styles.infoLabel}>说明</span>
                                    <span style={styles.infoValue}>{meta.description}</span>
                                </div>
                                {crawler.started_at && (
                                    <div style={styles.infoRow}>
                                        <span style={styles.infoLabel}>启动时间</span>
                                        <span style={styles.infoValue}>{crawler.started_at}</span>
                                    </div>
                                )}
                                {crawler.last_run && (
                                    <div style={styles.infoRow}>
                                        <span style={styles.infoLabel}>上次运行</span>
                                        <span style={styles.infoValue}>{crawler.last_run}</span>
                                    </div>
                                )}
                                {crawler.error && (
                                    <div style={styles.infoRow}>
                                        <span style={styles.infoLabel}>错误信息</span>
                                        <span style={{ ...styles.infoValue, color: '#ff4d4f' }}>{crawler.error}</span>
                                    </div>
                                )}
                            </div>

                            {/* 操作按钮 */}
                            <div style={styles.cardFooter}>
                                {isRunning ? (
                                    <button
                                        style={{ ...styles.stopBtn, borderColor: meta.color, color: meta.color }}
                                        onClick={() => handleStop(source)}
                                        disabled={actionLoading[source]}
                                    >
                                        {actionLoading[source] ? '停止中...' : '停止爬虫'}
                                    </button>
                                ) : (
                                    <button
                                        style={{ ...styles.startBtn, background: meta.color }}
                                        onClick={() => handleStart(source)}
                                        disabled={actionLoading[source]}
                                    >
                                        {actionLoading[source] ? '启动中...' : '启动爬虫'}
                                    </button>
                                )}
                            </div>
                        </div>
                    );
                })}
            </div>

            {/* 最近入库数据 */}
            <div style={styles.recentSection}>
                <div style={styles.recentHeader}>
                    <h3 style={styles.recentTitle}>最近入库数据</h3>
                    <span style={styles.recentBadge}>自动刷新</span>
                </div>
                {recentJobsLoading && recentJobs.length === 0 ? (
                    <div style={styles.loading}>加载中...</div>
                ) : recentJobs.length === 0 ? (
                    <div style={styles.emptyState}>暂无入库数据</div>
                ) : (
                    <div style={styles.tableWrap}>
                        <table style={styles.table}>
                            <thead>
                                <tr>
                                    <th style={styles.th}>数据源</th>
                                    <th style={styles.th}>职位名称</th>
                                    <th style={styles.th}>公司</th>
                                    <th style={styles.th}>城市</th>
                                    <th style={styles.th}>薪资</th>
                                    <th style={styles.th}>链接</th>
                                    <th style={styles.th}>入库时间</th>
                                </tr>
                            </thead>
                            <tbody>
                                {recentJobs.map((job, idx) => (
                                    <tr key={`${job.data_source}-${job.id}-${idx}`} style={styles.tr}>
                                        <td style={styles.td}>
                                            <span style={{
                                                ...styles.sourceTag,
                                                background: SOURCE_COLORS[job.data_source] + '18',
                                                color: SOURCE_COLORS[job.data_source]
                                            }}>
                                                {SOURCE_LABELS[job.data_source] || job.data_source}
                                            </span>
                                        </td>
                                        <td style={styles.td}>{job.position_name || '-'}</td>
                                        <td style={styles.td}>{job.company_name || '-'}</td>
                                        <td style={styles.td}>{job.city || '-'}</td>
                                        <td style={styles.td}>{job.salary || '-'}</td>
                                        <td style={styles.td}>
                                            {job.job_url ? (
                                                <a href={job.job_url} target="_blank" rel="noopener noreferrer" style={{ color: '#1677ff', textDecoration: 'none', fontSize: '12px' }}>
                                                    查看详情
                                                </a>
                                            ) : '-'}
                                        </td>
                                        <td style={{ ...styles.td, color: '#999', fontSize: '12px' }}>{job.created_at || '-'}</td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>
                )}
            </div>
        </div>
    );
};

const styles = {
    container: { padding: '20px' },
    pageTitle: { fontSize: '24px', fontWeight: 'bold', marginBottom: '8px', color: '#262626' },
    subtitle: { fontSize: '14px', color: '#999', marginBottom: '24px' },
    loading: { textAlign: 'center', padding: '50px', fontSize: '16px', color: '#999' },
    crawlerGrid: { display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '20px' },
    crawlerCard: {
        background: '#fff', borderRadius: '10px', overflow: 'hidden',
        boxShadow: '0 2px 8px rgba(0,0,0,0.1)', border: '2px solid'
    },
    cardHeader: {
        display: 'flex', alignItems: 'center', gap: '10px',
        padding: '16px 20px', fontSize: '16px', fontWeight: '600'
    },
    cardIcon: { fontSize: '24px' },
    cardTitle: { flex: 1, color: '#262626' },
    statusBadge: { padding: '3px 10px', borderRadius: '10px', fontSize: '12px', fontWeight: '500' },
    cardBody: { padding: '16px 20px', display: 'flex', flexDirection: 'column', gap: '10px' },
    infoRow: { display: 'flex', alignItems: 'center', gap: '8px' },
    infoLabel: { color: '#999', fontSize: '13px', minWidth: '70px', flexShrink: 0 },
    infoValue: { color: '#595959', fontSize: '13px' },
    cardFooter: { padding: '12px 20px', borderTop: '1px solid #f0f0f0', display: 'flex', justifyContent: 'center' },
    startBtn: { padding: '8px 32px', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '14px', fontWeight: '500' },
    stopBtn: { padding: '8px 32px', background: '#fff', border: '2px solid', borderRadius: '6px', cursor: 'pointer', fontSize: '14px', fontWeight: '500' },
    // 最近入库数据区
    recentSection: { marginTop: '28px', background: '#fff', borderRadius: '10px', boxShadow: '0 2px 8px rgba(0,0,0,0.1)', overflow: 'hidden' },
    recentHeader: { display: 'flex', alignItems: 'center', gap: '10px', padding: '16px 20px', borderBottom: '1px solid #f0f0f0' },
    recentTitle: { margin: 0, fontSize: '16px', fontWeight: '600', color: '#262626' },
    recentBadge: { fontSize: '11px', color: '#999', background: '#fafafa', padding: '2px 8px', borderRadius: '4px', border: '1px solid #f0f0f0' },
    tableWrap: { overflowX: 'auto' },
    table: { width: '100%', borderCollapse: 'collapse', fontSize: '13px' },
    th: { textAlign: 'left', padding: '10px 16px', background: '#fafafa', color: '#595959', fontWeight: '500', borderBottom: '1px solid #f0f0f0', whiteSpace: 'nowrap' },
    tr: { transition: 'background 0.2s' },
    td: { padding: '9px 16px', borderBottom: '1px solid #f5f5f5', color: '#595959' },
    sourceTag: { display: 'inline-block', padding: '2px 8px', borderRadius: '4px', fontSize: '12px', fontWeight: '500' },
    emptyState: { padding: '40px', textAlign: 'center', color: '#999', fontSize: '14px' }
};

export default CrawlerPage;
