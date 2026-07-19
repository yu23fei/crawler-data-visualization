import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { authAPI } from '../../utils/api';
import { setToken, setUser } from '../../utils/auth';

const Login = () => {
    const [form, setForm] = useState({ username: '', password: '' })
    const [errors, setErrors] = useState({})
    const [touched, setTouched] = useState({})
    const [serverError, setServerError] = useState('')
    const [loading, setLoading] = useState(false)
    const navigate = useNavigate()

    const validate = (name, value) => {
        if (name === 'username') {
            if (!value) return '请输入用户名'
            if (value.length < 3 || value.length > 30) return '用户名需3-30个字符'
            return ''
        }
        if (name === 'password') {
            if (!value) return '请输入密码'
            return ''
        }
        return ''
    }

    const handleChange = (e) => {
        const { name, value } = e.target
        setForm(prev => ({ ...prev, [name]: value }))
        if (touched[name]) {
            setErrors(prev => ({ ...prev, [name]: validate(name, value) }))
        }
    }

    const handleBlur = (e) => {
        const { name, value } = e.target
        setTouched(prev => ({ ...prev, [name]: true }))
        setErrors(prev => ({ ...prev, [name]: validate(name, value) }))
    }

    const handleSubmit = async (e) => {
        e.preventDefault()
        setServerError('')

        const newTouched = { username: true, password: true }
        const newErrors = {
            username: validate('username', form.username),
            password: validate('password', form.password)
        }
        setTouched(newTouched)
        setErrors(newErrors)
        if (newErrors.username || newErrors.password) return

        setLoading(true)
        try {
            const res = await authAPI.login(form)
            if (res.code === 200) {
                setToken(res.data.token)
                setUser({ ...res.data.user, role: res.data.role })
                const role = res.data.role
                if (role === 'admin') navigate('/admin/users')
                else if (role === 'vip') navigate('/vip/charts')
                else navigate('/guest/charts')
            } else {
                setServerError(res.msg || '登录失败')
            }
        } catch (err) {
            setServerError(err.response?.data?.msg || '网络错误，请稍后重试')
        } finally {
            setLoading(false)
        }
    }

    return (
        <div style={styles.container}>
            <div style={styles.card}>
                <h2 style={styles.title}>登录</h2>
                <p style={styles.subtitle}>招聘大数据可视化分析平台</p>
                {serverError && <div style={styles.error}>{serverError}</div>}
                <form onSubmit={handleSubmit} style={styles.form}>
                    <div style={styles.inputGroup}>
                        <label style={styles.label}>用户名 *</label>
                        <input type="text" name="username" value={form.username}
                            onChange={handleChange} onBlur={handleBlur}
                            style={{ ...styles.input, borderColor: touched.username && errors.username ? '#ff4d4f' : touched.username && !errors.username && form.username ? '#52c41a' : '#ddd' }}
                        />
                        {touched.username && errors.username && <span style={styles.fieldError}>{errors.username}</span>}
                    </div>
                    <div style={styles.inputGroup}>
                        <label style={styles.label}>密码 *</label>
                        <input type="password" name="password" value={form.password}
                            onChange={handleChange} onBlur={handleBlur}
                            style={{ ...styles.input, borderColor: touched.password && errors.password ? '#ff4d4f' : touched.password && !errors.password && form.password ? '#52c41a' : '#ddd' }}
                        />
                        {touched.password && errors.password && <span style={styles.fieldError}>{errors.password}</span>}
                    </div>
                    <button type="submit" style={styles.button} disabled={loading}>
                        {loading ? '登录中...' : '登录'}
                    </button>
                </form>
                <div style={styles.links}>
                    <Link to="/register" style={styles.link}>注册账号</Link>
                    <Link to="/reset-password" style={styles.link}>忘记密码</Link>
                </div>
            </div>
        </div>
    )
}

const styles = {
    container: { minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', padding: '20px' },
    card: { background: 'white', borderRadius: '10px', padding: '40px', width: '100%', maxWidth: '400px', boxShadow: '0 10px 40px rgba(0,0,0,0.2)' },
    title: { margin: '0 0 10px 0', fontSize: '24px', fontWeight: 'bold', color: '#333', textAlign: 'center' },
    subtitle: { margin: '0 0 30px 0', fontSize: '14px', color: '#666', textAlign: 'center' },
    error: { background: '#fee2e2', color: '#dc2626', padding: '10px', borderRadius: '5px', marginBottom: '20px', fontSize: '14px' },
    form: { display: 'flex', flexDirection: 'column' },
    inputGroup: { marginBottom: '15px' },
    label: { display: 'block', marginBottom: '5px', fontSize: '14px', fontWeight: '500', color: '#333' },
    input: { width: '100%', padding: '10px', border: '1px solid #ddd', borderRadius: '5px', fontSize: '14px', boxSizing: 'border-box', outline: 'none', transition: 'border-color 0.2s' },
    fieldError: { color: '#ff4d4f', fontSize: '12px', marginTop: '4px', display: 'block' },
    button: { background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', color: 'white', border: 'none', padding: '12px', borderRadius: '5px', fontSize: '16px', fontWeight: '500', cursor: 'pointer', marginTop: '10px' },
    links: { display: 'flex', justifyContent: 'space-between', marginTop: '20px' },
    link: { color: '#667eea', textDecoration: 'none', fontSize: '14px' }
}

export default Login
