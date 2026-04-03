import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authApi } from '../api/client'
import { SwordIcon } from '../components/Icons'

export default function Login() {
  const navigate = useNavigate()
  const [isRegister, setIsRegister] = useState(false)
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [displayName, setDisplayName] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!username.trim() || !password.trim()) { setError('请填写用户名和密码'); return }
    setError(''); setLoading(true)

    try {
      const result = isRegister
        ? await authApi.register(username.trim(), password, displayName.trim() || username.trim())
        : await authApi.login(username.trim(), password)

      // 存储 token 和用户信息
      localStorage.setItem('token', result.token)
      localStorage.setItem('user', JSON.stringify({
        id: result.user_id,
        username: result.username,
        displayName: result.display_name,
      }))

      navigate('/')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh', display: 'flex', alignItems: 'center', justifyContent: 'center',
      background: 'var(--bg)', padding: 20,
    }}>
      <div style={{ width: '100%', maxWidth: 400 }}>
        {/* 标题 */}
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <h1 style={{
            fontSize: '2.5rem', fontWeight: 900, color: 'var(--gold)',
            textShadow: '0 2px 8px rgba(201,168,76,0.3)', letterSpacing: '0.15em',
            fontFamily: 'Georgia, "Noto Serif SC", serif',
          }}>
            <SwordIcon size={32} color="var(--gold)" style={{ display: 'inline', verticalAlign: 'middle', marginRight: 8 }} />
            AI 跑团
          </h1>
          <p style={{ fontSize: 13, color: 'var(--text-dim)', marginTop: 6 }}>
            DnD 5e · AI地下城主 · 单人冒险
          </p>
        </div>

        {/* 表单卡片 */}
        <div className="panel" style={{ padding: 28 }}>
          <h2 style={{ color: 'var(--gold)', fontSize: 18, fontWeight: 700, margin: '0 0 20px', textAlign: 'center' }}>
            {isRegister ? '创建账号' : '登录'}
          </h2>

          <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
            <div>
              <label style={{ display: 'block', fontSize: 12, color: 'var(--parchment-dark)', marginBottom: 4 }}>用户名</label>
              <input className="input-fantasy" type="text" value={username}
                onChange={e => setUsername(e.target.value)}
                placeholder="输入用户名" autoFocus autoComplete="username" />
            </div>

            <div>
              <label style={{ display: 'block', fontSize: 12, color: 'var(--parchment-dark)', marginBottom: 4 }}>密码</label>
              <input className="input-fantasy" type="password" value={password}
                onChange={e => setPassword(e.target.value)}
                placeholder="输入密码" autoComplete={isRegister ? "new-password" : "current-password"} />
            </div>

            {isRegister && (
              <div>
                <label style={{ display: 'block', fontSize: 12, color: 'var(--parchment-dark)', marginBottom: 4 }}>显示名称（可选）</label>
                <input className="input-fantasy" type="text" value={displayName}
                  onChange={e => setDisplayName(e.target.value)}
                  placeholder="你在游戏中的名字" />
              </div>
            )}

            {error && (
              <p style={{ color: 'var(--red-light)', fontSize: 13, margin: 0, padding: '6px 10px',
                background: 'rgba(139,32,32,0.15)', borderRadius: 6, border: '1px solid var(--red)' }}>
                {error}
              </p>
            )}

            <button type="submit" className="btn-gold" disabled={loading}
              style={{ padding: '10px', fontSize: 15, marginTop: 4 }}>
              {loading ? '处理中...' : isRegister ? '注册' : '登录'}
            </button>
          </form>

          {/* 切换登录/注册 */}
          <div style={{ textAlign: 'center', marginTop: 16 }}>
            <button onClick={() => { setIsRegister(!isRegister); setError('') }}
              style={{
                background: 'none', border: 'none', color: 'var(--gold-dim)',
                cursor: 'pointer', fontSize: 13, fontFamily: 'inherit',
                textDecoration: 'underline',
              }}>
              {isRegister ? '已有账号？点击登录' : '没有账号？点击注册'}
            </button>
          </div>
        </div>

        {/* 测试账号提示 */}
        <p style={{ textAlign: 'center', marginTop: 16, fontSize: 11, color: 'var(--text-dim)', opacity: 0.6 }}>
          测试账号：test / 123456
        </p>
      </div>
    </div>
  )
}
