// frontend/src/components/Layout/Topbar.js
import React from 'react';
import { getUser, getUserRole } from '../../utils/auth';

const Topbar = () => {
    const user = getUser();
    const role = getUserRole();

    const getRoleName = () => {
        switch (role) {
            case 'admin': return '管理员';
            case 'vip': return 'VIP用户';
            case 'guest': return '普通访客';
            default: return '未知角色';
        }
    };

    return (
        <div style={styles.topbar}>
            <div style={styles.left}>
                <h1 style={styles.title}>招聘大数据可视化分析平台</h1>
            </div>
            <div style={styles.right}>
                <div style={styles.userInfo}>
                    <span style={styles.username}>{user?.username || '未登录'}</span>
                    <span style={styles.role}>{getRoleName()}</span>
                </div>
            </div>
        </div>
    );
};

const styles = {
    topbar: {
        display: 'flex',
        justifyContent: 'space-between',
        alignItems: 'center',
        padding: '16px 32px',
        background: 'white',
        borderBottom: '1px solid #e5e7eb',
        marginBottom: '24px'
    },
    left: {
        flex: 1
    },
    title: {
        margin: 0,
        fontSize: '22px',
        fontWeight: '600',
        color: '#1a1a2e'
    },
    right: {
        display: 'flex',
        alignItems: 'center'
    },
    userInfo: {
        display: 'flex',
        alignItems: 'center',
        gap: '12px'
    },
    username: {
        fontWeight: '500',
        color: '#333'
    },
    role: {
        background: '#f0f2f5',
        padding: '4px 8px',
        borderRadius: '4px',
        fontSize: '12px',
        color: '#666'
    }
};

export default Topbar;
