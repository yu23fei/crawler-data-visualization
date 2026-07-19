import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { authAPI } from '../../utils/api';

const ResetPassword = () => {
    const [form, setForm] = useState({ username: '', security_answer: '', new_password: '', confirm_password: '' })
    const [errors, setErrors] = useState({})
    const [touched, setTouched] = useState({})
    const [serverError, setServerError] = useState('')
    const [success, setSuccess] = useState('')
    const [loading, setLoading] = useState(false)
    const navigate = useNavigate()

    const validate = (name, value) => {
        if (name === 'username') {
            if (!value) return '请输入用户名'
            if (value.length < 3 || value.length > 30) return '用户名需3-30个字符'
            return ''
        }
        if (name === 'security_answer') {
            if (!value) return '请输入安全答案'
            if (value.length < 2 || value.length > 200) return '安全答案需2-200个字符'
            return ''
        }
        if (name === 'new_password') {
            if (!value) return '请输入新密码'
            if (value.length < 6 || value.length > 50) return '密码需6-50个字符'
            return ''
        }
        if (name === 'confirm_password') {
            if (!value) return '请确认密码'
            if (value !== form.new_password) return '两次密码不一致'
            return ''
        }
        return ''
    }

    const handleChange = (e) => {
        const { name, value } = e.target
        const newForm = { ...form, [name]: value }
        setForm(newForm)
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
        setSuccess('')

        const newTouched = {}
        const newErrors = {}
        for (const key of ['username', 'security_answer', 'new_password', 'confirm_password']) {
            newTouched[key] = true
            const err = validate(key, form[key])
            if (err) newErrors[key] = err
        }
        setTouched(newTouched)
        setErrors(newErrors)
        if (Object.keys(newErrors).length > 0) return

        setLoading(true)
        try {
            const res = await authAPI.resetPassword({
                username: form.username,
                security_answer: form.security_answer,
                new_password: form.new_password
            })
            if (res.code === 200) {
                setSuccess('密码重置成功！请使用新密码登录。')
                setTimeout(() => navigate('/login'), 3000)
            } else {
                setServerError(res.msg || '密码重置失败')
            }
        } catch (err) {
            setServerError(err.response?.data?.msg || '网络错误，请稍后重试')
        } finally {
            setLoading(false)
        }
    }

    const fields = [
        { name: 'username', label: '用户名', type: 'text', required: true },
        { name: 'security_answer', label: '安全答案', type: 'text', required: true },
        { name: 'new_password', label: '新密码', type: 'password', required: true },
        { name: 'confirm_password', label: '确认新密码', type: 'password', required: true },
    ]

    return (
        <div style={styles.container}>
            <div style={styles.card}>
                <h2 style={styles.title}>重置密码</h2>
                <p style={styles.subtitle}>通过安全问题重置密码</p>
                {serverError && <div style={styles.error}>{serverError}</div>}
                {success && <div style={styles.success}>{success}</div>}
                <form onSubmit={handleSubmit} style={styles.form}>
                    {fields.map(f => (
                        <div key={f.name} style={styles.inputGroup}>
                            <label style={styles.label}>{f.label} *</label>
                            <input type={f.type} name={f.name} value={form[f.name]}
                                onChange={handleChange} onBlur={handleBlur}
                                style={{
                                    ...styles.input,
                                    borderColor: touched[f.name] && errors[f.name] ? '#ff4d4f' : touched[f.name] && !errors[f.name] && form[f.name] ? '#52c41a' : '#ddd'
                                }}
                            />
                            {touched[f.name] && errors[f.name] && <span style={styles.fieldError}>{errors[f.name]}</span>}
                        </div>
                    ))}
                    <button type="submit" style={styles.button} disabled={loading}>
                        {loading ? '重置中...' : '重置密码'}
                    </button>
                </form>
                <div style={styles.links}>
                    <Link to="/login" style={styles.link}>返回登录</Link>
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
    success: { background: '#d1fae5', color: '#059669', padding: '10px', borderRadius: '5px', marginBottom: '20px', fontSize: '14px' },
    form: { display: 'flex', flexDirection: 'column' },
    inputGroup: { marginBottom: '15px' },
    label: { display: 'block', marginBottom: '5px', fontSize: '14px', fontWeight: '500', color: '#333' },
    input: { width: '100%', padding: '10px', border: '1px solid #ddd', borderRadius: '5px', fontSize: '14px', boxSizing: 'border-box', outline: 'none', transition: 'border-color 0.2s' },
    fieldError: { color: '#ff4d4f', fontSize: '12px', marginTop: '4px', display: 'block' },
    button: { background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', color: 'white', border: 'none', padding: '12px', borderRadius: '5px', fontSize: '16px', fontWeight: '500', cursor: 'pointer', marginTop: '10px' },
    links: { marginTop: '20px', textAlign: 'center' },
    link: { color: '#667eea', textDecoration: 'none', fontSize: '14px' }
}

export default ResetPassword
