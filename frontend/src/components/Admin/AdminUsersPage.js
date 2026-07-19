// AdminUsersPage.js - 管理员用户管理页面
// 功能：用户列表分页展示、新增用户、删除用户、修改角色、启用/禁用、角色权限管理
import React, { useState, useEffect } from 'react';
import { adminAPI } from '../../utils/api';

const AdminUsersPage = () => {
    // 用户列表状态
    const [users, setUsers] = useState([]);
    const [total, setTotal] = useState(0);
    const [page, setPage] = useState(1);
    const [loading, setLoading] = useState(true);

    // 角色和权限数据（用于弹窗下拉选项和权限勾选）
    const [roles, setRoles] = useState([]);
    const [permissions, setPermissions] = useState([]);

    // 模态框控制状态
    const [showAddModal, setShowAddModal] = useState(false);       // 新增用户弹窗
    const [showRoleModal, setShowRoleModal] = useState(false);      // 修改角色弹窗
    const [showPermModal, setShowPermModal] = useState(false);      // 编辑权限弹窗
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(null); // 删除确认弹窗
    const [showPasswordModal, setShowPasswordModal] = useState(false); // 重置密码弹窗
    const [resetPasswordUser, setResetPasswordUser] = useState(null);   // 正在重置密码的用户
    const [newPassword, setNewPassword] = useState('');                // 新密码
    const [resetPasswordError, setResetPasswordError] = useState(null); // 重置密码错误

    // 表单数据状态
    const [newUser, setNewUser] = useState({ username: '', password: '', email: '', phone: '', role_name: 'guest' });
    const [editingUser, setEditingUser] = useState(null);          // 当前正在编辑角色的用户
    const [selectedRole, setSelectedRole] = useState(null);        // 当前选中的角色
    const [selectedPermissions, setSelectedPermissions] = useState([]); // 当前选中的权限ID列表

    const [error, setError] = useState(null);
    const [success, setSuccess] = useState(null);
    const size = 10; // 每页显示条数

    // 获取用户列表
    const fetchUsers = async () => {
        setLoading(true);
        try {
            const result = await adminAPI.getUsers({ page, size });
            if (result.code === 200) {
                setUsers(result.data.users);
                setTotal(result.data.total);
            }
        } catch (err) {
            setError('获取用户列表失败');
        } finally {
            setLoading(false);
        }
    };

    // 获取角色列表
    const fetchRoles = async () => {
        try {
            const result = await adminAPI.getRoles();
            if (result.code === 200) setRoles(result.data);
        } catch (err) {
            console.error('获取角色失败', err);
        }
    };

    // 获取权限列表
    const fetchPermissions = async () => {
        try {
            const result = await adminAPI.getPermissions();
            if (result.code === 200) setPermissions(result.data);
        } catch (err) {
            console.error('获取权限失败', err);
        }
    };

    // 初始化加载（切换分页时重新拉取用户列表）
    useEffect(() => {
        fetchUsers();
        fetchRoles();
        fetchPermissions();
    }, [page]);

    // 显示成功提示，3秒后自动消失
    const showSuccess = (msg) => {
        setSuccess(msg);
        setTimeout(() => setSuccess(null), 3000);
    };

    // 创建新用户（调用后端 API）
    const handleCreateUser = async () => {
        if (!newUser.username || !newUser.password) {
            setError('用户名和密码不能为空');
            return;
        }
        try {
            const result = await adminAPI.createUser(newUser);
            if (result.code === 200) {
                setShowAddModal(false);
                setNewUser({ username: '', password: '', email: '', phone: '', role_name: 'guest' });
                fetchUsers();
                showSuccess('用户创建成功');
            } else {
                setError(result.msg || '创建失败');
            }
        } catch (err) {
            setError(err.response?.data?.msg || '创建失败');
        }
    };

    // 删除用户（二次确认后执行）
    const handleDeleteUser = async (userId) => {
        try {
            const result = await adminAPI.deleteUser(userId);
            if (result.code === 200) {
                setShowDeleteConfirm(null);
                fetchUsers();
                showSuccess('用户删除成功');
            } else {
                setError(result.msg || '删除失败');
            }
        } catch (err) {
            setError(err.response?.data?.msg || '删除失败');
        }
    };

    // 修改用户角色
    const handleRoleChange = async () => {
        if (!editingUser || !selectedRole) return;
        try {
            const result = await adminAPI.updateUserRole(editingUser.id, { role_name: selectedRole });
            if (result.code === 200) {
                setShowRoleModal(false);
                fetchUsers();
                showSuccess('角色修改成功');
            }
        } catch (err) {
            setError('角色修改失败');
        }
    };

    // 重置用户密码
    const handleResetPassword = async () => {
        if (!resetPasswordUser || !newPassword) {
            setResetPasswordError('请输入新密码');
            return;
        }
        try {
            const result = await adminAPI.resetUserPassword(resetPasswordUser.id, { password: newPassword });
            if (result.code === 200) {
                setShowPasswordModal(false);
                setResetPasswordUser(null);
                setNewPassword('');
                setResetPasswordError(null);
                showSuccess('密码重置成功');
            } else {
                setResetPasswordError(result.msg || '重置失败');
            }
        } catch (err) {
            setResetPasswordError(err.response?.data?.msg || '网络错误');
        }
    };

    // 切换用户启用/禁用状态
    const handleStatusToggle = async (userId, currentStatus) => {
        const newStatus = currentStatus === 'active' ? 'disabled' : 'active';
        try {
            const result = await adminAPI.updateUserStatus(userId, { status: newStatus });
            if (result.code === 200) {
                fetchUsers();
                showSuccess(newStatus === 'active' ? '用户已启用' : '用户已禁用');
            }
        } catch (err) {
            setError('状态更新失败');
        }
    };

    // 打开权限编辑弹窗
    const openPermModal = async (role) => {
        setSelectedRole(role.name);
        try {
            // 初始化时将已选权限全部清空，让用户重新勾选
            setSelectedPermissions([]);
            setShowPermModal(true);
        } catch (err) {
            console.error(err);
        }
    };

    // 保存角色权限
    const handleSavePermissions = async () => {
        const role = roles.find(r => r.name === selectedRole);
        if (!role) return;
        try {
            const result = await adminAPI.updateRolePermissions(role.id, { permission_ids: selectedPermissions });
            if (result.code === 200) {
                setShowPermModal(false);
                fetchRoles();
                showSuccess('权限更新成功');
            }
        } catch (err) {
            setError('权限更新失败');
        }
    };

    const totalPages = Math.ceil(total / size);

    // 角色标签（带颜色）
    const getRoleBadge = (roleName) => {
        const colors = { admin: '#f5222d', vip: '#faad14', guest: '#52c41a' };
        const labels = { admin: '管理员', vip: 'VIP', guest: '访客' };
        return (
            <span style={{ ...styles.badge, background: colors[roleName] || '#d9d9d9' }}>
                {labels[roleName] || roleName}
            </span>
        );
    };

    // 状态标签（带颜色）
    const getStatusBadge = (status) => {
        const colors = { active: '#52c41a', disabled: '#ff4d4f', pending: '#faad14' };
        const labels = { active: '正常', disabled: '已禁用', pending: '待审批' };
        return (
            <span style={{ ...styles.badge, background: colors[status] || '#d9d9d9' }}>
                {labels[status] || status}
            </span>
        );
    };

    return (
        <div style={styles.container}>
            <h2 style={styles.pageTitle}>用户管理</h2>

            {/* 提示信息 */}
            {error && <div style={styles.errorMsg}>{error}<span style={styles.closeBtn} onClick={() => setError(null)}>×</span></div>}
            {success && <div style={styles.successMsg}>{success}</div>}

            {/* 操作栏：新增用户按钮 + 总数统计 */}
            <div style={styles.toolbar}>
                <button style={styles.addBtn} onClick={() => setShowAddModal(true)}>+ 新增用户</button>
                <span style={styles.totalText}>共 {total} 个用户</span>
            </div>

            {/* 用户列表表格 */}
            {loading ? (
                <div style={styles.loading}>加载中...</div>
            ) : (
                <div style={styles.tableCard}>
                    <div style={styles.tableWrapper}>
                        <table style={styles.table}>
                            <thead>
                                <tr>
                                    <th style={styles.th}>ID</th>
                                    <th style={styles.th}>用户名</th>
                                    <th style={styles.th}>邮箱</th>
                                    <th style={styles.th}>密码</th>
                                    <th style={styles.th}>角色</th>
                                    <th style={styles.th}>状态</th>
                                    <th style={styles.th}>创建时间</th>
                                    <th style={styles.th}>操作</th>
                                </tr>
                            </thead>
                            <tbody>
                                {users.map((user, index) => (
                                    <tr key={user.id} style={index % 2 === 0 ? styles.trEven : styles.trOdd}>
                                        <td style={styles.td}>{user.id}</td>
                                        <td style={styles.td}>{user.username}</td>
                                        <td style={styles.td}>{user.email || '-'}</td>
                                        <td style={styles.td}>
                                            <span style={{ fontFamily: 'monospace', fontSize: '13px', color: '#999' }}>已加密</span>
                                        </td>
                                        <td style={styles.td}>{getRoleBadge(user.roles)}</td>
                                        <td style={styles.td}>{getStatusBadge(user.status)}</td>
                                        <td style={styles.td}>{user.created_at ? new Date(user.created_at).toLocaleDateString() : '-'}</td>
                                        <td style={styles.td}>
                                            <div style={styles.actions}>
                                                <button style={styles.roleBtn} onClick={() => { setEditingUser(user); setSelectedRole(user.roles?.split(',')[0] || 'guest'); setShowRoleModal(true); }}>改角色</button>
                                                <button style={styles.passwordBtn} onClick={() => { setResetPasswordUser(user); setNewPassword(''); setResetPasswordError(null); setShowPasswordModal(true); }}>密码</button>
                                                <button style={user.status === 'active' ? styles.disableBtn : styles.enableBtn} onClick={() => handleStatusToggle(user.id, user.status)}>{user.status === 'active' ? '禁用' : '启用'}</button>
                                                <button style={styles.deleteBtn} onClick={() => setShowDeleteConfirm(user)}>删除</button>
                                            </div>
                                        </td>
                                    </tr>
                                ))}
                            </tbody>
                        </table>
                    </div>

                    {/* 分页控件 */}
                    <div style={styles.pagination}>
                        <button style={styles.pageBtn} disabled={page <= 1} onClick={() => setPage(p => p - 1)}>上一页</button>
                        <span style={styles.pageInfo}>第 {page} 页 / 共 {totalPages} 页</span>
                        <button style={styles.pageBtn} disabled={page >= totalPages} onClick={() => setPage(p => p + 1)}>下一页</button>
                    </div>
                </div>
            )}

            {/* 角色权限管理区域 */}
            <div style={styles.sectionCard}>
                <h3 style={styles.sectionTitle}>角色权限管理</h3>
                <div style={styles.roleList}>
                    {roles.map(role => (
                        <div key={role.id} style={styles.roleItem}>
                            <span style={styles.roleName}>{role.name}</span>
                            <span style={styles.roleDesc}>{role.description}</span>
                            <button style={styles.permBtn} onClick={() => openPermModal(role)}>编辑权限</button>
                        </div>
                    ))}
                </div>
            </div>

            {/* 新增用户弹窗 */}
            {showAddModal && (
                <div style={styles.modalOverlay}>
                    <div style={styles.modal}>
                        <h3 style={styles.modalTitle}>新增用户</h3>
                        <div style={styles.formGroup}>
                            <label style={styles.label}>用户名 *</label>
                            <input style={styles.input} value={newUser.username} onChange={e => setNewUser({ ...newUser, username: e.target.value })} />
                        </div>
                        <div style={styles.formGroup}>
                            <label style={styles.label}>密码 *</label>
                            <input style={styles.input} type="password" value={newUser.password} onChange={e => setNewUser({ ...newUser, password: e.target.value })} />
                        </div>
                        <div style={styles.formGroup}>
                            <label style={styles.label}>邮箱</label>
                            <input style={styles.input} value={newUser.email} onChange={e => setNewUser({ ...newUser, email: e.target.value })} />
                        </div>
                        <div style={styles.formGroup}>
                            <label style={styles.label}>手机号</label>
                            <input style={styles.input} value={newUser.phone} onChange={e => setNewUser({ ...newUser, phone: e.target.value })} />
                        </div>
                        <div style={styles.formGroup}>
                            <label style={styles.label}>角色</label>
                            <select style={styles.input} value={newUser.role_name} onChange={e => setNewUser({ ...newUser, role_name: e.target.value })}>
                                {roles.map(r => <option key={r.id} value={r.name}>{r.name}</option>)}
                            </select>
                        </div>
                        <div style={styles.modalFooter}>
                            <button style={styles.cancelBtn} onClick={() => setShowAddModal(false)}>取消</button>
                            <button style={styles.confirmBtn} onClick={handleCreateUser}>确定</button>
                        </div>
                    </div>
                </div>
            )}

            {/* 修改角色弹窗 */}
            {showRoleModal && (
                <div style={styles.modalOverlay}>
                    <div style={styles.modal}>
                        <h3 style={styles.modalTitle}>修改角色 - {editingUser?.username}</h3>
                        <div style={styles.formGroup}>
                            <label style={styles.label}>选择角色</label>
                            <select style={styles.input} value={selectedRole} onChange={e => setSelectedRole(e.target.value)}>
                                {roles.map(r => <option key={r.id} value={r.name}>{r.name} - {r.description}</option>)}
                            </select>
                        </div>
                        <div style={styles.modalFooter}>
                            <button style={styles.cancelBtn} onClick={() => setShowRoleModal(false)}>取消</button>
                            <button style={styles.confirmBtn} onClick={handleRoleChange}>确定</button>
                        </div>
                    </div>
                </div>
            )}

            {/* 权限编辑弹窗（勾选对应角色的所有权限） */}
            {showPermModal && (
                <div style={styles.modalOverlay}>
                    <div style={{ ...styles.modal, maxWidth: '500px' }}>
                        <h3 style={styles.modalTitle}>编辑权限 - {selectedRole}</h3>
                        <div style={styles.permList}>
                            {permissions.map(perm => (
                                <label key={perm.id} style={styles.permItem}>
                                    <input
                                        type="checkbox"
                                        checked={selectedPermissions.includes(perm.id)}
                                        onChange={e => {
                                            if (e.target.checked) {
                                                setSelectedPermissions([...selectedPermissions, perm.id]);
                                            } else {
                                                setSelectedPermissions(selectedPermissions.filter(id => id !== perm.id));
                                            }
                                        }}
                                    />
                                    <span style={styles.permLabel}>{perm.name}</span>
                                    <span style={styles.permDesc}>{perm.description}</span>
                                </label>
                            ))}
                        </div>
                        <div style={styles.modalFooter}>
                            <button style={styles.cancelBtn} onClick={() => setShowPermModal(false)}>取消</button>
                            <button style={styles.confirmBtn} onClick={handleSavePermissions}>保存</button>
                        </div>
                    </div>
                </div>
            )}

            {/* VIP申请管理区域 */}
            <div style={styles.sectionCard}>
                <h3 style={styles.sectionTitle}>VIP申请审批</h3>
                <VipApplications />
            </div>

            {/* 重置密码弹窗 */}
            {showPasswordModal && (
                <div style={styles.modalOverlay}>
                    <div style={styles.modal}>
                        <h3 style={styles.modalTitle}>重置密码 - {resetPasswordUser?.username}</h3>
                        {resetPasswordError && <div style={styles.errorMsg}>{resetPasswordError}<span style={styles.closeBtn} onClick={() => setResetPasswordError(null)}>×</span></div>}
                        <div style={styles.formGroup}>
                            <label style={styles.label}>当前密码（已加密存储，不可查看）</label>
                            <div style={{ padding: '8px 12px', background: '#f5f5f5', borderRadius: '4px', fontSize: '14px', color: '#999' }}>
                                出于安全考虑，密码已加密存储，无法查看明文
                            </div>
                        </div>
                        <div style={styles.formGroup}>
                            <label style={styles.label}>新密码 *</label>
                            <input style={styles.input} type="text" value={newPassword} onChange={e => setNewPassword(e.target.value)} placeholder="8-64位，含大小写字母和数字" />
                        </div>
                        <div style={styles.modalFooter}>
                            <button style={styles.cancelBtn} onClick={() => { setShowPasswordModal(false); setResetPasswordUser(null); setNewPassword(''); setResetPasswordError(null); }}>取消</button>
                            <button style={styles.confirmBtn} onClick={handleResetPassword}>确认重置</button>
                        </div>
                    </div>
                </div>
            )}

            {/* 删除确认弹窗 */}
            {showDeleteConfirm && (
                <div style={styles.modalOverlay}>
                    <div style={styles.modal}>
                        <h3 style={styles.modalTitle}>确认删除</h3>
                        <p style={styles.confirmText}>确定要删除用户 <strong>{showDeleteConfirm.username}</strong> 吗？此操作不可恢复。</p>
                        <div style={styles.modalFooter}>
                            <button style={styles.cancelBtn} onClick={() => setShowDeleteConfirm(null)}>取消</button>
                            <button style={styles.deleteConfirmBtn} onClick={() => handleDeleteUser(showDeleteConfirm.id)}>确认删除</button>
                        </div>
                    </div>
                </div>
            )}
        </div>
    );
};

// VIP申请审批子组件
const VipApplications = () => {
    const [apps, setApps] = useState([]);
    const [loading, setLoading] = useState(true);
    const [msg, setMsg] = useState(null);

    const fetchApps = async () => {
        setLoading(true);
        try {
            const res = await adminAPI.getVipApplications();
            if (res.code === 200) setApps(res.data);
        } catch (err) {
            setMsg('获取申请列表失败');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => { fetchApps(); }, []);

    const handleApprove = async (userId) => {
        try {
            const res = await adminAPI.approveVip(userId);
            if (res.code === 200) {
                setMsg({ type: 'success', text: '审批通过' });
                fetchApps();
            }
        } catch (err) {
            setMsg({ type: 'error', text: '审批失败' });
        }
    };

    const handleReject = async (userId) => {
        try {
            const res = await adminAPI.rejectVip(userId, { remark: '管理员拒绝' });
            if (res.code === 200) {
                setMsg({ type: 'success', text: '已拒绝' });
                fetchApps();
            }
        } catch (err) {
            setMsg({ type: 'error', text: '操作失败' });
        }
    };

    const pending = apps.filter(a => a.status === 'pending');

    return (
        <div>
            {msg && (
                <div style={{
                    ...styles.errorMsg,
                    background: msg.type === 'success' ? '#f6ffed' : '#fff2f0',
                    color: msg.type === 'success' ? '#52c41a' : '#ff4d4f'
                }}>{msg.text}<span style={styles.closeBtn} onClick={() => setMsg(null)}>×</span></div>
            )}
            {loading ? (
                <div style={styles.loading}>加载中...</div>
            ) : pending.length === 0 ? (
                <p style={{ color: '#999', fontSize: '14px' }}>暂无待审批的VIP申请</p>
            ) : (
                <div style={styles.tableWrapper}>
                    <table style={styles.table}>
                        <thead>
                            <tr>
                                <th style={styles.th}>申请人</th>
                                <th style={styles.th}>邮箱</th>
                                <th style={styles.th}>申请时间</th>
                                <th style={styles.th}>操作</th>
                            </tr>
                        </thead>
                        <tbody>
                            {pending.map((app, i) => (
                                <tr key={app.id} style={i % 2 === 0 ? styles.trEven : styles.trOdd}>
                                    <td style={styles.td}>{app.username}</td>
                                    <td style={styles.td}>{app.email || '-'}</td>
                                    <td style={styles.td}>{new Date(app.created_at).toLocaleString()}</td>
                                    <td style={styles.td}>
                                        <div style={styles.actions}>
                                            <button style={{ ...styles.roleBtn, background: '#f6ffed', color: '#52c41a', border: '1px solid #b7eb8f' }} onClick={() => handleApprove(app.user_id)}>批准</button>
                                            <button style={{ ...styles.roleBtn, background: '#fff2f0', color: '#ff4d4f', border: '1px solid #ffccc7' }} onClick={() => handleReject(app.user_id)}>拒绝</button>
                                        </div>
                                    </td>
                                </tr>
                            ))}
                        </tbody>
                    </table>
                </div>
            )}
        </div>
    );
};

const styles = {
    container: { padding: '20px' },
    pageTitle: { fontSize: '24px', fontWeight: 'bold', marginBottom: '24px', color: '#262626' },
    loading: { textAlign: 'center', padding: '50px', fontSize: '16px', color: '#999' },
    errorMsg: { background: '#fff2f0', border: '1px solid #ffccc7', color: '#ff4d4f', padding: '10px 16px', borderRadius: '6px', marginBottom: '16px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' },
    successMsg: { background: '#f6ffed', border: '1px solid #b7eb8f', color: '#52c41a', padding: '10px 16px', borderRadius: '6px', marginBottom: '16px' },
    closeBtn: { cursor: 'pointer', fontSize: '18px', fontWeight: 'bold' },
    toolbar: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' },
    addBtn: { padding: '8px 20px', background: '#1890ff', color: '#fff', border: 'none', borderRadius: '6px', cursor: 'pointer', fontSize: '14px', fontWeight: '500' },
    totalText: { color: '#666', fontSize: '14px' },
    tableCard: { background: '#fff', borderRadius: '8px', boxShadow: '0 2px 8px rgba(0,0,0,0.1)' },
    tableWrapper: { overflowX: 'auto' },
    table: { width: '100%', borderCollapse: 'collapse' },
    th: { padding: '12px 16px', textAlign: 'left', fontWeight: '600', color: '#262626', borderBottom: '2px solid #f0f0f0', whiteSpace: 'nowrap', background: '#fafafa' },
    td: { padding: '12px 16px', borderBottom: '1px solid #f0f0f0', color: '#595959' },
    trEven: { background: '#fafafa' },
    trOdd: { background: '#fff' },
    actions: { display: 'flex', gap: '8px' },
    roleBtn: { padding: '4px 12px', background: '#e6f7ff', color: '#1890ff', border: '1px solid #91d5ff', borderRadius: '4px', cursor: 'pointer', fontSize: '12px' },
    passwordBtn: { padding: '4px 12px', background: '#f0f5ff', color: '#2f54eb', border: '1px solid #adc6ff', borderRadius: '4px', cursor: 'pointer', fontSize: '12px' },
    disableBtn: { padding: '4px 12px', background: '#fff7e6', color: '#fa8c16', border: '1px solid #ffd591', borderRadius: '4px', cursor: 'pointer', fontSize: '12px' },
    enableBtn: { padding: '4px 12px', background: '#f6ffed', color: '#52c41a', border: '1px solid #b7eb8f', borderRadius: '4px', cursor: 'pointer', fontSize: '12px' },
    deleteBtn: { padding: '4px 12px', background: '#fff2f0', color: '#ff4d4f', border: '1px solid #ffccc7', borderRadius: '4px', cursor: 'pointer', fontSize: '12px' },
    badge: { display: 'inline-block', padding: '2px 8px', borderRadius: '10px', color: '#fff', fontSize: '12px', fontWeight: '500' },
    pagination: { display: 'flex', justifyContent: 'center', alignItems: 'center', gap: '16px', padding: '16px' },
    pageBtn: { padding: '6px 14px', border: '1px solid #d9d9d9', borderRadius: '4px', background: '#fff', cursor: 'pointer', fontSize: '13px' },
    pageInfo: { fontSize: '13px', color: '#666' },
    sectionCard: { background: '#fff', borderRadius: '8px', boxShadow: '0 2px 8px rgba(0,0,0,0.1)', marginTop: '20px', padding: '20px' },
    sectionTitle: { fontSize: '16px', fontWeight: '600', marginBottom: '16px', color: '#262626' },
    roleList: { display: 'flex', flexDirection: 'column', gap: '12px' },
    roleItem: { display: 'flex', alignItems: 'center', gap: '12px', padding: '12px', background: '#fafafa', borderRadius: '6px' },
    roleName: { fontWeight: '600', color: '#262626', minWidth: '60px' },
    roleDesc: { color: '#666', flex: 1, fontSize: '13px' },
    permBtn: { padding: '4px 12px', background: '#f0f0f0', color: '#333', border: '1px solid #d9d9d9', borderRadius: '4px', cursor: 'pointer', fontSize: '12px' },
    modalOverlay: { position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, background: 'rgba(0,0,0,0.5)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000 },
    modal: { background: '#fff', borderRadius: '8px', padding: '24px', width: '400px', maxWidth: '90vw', maxHeight: '80vh', overflow: 'auto' },
    modalTitle: { fontSize: '18px', fontWeight: '600', marginBottom: '20px', color: '#262626' },
    formGroup: { marginBottom: '16px' },
    label: { display: 'block', marginBottom: '6px', fontSize: '14px', color: '#333', fontWeight: '500' },
    input: { width: '100%', padding: '8px 12px', border: '1px solid #d9d9d9', borderRadius: '4px', fontSize: '14px', boxSizing: 'border-box' },
    modalFooter: { display: 'flex', justifyContent: 'flex-end', gap: '10px', marginTop: '20px' },
    cancelBtn: { padding: '8px 16px', background: '#fff', color: '#666', border: '1px solid #d9d9d9', borderRadius: '4px', cursor: 'pointer', fontSize: '14px' },
    confirmBtn: { padding: '8px 16px', background: '#1890ff', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '14px' },
    deleteConfirmBtn: { padding: '8px 16px', background: '#ff4d4f', color: '#fff', border: 'none', borderRadius: '4px', cursor: 'pointer', fontSize: '14px' },
    confirmText: { fontSize: '14px', color: '#666', lineHeight: '1.6' },
    permList: { display: 'flex', flexDirection: 'column', gap: '10px', maxHeight: '300px', overflow: 'auto' },
    permItem: { display: 'flex', alignItems: 'center', gap: '10px', padding: '8px', background: '#fafafa', borderRadius: '4px', cursor: 'pointer' },
    permLabel: { fontWeight: '500', color: '#262626', minWidth: '120px' },
    permDesc: { color: '#999', fontSize: '12px' }
};

export default AdminUsersPage;
