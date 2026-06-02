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
    <div className="login-page">
      {/* 局部装饰符文环（除背景层外的额外点缀） */}
      <div className="login-runes">
        <div className="rune-ring login-rune login-rune-left" />
        <div className="rune-ring login-rune login-rune-right" />
      </div>

      <div className="panel-ornate login-card">
        <div className="login-mark">⚜</div>
        <div className="display-title login-title">龙与编年史</div>
        <div className="eyebrow login-eyebrow">✦ AI 地下城 · D&D 5e ✦</div>
        <div className="login-copy">
          "推开厚重的橡木门，<br />你的传奇将由此开启..."
        </div>

        <Divider>❧</Divider>

        <form onSubmit={handleSubmit} className="login-form">
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
            <div className="login-error">
              {error}
            </div>
          )}

          <button
            type="submit"
            className="btn-gold login-submit"
            disabled={loading}
          >
            {loading ? '✦ 启动符文中… ✦' : isRegister ? '✦ 创建英雄档案 ✦' : '✦ 进入传说 ✦'}
          </button>

          <button
            type="button"
            className="btn-ghost login-toggle"
            onClick={() => { setIsRegister(!isRegister); setError('') }}
          >
            {isRegister ? '已有英雄档案？点击登录' : '创建新的英雄档案'}
          </button>
        </form>

        <p className="login-hint">
          测试账号：test / 123456
        </p>
      </div>
    </div>
  )
}
