import React, { useState, useEffect } from 'react';
import { authAPI } from '../../utils/api';
import { getUser } from '../../utils/auth';

const MODE_VIEW = 'view';
const MODE_EDIT_PROFILE = 'edit_profile';
const MODE_CHANGE_PASSWORD = 'change_password';

const ProfilePage = () => {
    const [profile, setProfile] = useState(null);
    const [loading, setLoading] = useState(true);
    const [mode, setMode] = useState(MODE_VIEW);
    const [applying, setApplying] = useState(false);
    const [result, setResult] = useState(null);

    const [formData, setFormData] = useState({
        email: '', phone: '', security_question: '', security_answer: ''
    });
    const [passwordData, setPasswordData] = useState({
        old_password: '', new_password: '', confirm_password: ''
    });
    const [saving, setSaving] = useState(false);
    const [showPassword, setShowPassword] = useState(false); // 密码显示/隐藏切换

    const loadProfile = () => {
        setLoading(true);
        authAPI.getProfile().then(res => {
            if (res.code === 200) {
                setProfile(res.data);
            }
        }).finally(() => setLoading(false));
    };

    useEffect(() => { loadProfile(); }, []);

    const user = getUser();
    const role = profile?.roles?.[0]?.name || user?.role || 'guest';

    const openEditProfile = () => {
        const p = profile?.user || {};
        setFormData({
            email: p.email || '',
            phone: p.phone || '',
            security_question: p.security_question || '',
            security_answer: ''
        });
        setMode(MODE_EDIT_PROFILE);
        setResult(null);
    };

    const openChangePassword = () => {
        setPasswordData({ old_password: '', new_password: '', confirm_password: '' });
        setMode(MODE_CHANGE_PASSWORD);
        setResult(null);
    };

    const handleSaveProfile = async () => {
        setSaving(true);
        setResult(null);
        try {
            const payload = {};
            if (formData.email) payload.email = formData.email;
            if (formData.phone) payload.phone = formData.phone;
            if (formData.security_question && formData.security_answer) {
                payload.security_question = formData.security_question;
                payload.security_answer = formData.security_answer;
            }
            const res = await authAPI.updateProfile(payload);
            if (res.code === 200) {
                setResult({ type: 'success', msg: res.msg });
                setMode(MODE_VIEW);
                loadProfile();
            } else {
                setResult({ type: 'error', msg: res.msg });
            }
        } catch (err) {
            setResult({ type: 'error', msg: err.response?.data?.msg || '保存失败' });
        } finally {
            setSaving(false);
        }
    };

    const handleChangePassword = async () => {
        if (passwordData.new_password !== passwordData.confirm_password) {
            setResult({ type: 'error', msg: '两次输入的新密码不一致' });
            return;
        }
        if (passwordData.new_password.length < 8) {
            setResult({ type: 'error', msg: '新密码至少8个字符' });
            return;
        }
        setSaving(true);
        setResult(null);
        try {
            const res = await authAPI.changePassword({
                old_password: passwordData.old_password,
                new_password: passwordData.new_password
            });
            if (res.code === 200) {
                setResult({ type: 'success', msg: res.msg + '，请重新登录' });
                setMode(MODE_VIEW);
            } else {
                setResult({ type: 'error', msg: res.msg });
            }
        } catch (err) {
            setResult({ type: 'error', msg: err.response?.data?.msg || '修改密码失败' });
        } finally {
            setSaving(false);
        }
    };

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

    if (loading && !profile) return <div style={styles.loading}>加载中...</div>;

    const renderResult = () => {
        if (!result) return null;
        return (
            <div style={{
                ...styles.resultMsg,
                background: result.type === 'success' ? '#f6ffed' : '#fff2f0',
                color: result.type === 'success' ? '#52c41a' : '#ff4d4f'
            }}>
                {result.msg}
            </div>
        );
    };

    const renderView = () => (
        <>
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
                    <span style={styles.label}>密保问题</span>
                    <span style={styles.value}>{profile?.user?.security_question || '-'}</span>
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
                <div style={styles.infoRow}>
                    <span style={styles.label}>密码</span>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                        <span style={{
                            fontFamily: 'monospace',
                            fontSize: '14px',
                            color: showPassword ? '#262626' : '#999',
                            fontWeight: showPassword ? '500' : 'normal'
                        }}>
                            {showPassword
                                ? (profile?.user?.plain_password || '(空)')
                                : '••••••••'
                            }
                        </span>
                        <button
                            style={styles.viewPasswordBtn}
                            onClick={() => setShowPassword(!showPassword)}
                        >
                            {showPassword ? '隐藏密码' : '查看密码'}
                        </button>
                    </div>
                </div>
            </div>

            <div style={styles.actions}>
                <button style={styles.actionBtn} onClick={openEditProfile}>编辑个人信息</button>
                <button style={styles.actionBtn} onClick={openChangePassword}>修改密码</button>
            </div>

            {role === 'guest' && (
                <div style={styles.upgradeSection}>
                    <h3 style={styles.sectionTitle}>升级VIP</h3>
                    <p style={styles.upgradeDesc}>VIP用户可查看详细数据、筛选岗位等更多功能</p>
                    <button style={styles.upgradeBtn} onClick={handleApplyVip} disabled={applying}>
                        {applying ? '提交中...' : '申请升级VIP'}
                    </button>
                </div>
            )}

            {role === 'vip' && (
                <div style={styles.vipInfo}>
                    <span style={styles.vipBadge}>✓ 您是VIP用户，享有全部数据权限</span>
                </div>
            )}
        </>
    );

    const renderEditProfile = () => (
        <div style={styles.card}>
            <h3 style={styles.sectionTitle}>编辑个人信息</h3>
            <div style={styles.formGroup}>
                <label style={styles.formLabel}>邮箱</label>
                <input style={styles.formInput} type="email" placeholder="请输入邮箱"
                    value={formData.email}
                    onChange={e => setFormData({ ...formData, email: e.target.value })} />
            </div>
            <div style={styles.formGroup}>
                <label style={styles.formLabel}>手机号</label>
                <input style={styles.formInput} type="text" placeholder="请输入手机号"
                    value={formData.phone}
                    onChange={e => setFormData({ ...formData, phone: e.target.value })} />
            </div>
            <div style={styles.formGroup}>
                <label style={styles.formLabel}>密保问题（修改需同时填写答案）</label>
                <input style={styles.formInput} type="text" placeholder="请输入新的密保问题"
                    value={formData.security_question}
                    onChange={e => setFormData({ ...formData, security_question: e.target.value })} />
            </div>
            <div style={styles.formGroup}>
                <label style={styles.formLabel}>密保答案</label>
                <input style={styles.formInput} type="text" placeholder="请输入密保答案"
                    value={formData.security_answer}
                    onChange={e => setFormData({ ...formData, security_answer: e.target.value })} />
            </div>
            <div style={styles.formActions}>
                <button style={styles.saveBtn} onClick={handleSaveProfile} disabled={saving}>
                    {saving ? '保存中...' : '保存'}
                </button>
                <button style={styles.cancelBtn} onClick={() => setMode(MODE_VIEW)}>取消</button>
            </div>
        </div>
    );

    const renderChangePassword = () => (
        <div style={styles.card}>
            <h3 style={styles.sectionTitle}>修改密码</h3>
            <div style={styles.formGroup}>
                <label style={styles.formLabel}>原密码</label>
                <input style={styles.formInput} type="password" placeholder="请输入原密码"
                    value={passwordData.old_password}
                    onChange={e => setPasswordData({ ...passwordData, old_password: e.target.value })} />
            </div>
            <div style={styles.formGroup}>
                <label style={styles.formLabel}>新密码</label>
                <input style={styles.formInput} type="password" placeholder="8-64位，包含大小写字母和数字"
                    value={passwordData.new_password}
                    onChange={e => setPasswordData({ ...passwordData, new_password: e.target.value })} />
            </div>
            <div style={styles.formGroup}>
                <label style={styles.formLabel}>确认新密码</label>
                <input style={styles.formInput} type="password" placeholder="再次输入新密码"
                    value={passwordData.confirm_password}
                    onChange={e => setPasswordData({ ...passwordData, confirm_password: e.target.value })} />
            </div>
            <div style={styles.formActions}>
                <button style={styles.saveBtn} onClick={handleChangePassword} disabled={saving}>
                    {saving ? '修改中...' : '修改密码'}
                </button>
                <button style={styles.cancelBtn} onClick={() => setMode(MODE_VIEW)}>取消</button>
            </div>
        </div>
    );

    return (
        <div style={styles.container}>
            <h2 style={styles.title}>个人信息</h2>
            {renderResult()}
            {mode === MODE_VIEW && renderView()}
            {mode === MODE_EDIT_PROFILE && renderEditProfile()}
            {mode === MODE_CHANGE_PASSWORD && renderChangePassword()}
        </div>
    );
};

const styles = {
    container: { padding: '20px', maxWidth: '600px', margin: '0 auto' },
    title: { fontSize: '24px', fontWeight: 'bold', marginBottom: '24px', color: '#262626' },
    loading: { textAlign: 'center', padding: '50px', fontSize: '16px', color: '#999' },
    card: { background: '#fff', borderRadius: '8px', boxShadow: '0 2px 8px rgba(0,0,0,0.1)', padding: '24px', marginBottom: '20px' },
    infoRow: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '12px 0', borderBottom: '1px solid #f0f0f0' },
    label: { color: '#666', fontSize: '14px' },
    value: { color: '#262626', fontSize: '14px', fontWeight: '500' },
    roleBadge: { display: 'inline-block', padding: '2px 12px', borderRadius: '10px', color: '#fff', fontSize: '12px', fontWeight: '500' },
    actions: { display: 'flex', gap: '12px', marginBottom: '20px' },
    actionBtn: { flex: 1, padding: '10px 16px', background: '#1890ff', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '14px', fontWeight: '500' },
    upgradeSection: { background: '#fff', borderRadius: '8px', boxShadow: '0 2px 8px rgba(0,0,0,0.1)', padding: '24px', textAlign: 'center' },
    sectionTitle: { fontSize: '18px', fontWeight: '600', marginBottom: '12px', color: '#262626' },
    upgradeDesc: { color: '#666', fontSize: '14px', marginBottom: '20px', lineHeight: '1.6' },
    resultMsg: { padding: '10px 16px', borderRadius: '6px', marginBottom: '16px', fontSize: '14px' },
    upgradeBtn: { padding: '10px 32px', background: 'linear-gradient(135deg, #faad14 0%, #f5222d 100%)', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '16px', fontWeight: '500' },
    vipInfo: { textAlign: 'center' },
    vipBadge: { display: 'inline-block', padding: '10px 24px', background: '#f6ffed', color: '#52c41a', borderRadius: '6px', fontSize: '14px', fontWeight: '500', border: '1px solid #b7eb8f' },
    formGroup: { marginBottom: '16px' },
    formLabel: { display: 'block', marginBottom: '6px', color: '#666', fontSize: '14px', fontWeight: '500' },
    formInput: { width: '100%', padding: '8px 12px', border: '1px solid #d9d9d9', borderRadius: '4px', fontSize: '14px', boxSizing: 'border-box' },
    formActions: { display: 'flex', gap: '12px', marginTop: '24px' },
    saveBtn: { flex: 1, padding: '10px 16px', background: '#52c41a', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '14px', fontWeight: '500' },
    cancelBtn: { flex: 1, padding: '10px 16px', background: '#fff', color: '#666', border: '1px solid #d9d9d9', borderRadius: '6px', cursor: 'pointer', fontSize: '14px' },
    viewPasswordBtn: { padding: '3px 12px', background: '#fff', color: '#1890ff', border: '1px solid #91d5ff', borderRadius: '4px', cursor: 'pointer', fontSize: '12px', whiteSpace: 'nowrap' },
};

export default ProfilePage;
