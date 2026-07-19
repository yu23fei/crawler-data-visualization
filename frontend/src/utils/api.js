// api.js - 前后端 API 通信模块
// 封装 axios 实例，统一管理请求拦截（注入 token）和响应拦截（401 自动登出）
import axios from 'axios';
import { getToken, logout } from './auth';

// 创建 axios 实例，使用相对路径（与前端同源，无需指定端口）
const api = axios.create({
    baseURL: '',
    timeout: 10000,
    headers: {
        'Content-Type': 'application/json'
    }
});

// 请求拦截器：自动从 sessionStorage 读取 token 并注入 Authorization 请求头
api.interceptors.request.use(
    (config) => {
        const token = getToken();
        if (token) {
            config.headers.Authorization = `Bearer ${token}`;
        }
        return config;
    },
    (error) => {
        return Promise.reject(error);
    }
);

// 响应拦截器：自动解包 response.data，401 时清除本地会话并跳转登录页
api.interceptors.response.use(
    (response) => {
        return response.data;
    },
    (error) => {
        if (error.response) {
            if (error.response.status === 401) {
                logout();
                window.location.href = '/login';
            }
        }
        return Promise.reject(error);
    }
);

// 认证相关 API（登录、注册、重置密码、获取个人信息、VIP申请）
export const authAPI = {
    login: (data) => api.post('/api/auth/login', data),
    register: (data) => api.post('/api/auth/register', data),
    resetPassword: (data) => api.post('/api/auth/reset-password', data),
    getProfile: () => api.get('/api/auth/profile'),
    applyVip: () => api.post('/api/auth/apply-vip')
};

// 管理员相关 API（用户 CRUD、角色权限管理、VIP审批）
export const adminAPI = {
    getUsers: (params) => api.get('/api/admin/users', { params }),
    createUser: (data) => api.post('/api/admin/users', data),
    deleteUser: (userId) => api.delete(`/api/admin/users/${userId}`),
    updateUserRole: (userId, data) => api.put(`/api/admin/users/${userId}/role`, data),
    updateUserStatus: (userId, data) => api.put(`/api/admin/users/${userId}/status`, data),
    resetUserPassword: (userId, data) => api.put(`/api/admin/users/${userId}/password`, data),
    getUserLogs: (params) => api.get('/api/admin/users/logs', { params }),
    getRoles: () => api.get('/api/admin/roles'),
    getPermissions: () => api.get('/api/admin/permissions'),
    updateRolePermissions: (roleId, data) => api.put(`/api/admin/roles/${roleId}/permissions`, data),
    getVipApplications: () => api.get('/api/admin/vip-applications'),
    approveVip: (userId) => api.put(`/api/admin/vip-applications/${userId}/approve`),
    rejectVip: (userId, data) => api.put(`/api/admin/vip-applications/${userId}/reject`, data)
};

// 数据分析相关 API（聚合分析、分页查询、多条件筛选）
export const dataAPI = {
    getAnalysis: () => api.get('/api/v2/analysis'),
    getJobPage: (params) => api.get('/api/job/page', { params }),
    filterJobs: (params) => api.get('/api/job/filter', { params })
};

// 爬虫管理 API（前程无忧 + 智联招聘，独立控制）
export const crawlerAPI = {
    start: (source) => api.post(`/api/admin/crawler/${source}/start`),
    stop: (source) => api.post(`/api/admin/crawler/${source}/stop`),
    getStatus: (source) => api.get(`/api/admin/crawler/${source}/status`),
    getAllStatus: () => api.get('/api/admin/crawler/status'),
    getRecentJobs: (params) => api.get('/api/admin/recent-jobs', { params })
};

// 数据库管理 API（表列表、表数据查看、记录增删改）
export const databaseAPI = {
    getTables: () => api.get('/api/admin/database/tables'),
    getTableData: (tableName, params) => api.get(`/api/admin/database/table/${tableName}`, { params }),
    addRecord: (data) => api.post('/api/admin/database/record', data),
    updateRecord: (data) => api.put('/api/admin/database/record', data),
    deleteRecord: (recordId, tableName) => api.delete(`/api/admin/database/record/${recordId}`, { params: { table: tableName } })
};

export default api;
