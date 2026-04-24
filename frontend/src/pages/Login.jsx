import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { authApi } from '../api/client'
import { Divider } from '../components/Ornaments'
import { setUser } from '../hooks/useUser'

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

      localStorage.setItem('token', result.token)
      setUser({
        user_id: result.user_id,
        id: result.user_id,
        username: result.username,
        displayName: result.display_name,
        display_name: result.display_name,
      })

      navigate('/')
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'grid', placeItems: 'center',
      padding: 24,
      position: 'relative', zIndex: 1,
    }}>
      {/* 局部装饰符文环（除背景层外的额外点缀） */}
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none', opacity: .18 }}>
        <div className="rune-ring" style={{ position: 'absolute', top: '10%', left: '-60px', width: 240, height: 240 }} />
        <div className="rune-ring" style={{ position: 'absolute', bottom: '-80px', right: '5%', width: 320, height: 320, animationDuration: '90s' }} />
      </div>

      <div className="panel-ornate" style={{
        padding: '42px 48px',
        width: 420, maxWidth: '92vw',
        position: 'relative', textAlign: 'center',
      }}>
        <div style={{ fontSize: 48, marginBottom: 8 }}>⚜</div>
        <div className="display-title" style={{ fontSize: 26, letterSpacing: '.15em' }}>龙与编年史</div>
        <div className="eyebrow" style={{ marginTop: 8 }}>✦ AI 地下城 · D&D 5e ✦</div>
        <div style={{
          fontFamily: 'var(--font-script)', fontStyle: 'italic',
          fontSize: 13, color: 'var(--parchment-dark)',
          margin: '14px 0 22px', lineHeight: 1.8,
        }}>
          "推开厚重的橡木门，<br />你的传奇将由此开启..."
        </div>

        <Divider>❧</Divider>

        <form onSubmit={handleSubmit} style={{ display: 'flex', flexDirection: 'column', gap: 12, marginTop: 18 }}>
          <input
            className="input-fantasy"
            type="text"
            placeholder="英雄之名"
            value={username}
            onChange={e => setUsername(e.target.value)}
            autoFocus
            autoComplete="username"
          />
          <input
            className="input-fantasy"
            type="password"
            placeholder="秘语密印"
            value={password}
            onChange={e => setPassword(e.target.value)}
            autoComplete={isRegister ? 'new-password' : 'current-password'}
          />
          {isRegister && (
            <input
              className="input-fantasy"
              type="text"
              placeholder="显示名称（可选）"
              value={displayName}
              onChange={e => setDisplayName(e.target.value)}
            />
          )}

          {error && (
            <div style={{
              fontSize: 12, color: '#ffaaaa',
              padding: '8px 10px',
              background: 'rgba(139,32,32,0.25)',
              border: '1px solid var(--blood)',
              borderRadius: 6,
              fontFamily: 'var(--font-mono)',
            }}>
              {error}
            </div>
          )}

          <button
            type="submit"
            className="btn-gold"
            disabled={loading}
            style={{ padding: '14px', marginTop: 6, fontSize: 14, letterSpacing: '.2em' }}
          >
            {loading ? '✦ 启动符文中… ✦' : isRegister ? '✦ 创建英雄档案 ✦' : '✦ 进入传说 ✦'}
          </button>

          <button
            type="button"
            className="btn-ghost"
            onClick={() => { setIsRegister(!isRegister); setError('') }}
          >
            {isRegister ? '已有英雄档案？点击登录' : '创建新的英雄档案'}
          </button>
        </form>

        <p style={{
          textAlign: 'center', marginTop: 18,
          fontSize: 11, color: 'var(--parchment-dark)', opacity: .55,
          fontFamily: 'var(--font-mono)',
        }}>
          测试账号：test / 123456
        </p>
      </div>
    </div>
  )
}
