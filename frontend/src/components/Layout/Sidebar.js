// frontend/src/components/Layout/Sidebar.js
import React from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { getUserRole, logout } from '../../utils/auth';

const Sidebar = () => {
    const navigate = useNavigate();
    const location = useLocation();
    const role = getUserRole();

    const getMenuItems = () => {
        switch (role) {
            case 'admin':
                return [
                    { id: 'users', label: '用户管理', path: '/admin/users' },
                    { id: 'crawler', label: '爬虫管理', path: '/admin/crawler' },
                    { id: 'database', label: '数据库管理', path: '/admin/database' },
                    { id: 'filter', label: '岗位筛选', path: '/admin/filter' },
                    { id: 'charts', label: '数据图表', path: '/admin/charts' },
                    { id: 'profile', label: '个人信息', path: '/admin/profile' }
                ];
            case 'vip':
                return [
                    { id: 'charts', label: '数据图表', path: '/vip/charts' },
                    { id: 'filter', label: '岗位筛选', path: '/vip/filter' },
                    { id: 'favorites', label: '我的收藏', path: '/vip/favorites' },
                    { id: 'history', label: '浏览历史', path: '/vip/history' },
                    { id: 'profile', label: '个人信息', path: '/vip/profile' }
                ];
            case 'guest':
            default:
                return [
                    { id: 'charts', label: '数据图表', path: '/guest/charts' },
                    { id: 'data', label: '数据查看', path: '/guest/data' },
                    { id: 'profile', label: '个人信息', path: '/guest/profile' }
                ];
        }
    };

    const menuItems = getMenuItems();

    const handleLogout = () => {
        logout();
        navigate('/login');
    };

    return (
        <div style={styles.sidebar}>
            <div style={styles.header}>
                <h2 style={styles.logo}>招聘大数据</h2>
                <p style={styles.subtitle}>可视化分析平台</p>
            </div>
            
            <div style={styles.menu}>
                {menuItems.map(item => (
                    <div
                        key={item.id}
                        style={{
                            ...styles.menuItem,
                            ...(location.pathname === item.path ? styles.activeMenuItem : {})
                        }}
                        onClick={() => navigate(item.path)}
                    >
                        <span style={styles.menuIcon}>◆</span>
                        <span>{item.label}</span>
                    </div>
                ))}
            </div>
            
            <div style={styles.footer}>
                <div style={styles.userInfo}>
                    <span style={styles.roleBadge}>
                        {role === 'admin' ? '管理员' : role === 'vip' ? 'VIP' : '访客'}
                    </span>
                </div>
                {role === 'guest' && (
                    <div
                        style={styles.upgradeButton}
                        onClick={() => navigate('/guest/profile')}
                    >
                        ↑ 申请升级VIP
                    </div>
                )}
                <div
                    style={styles.logoutButton}
                    onClick={handleLogout}
                >
                    退出登录
                </div>
            </div>
        </div>
    );
};

const styles = {
    sidebar: {
        width: '220px',
        background: 'linear-gradient(180deg, #1a1a2e 0%, #16213e 100%)',
        color: 'white',
        padding: '20px 0',
        flexShrink: 0,
        position: 'fixed',
        left: 0,
        top: 0,
        height: '100vh',
        overflowY: 'auto',
        zIndex: 100,
        boxShadow: '2px 0 12px rgba(0,0,0,0.15)',
        display: 'flex',
        flexDirection: 'column'
    },
    header: {
        textAlign: 'center',
        padding: '10px 16px 24px',
        borderBottom: '1px solid rgba(255,255,255,0.1)',
        marginBottom: '8px'
    },
    logo: {
        margin: 0,
        fontSize: '18px',
        fontWeight: '600',
        letterSpacing: '2px'
    },
    subtitle: {
        margin: '4px 0 0 0',
        fontSize: '11px',
        color: 'rgba(255,255,255,0.5)',
        letterSpacing: '1px'
    },
    menu: {
        flex: 1,
        padding: '0 0'
    },
    menuItem: {
        padding: '12px 20px',
        cursor: 'pointer',
        color: 'rgba(255,255,255,0.7)',
        transition: 'all 0.25s',
        fontSize: '14px',
        borderLeft: '3px solid transparent',
        display: 'flex',
        alignItems: 'center',
        gap: '10px'
    },
    activeMenuItem: {
        background: 'rgba(64,158,255,0.2)',
        color: 'white',
        borderLeftColor: '#409eff'
    },
    menuIcon: {
        width: '16px',
        textAlign: 'center',
        fontSize: '14px',
        opacity: '0.7'
    },
    footer: {
        padding: '16px',
        borderTop: '1px solid rgba(255,255,255,0.1)'
    },
    userInfo: {
        marginBottom: '10px',
        textAlign: 'center'
    },
    roleBadge: {
        background: 'rgba(64,158,255,0.3)',
        padding: '4px 8px',
        borderRadius: '4px',
        fontSize: '12px'
    },
    upgradeButton: {
        padding: '8px',
        textAlign: 'center',
        cursor: 'pointer',
        color: '#faad14',
        fontSize: '13px',
        borderRadius: '4px',
        transition: 'all 0.25s',
        marginBottom: '4px',
        border: '1px solid rgba(250,173,20,0.3)',
        background: 'rgba(250,173,20,0.1)'
    },
    logoutButton: {
        padding: '8px',
        textAlign: 'center',
        cursor: 'pointer',
        color: 'rgba(255,255,255,0.7)',
        fontSize: '14px',
        borderRadius: '4px',
        transition: 'all 0.25s'
    }
};

export default Sidebar;
