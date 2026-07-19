// auth.js - 用户认证状态管理
// 使用 sessionStorage 存储 token 和用户信息，每个标签页独立隔离
// 注：sessionStorage 会在关闭标签页时自动清除

// 存储令牌
export const setToken = (token) => {
    sessionStorage.setItem('token', token);
};

// 获取令牌
export const getToken = () => {
    return sessionStorage.getItem('token');
};

// 移除令牌
export const removeToken = () => {
    sessionStorage.removeItem('token');
};

// 存储用户信息
export const setUser = (user) => {
    sessionStorage.setItem('user', JSON.stringify(user));
};

// 获取用户信息
export const getUser = () => {
    const user = sessionStorage.getItem('user');
    return user ? JSON.parse(user) : null;
};

// 移除用户信息
export const removeUser = () => {
    sessionStorage.removeItem('user');
};

// 检查是否已登录（仅判断 token 是否存在，不验证有效性）
export const isAuthenticated = () => {
    const token = getToken();
    return !!token;
};

// 获取用户角色
export const getUserRole = () => {
    const user = getUser();
    return user ? user.role : null;
};

// 退出登录（清除所有本地会话数据）
export const logout = () => {
    removeToken();
    removeUser();
};
