import React, { useState, useEffect } from 'react';
import { authAPI } from '../../utils/api';
import { getUser } from '../../utils/auth';

const ProfilePage = () => {
    const [profile, setProfile] = useState(null);
    const [loading, setLoading] = useState(true);
    const [applying, setApplying] = useState(false);
    const [result, setResult] = useState(null);

    useEffect(() => {
        authAPI.getProfile().then(res => {
            if (res.code === 200) {
                setProfile(res.data);
            }
        }).finally(() => setLoading(false));
    }, []);

    const handleApplyVip = async () => {
        setApplying(true);
        setResult(null);
        try {
            const res = await authAPI.applyVip();
            setResult({ type: res.code === 200 ? 'success' : 'error', msg: res.msg });
        } catch (err) {
            setResult({ type: 'error', msg: err.response?.data?.msg || '申请失败' });
        } finally {
            setApplying(false);
        }
    };

    if (loading) return <div style={styles.loading}>加载中...</div>;

    const user = getUser();
    const role = profile?.roles?.[0]?.name || user?.role || 'guest';

    return (
        <div style={styles.container}>
            <h2 style={styles.title}>个人信息</h2>
            <div style={styles.card}>
                <div style={styles.infoRow}>
                    <span style={styles.label}>用户名</span>
                    <span style={styles.value}>{profile?.user?.username || user?.username}</span>
                </div>
                <div style={styles.infoRow}>
                    <span style={styles.label}>邮箱</span>
                    <span style={styles.value}>{profile?.user?.email || '-'}</span>
                </div>
                <div style={styles.infoRow}>
                    <span style={styles.label}>手机</span>
                    <span style={styles.value}>{profile?.user?.phone || '-'}</span>
                </div>
                <div style={styles.infoRow}>
                    <span style={styles.label}>当前角色</span>
                    <span style={{
                        ...styles.roleBadge,
                        background: role === 'vip' ? '#faad14' : role === 'admin' ? '#f5222d' : '#52c41a'
                    }}>
                        {role === 'admin' ? '管理员' : role === 'vip' ? 'VIP用户' : '普通用户'}
                    </span>
                </div>
                <div style={styles.infoRow}>
                    <span style={styles.label}>注册时间</span>
                    <span style={styles.value}>
                        {profile?.user?.created_at ? new Date(profile.user.created_at).toLocaleDateString() : '-'}
                    </span>
                </div>
            </div>

            {role === 'guest' && (
                <div style={styles.upgradeSection}>
                    <h3 style={styles.sectionTitle}>升级VIP</h3>
                    <p style={styles.upgradeDesc}>VIP用户可查看详细数据、筛选岗位等更多功能</p>
                    {result && (
                        <div style={{
                            ...styles.resultMsg,
                            background: result.type === 'success' ? '#f6ffed' : '#fff2f0',
                            color: result.type === 'success' ? '#52c41a' : '#ff4d4f'
                        }}>
                            {result.msg}
                        </div>
                    )}
                    <button
                        style={styles.upgradeBtn}
                        onClick={handleApplyVip}
                        disabled={applying}
                    >
                        {applying ? '提交中...' : '申请升级VIP'}
                    </button>
                </div>
            )}

            {role === 'vip' && (
                <div style={styles.vipInfo}>
                    <span style={styles.vipBadge}>✓ 您是VIP用户，享有全部数据权限</span>
                </div>
            )}
        </div>
    );
};

const styles = {
    container: { padding: '20px', maxWidth: '600px', margin: '0 auto' },
    title: { fontSize: '24px', fontWeight: 'bold', marginBottom: '24px', color: '#262626' },
    loading: { textAlign: 'center', padding: '50px', fontSize: '16px', color: '#999' },
    card: { background: '#fff', borderRadius: '8px', boxShadow: '0 2px 8px rgba(0,0,0,0.1)', padding: '24px' },
    infoRow: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 0', borderBottom: '1px solid #f0f0f0' },
    label: { color: '#666', fontSize: '14px' },
    value: { color: '#262626', fontSize: '14px', fontWeight: '500' },
    roleBadge: { display: 'inline-block', padding: '2px 12px', borderRadius: '10px', color: '#fff', fontSize: '12px', fontWeight: '500' },
    upgradeSection: { background: '#fff', borderRadius: '8px', boxShadow: '0 2px 8px rgba(0,0,0,0.1)', padding: '24px', marginTop: '20px', textAlign: 'center' },
    sectionTitle: { fontSize: '18px', fontWeight: '600', marginBottom: '12px', color: '#262626' },
    upgradeDesc: { color: '#666', fontSize: '14px', marginBottom: '20px', lineHeight: '1.6' },
    resultMsg: { padding: '10px 16px', borderRadius: '6px', marginBottom: '16px', fontSize: '14px' },
    upgradeBtn: { padding: '10px 32px', background: 'linear-gradient(135deg, #faad14 0%, #f5222d 100%)', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '16px', fontWeight: '500' },
    vipInfo: { marginTop: '20px', textAlign: 'center' },
    vipBadge: { display: 'inline-block', padding: '10px 24px', background: '#f6ffed', color: '#52c41a', borderRadius: '6px', fontSize: '14px', fontWeight: '500', border: '1px solid #b7eb8f' },
};

export default ProfilePage;
