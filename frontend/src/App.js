// App.js - 应用根组件
// 定义路由结构：公开路由 + 角色路由（guest/vip/admin），路由守卫基于 sessionStorage 的角色信息
import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import Login from './components/Auth/Login';
import Register from './components/Auth/Register';
import ResetPassword from './components/Auth/ResetPassword';
import Layout from './components/Layout/Layout';
import ChartsPage from './components/Charts/ChartsPage';
import DataPage from './components/Data/DataPage';
import FilterPage from './components/Filter/FilterPage';
import AdminUsersPage from './components/Admin/AdminUsersPage';
import CrawlerPage from './components/Admin/CrawlerPage';
import DatabasePage from './components/Admin/DatabasePage';
import ProfilePage from './components/Auth/ProfilePage';
import JobDetailPage from './components/JobDetailPage';
import FavoritesPage from './components/FavoritesPage';
import HistoryPage from './components/HistoryPage';
import { isAuthenticated, getUserRole } from './utils/auth';

// 路由守卫组件
// 检查是否登录 + 角色是否匹配，否则重定向到登录页或未授权页
const PrivateRoute = ({ children, allowedRoles }) => {
    if (!isAuthenticated()) {
        return <Navigate to="/login" replace />;
    }
    
    const userRole = getUserRole();
    if (allowedRoles && !allowedRoles.includes(userRole)) {
        return <Navigate to="/unauthorized" replace />;
    }
    
    return children;
};

// 未授权页面
const Unauthorized = () => (
    <div style={{ textAlign: 'center', padding: '50px' }}>
        <h1>403 - 权限不足</h1>
        <p>您没有权限访问此页面</p>
        <button onClick={() => window.history.back()}>返回上一页</button>
    </div>
);

function App() {
    return (
        <Router>
            <Routes>
                {/* ===== 公开路由（无需登录） ===== */}
                <Route path="/login" element={<Login />} />
                <Route path="/register" element={<Register />} />
                <Route path="/reset-password" element={<ResetPassword />} />
                <Route path="/unauthorized" element={<Unauthorized />} />
                
                {/* ===== 访客路由（仅 guest 角色可访问） ===== */}
                <Route
                    path="/guest"
                    element={
                        <PrivateRoute allowedRoles={['guest']}>
                            <Layout />
                        </PrivateRoute>
                    }
                >
                    <Route index element={<Navigate to="charts" replace />} />
                    <Route path="charts" element={<ChartsPage />} />
                    <Route path="data" element={<DataPage />} />
                    <Route path="job-detail" element={<JobDetailPage />} />
                    <Route path="profile" element={<ProfilePage />} />
                </Route>
                
                {/* ===== VIP 路由（仅 vip 角色可访问） ===== */}
                <Route
                    path="/vip"
                    element={
                        <PrivateRoute allowedRoles={['vip']}>
                            <Layout />
                        </PrivateRoute>
                    }
                >
                    <Route path="charts" element={<ChartsPage />} />
                    <Route path="filter" element={<FilterPage />} />
                    <Route path="profile" element={<ProfilePage />} />
                    <Route path="favorites" element={<FavoritesPage />} />
                    <Route path="history" element={<HistoryPage />} />
                    <Route path="job-detail" element={<JobDetailPage />} />
                </Route>
                
                {/* ===== 管理员路由（仅 admin 角色可访问） ===== */}
                <Route
                    path="/admin"
                    element={
                        <PrivateRoute allowedRoles={['admin']}>
                            <Layout />
                        </PrivateRoute>
                    }
                >
                    <Route path="users" element={<AdminUsersPage />} />
                    <Route path="crawler" element={<CrawlerPage />} />
                    <Route path="database" element={<DatabasePage />} />
                    <Route path="filter" element={<FilterPage />} />
                    <Route path="charts" element={<ChartsPage />} />
                    <Route path="profile" element={<ProfilePage />} />
                    <Route path="job-detail" element={<JobDetailPage />} />
                </Route>
                
                {/* ===== 默认路由（未匹配时跳转登录） ===== */}
                <Route path="/" element={<Navigate to="/login" replace />} />
                <Route path="*" element={<Navigate to="/login" replace />} />
            </Routes>
        </Router>
    );
}

export default App;
