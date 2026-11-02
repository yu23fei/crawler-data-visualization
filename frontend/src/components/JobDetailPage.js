import React, { useState, useEffect, useCallback } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { dataAPI } from '../utils/api';
import { getUserRole } from '../utils/auth';

const JobDetailPage = () => {
    const [searchParams] = useSearchParams();
    const navigate = useNavigate();
    const role = getUserRole();

    const jobId = searchParams.get('id');
    const source = searchParams.get('source');

    const [detail, setDetail] = useState(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState(null);
    const [isFavorited, setIsFavorited] = useState(false);
    const [favLoading, setFavLoading] = useState(false);

    const fetchDetail = useCallback(async () => {
        if (!jobId || !source) {
            setError('缺少岗位ID或数据来源参数');
            setLoading(false);
            return;
        }
        setLoading(true);
        try {
            const result = await dataAPI.getJobDetail({ id: jobId, source });
            if (result.code === 200) {
                setDetail(result.data);
            } else {
                setError(result.msg || '获取岗位详情失败');
            }
        } catch (err) {
            setError('网络错误，请检查后端服务是否启动');
        } finally {
            setLoading(false);
        }
    }, [jobId, source]);

    const recordHistory = useCallback(async () => {
        if (!jobId || !source) return;
        try {
            await dataAPI.recordHistory({ job_id: jobId, data_source: source });
        } catch (e) {
        }
    }, [jobId, source]);

    const checkFavoriteStatus = useCallback(async () => {
        if (!jobId || !source) return;
        try {
            const result = await dataAPI.getFavorites({ page: 1, size: 1000 });
            if (result.code === 200) {
                const favs = result.data || [];
                const found = favs.some(f => String(f.job_id) === String(jobId) && f.data_source === source);
                setIsFavorited(found);
            }
        } catch (e) {
        }
    }, [jobId, source]);

    useEffect(() => {
        fetchDetail();
        if (role === 'vip') {
            recordHistory();
            checkFavoriteStatus();
        }
    }, [fetchDetail, recordHistory, checkFavoriteStatus, role]);

    const handleToggleFavorite = async () => {
        setFavLoading(true);
        try {
            if (isFavorited) {
                await dataAPI.removeFavorite({ job_id: jobId, data_source: source });
                setIsFavorited(false);
            } else {
                await dataAPI.addFavorite({ job_id: jobId, data_source: source });
                setIsFavorited(true);
            }
        } catch (e) {
        } finally {
            setFavLoading(false);
        }
    };

    const handleGoBack = () => {
        navigate(-1);
    };

    const renderField = (label, value) => {
        if (!value || value === '-' || value === '未知') return null;
        return (
            <div style={styles.fieldRow}>
                <span style={styles.fieldLabel}>{label}</span>
                <span style={styles.fieldValue}>{value}</span>
            </div>
        );
    };

    if (loading) return <div style={styles.centerMsg}>加载中...</div>;
    if (error) return <div style={styles.centerMsg}>{error}</div>;
    if (!detail) return <div style={styles.centerMsg}>岗位不存在</div>;

    const skillTags = detail.skill_tags;
    let tags = [];
    if (skillTags) {
        try {
            tags = typeof skillTags === 'string' ? JSON.parse(skillTags) : skillTags;
        } catch (e) {
            tags = [];
        }
    }

    return (
        <div style={styles.container}>
            <div style={styles.toolbar}>
                <button style={styles.backBtn} onClick={handleGoBack}>← 返回列表</button>
                {role === 'vip' && (
                    <button
                        style={{
                            ...styles.favBtn,
                            background: isFavorited ? '#ff4d4f' : '#1890ff'
                        }}
                        onClick={handleToggleFavorite}
                        disabled={favLoading}
                    >
                        {isFavorited ? '♥ 已收藏' : '♡ 收藏'}
                    </button>
                )}
            </div>

            <div style={styles.card}>
                <h2 style={styles.jobTitle}>{detail.position_name || '岗位名称'}</h2>
                <div style={styles.companyName}>{detail.company_name || '-'}</div>

                <div style={styles.salaryTag}>
                    {detail.salary_range || '薪资面议'}
                </div>

                <div style={styles.divider} />

                <div style={styles.grid}>
                    {renderField('工作城市', detail.city)}
                    {renderField('城市等级', detail.city_tier)}
                    {renderField('学历要求', detail.education_std)}
                    {renderField('经验要求', detail.exp_range)}
                    {renderField('工作类型', detail.work_type)}
                    {renderField('招聘人数', detail.recruit_number)}
                    {renderField('发布日期', detail.publish_date)}
                    {renderField('公司规模', detail.company_size)}
                    {renderField('公司性质', detail.company_nature)}
                    {renderField('融资阶段', detail.financing_stage)}
                    {renderField('所属行业', detail.industry_category)}
                    {renderField('数据来源', detail.source)}
                </div>

                {tags.length > 0 && (
                    <>
                        <div style={styles.divider} />
                        <div style={styles.sectionTitle}>技能标签</div>
                        <div style={styles.tagWrapper}>
                            {tags.map((tag, i) => (
                                <span key={i} style={styles.tag}>{tag}</span>
                            ))}
                        </div>
                    </>
                )}

                {detail.company_intro_clean && (
                    <>
                        <div style={styles.divider} />
                        <div style={styles.sectionTitle}>公司简介</div>
                        <div style={styles.introText}>{detail.company_intro_clean}</div>
                    </>
                )}
            </div>
        </div>
    );
};

const styles = {
    container: { padding: '20px', maxWidth: '900px', margin: '0 auto' },
    centerMsg: { textAlign: 'center', padding: '50px', fontSize: '16px', color: '#999' },
    toolbar: { display: 'flex', justifyContent: 'space-between', marginBottom: '20px' },
    backBtn: {
        padding: '8px 20px', border: '1px solid #d9d9d9', borderRadius: '4px',
        background: '#fff', cursor: 'pointer', fontSize: '14px', color: '#555'
    },
    favBtn: {
        padding: '8px 20px', border: 'none', borderRadius: '4px',
        cursor: 'pointer', fontSize: '14px', color: '#fff'
    },
    card: {
        background: '#fff', borderRadius: '8px', padding: '32px',
        boxShadow: '0 2px 8px rgba(0,0,0,0.1)'
    },
    jobTitle: { fontSize: '22px', fontWeight: 'bold', color: '#262626', margin: '0 0 8px 0' },
    companyName: { fontSize: '16px', color: '#1890ff', marginBottom: '12px' },
    salaryTag: {
        display: 'inline-block', padding: '4px 12px', background: '#fff7e6',
        border: '1px solid #ffd591', borderRadius: '4px', color: '#fa8c16',
        fontSize: '16px', fontWeight: '600'
    },
    divider: { height: '1px', background: '#f0f0f0', margin: '20px 0' },
    grid: { display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '12px' },
    fieldRow: { display: 'flex', padding: '8px 0', borderBottom: '1px dashed #f5f5f5' },
    fieldLabel: {
        width: '100px', color: '#999', fontSize: '14px', flexShrink: 0
    },
    fieldValue: { color: '#262626', fontSize: '14px', flex: 1 },
    sectionTitle: { fontSize: '16px', fontWeight: '600', color: '#262626', marginBottom: '12px' },
    tagWrapper: { display: 'flex', flexWrap: 'wrap', gap: '8px' },
    tag: {
        padding: '4px 12px', background: '#f0f5ff', border: '1px solid #d6e4ff',
        borderRadius: '4px', color: '#2f54eb', fontSize: '13px'
    },
    introText: {
        fontSize: '14px', color: '#595959', lineHeight: '1.8',
        whiteSpace: 'pre-wrap'
    }
};

export default JobDetailPage;
