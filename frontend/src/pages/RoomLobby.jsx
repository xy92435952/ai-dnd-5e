/**
 * RoomLobby — 多人联机大厅
 * - 创建房间（选模组 + 人数）
 * - 用 6 位码加入房间
 * - 跳转到 /room/:sessionId 进入房间界面
 *
 * 视觉来源：design v0.10
 */
import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { modulesApi, roomsApi } from '../api/client'
import { Divider } from '../components/Ornaments'

export default function RoomLobby() {
  const nav = useNavigate()
  const [modules, setModules] = useState([])
  const [tab, setTab] = useState('create') // 'create' | 'join'
  const [moduleId, setModuleId] = useState('')
  const [saveName, setSaveName] = useState('')
  const [maxPlayers, setMaxPlayers] = useState(4)
  const [roomCode, setRoomCode] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    modulesApi.list()
      .then((mods) => {
        setModules(mods || [])
        if (mods?.[0]) setModuleId(mods[0].id)
      })
      .catch((e) => setError(e.message))
  }, [])

  const onCreate = async () => {
    if (!moduleId) { setError('请先选择模组'); return }
    setError(''); setBusy(true)
    try {
      const r = await roomsApi.create(moduleId, saveName.trim() || null, maxPlayers)
      nav(`/room/${r.session_id}`)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  const onJoin = async () => {
    const code = roomCode.trim()
    if (code.length !== 6) { setError('请输入 6 位房间码'); return }
    setError(''); setBusy(true)
    try {
      const r = await roomsApi.join(code)
      nav(`/room/${r.session_id}`)
    } catch (e) {
      setError(e.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={{
      minHeight: '100vh',
      display: 'grid', placeItems: 'center',
      padding: 24, position: 'relative', zIndex: 1,
    }}>
      <div className="panel-ornate" style={{
        padding: '36px 40px',
        width: 460, maxWidth: '92vw',
        position: 'relative', textAlign: 'center',
      }}>
        <div style={{ fontSize: 36, marginBottom: 6 }}>🎲</div>
        <div className="display-title" style={{ fontSize: 24, letterSpacing: '.12em' }}>多人联机大厅</div>
        <div className="eyebrow" style={{ marginTop: 6 }}>✦ 与朋友一起进行 AI 跑团 ✦</div>

        <Divider>❧</Divider>

        {/* 切换 */}
        <div style={{ display: 'flex', gap: 4, marginTop: 14, padding: 4, background: 'rgba(10,6,2,.5)', borderRadius: 24, border: '1px solid var(--bark-light)' }}>
          {[
            { key: 'create', label: '创建房间' },
            { key: 'join',   label: '加入房间' },
          ].map(t => (
            <button
              key={t.key}
              onClick={() => { setTab(t.key); setError('') }}
              style={{
                flex: 1, padding: '8px 0',
                background: tab === t.key ? 'var(--gold-gradient)' : 'transparent',
                color: tab === t.key ? 'var(--void)' : 'var(--parchment-dark)',
                fontWeight: tab === t.key ? 700 : 400,
                border: 'none', borderRadius: 20,
                fontFamily: 'var(--font-heading)',
                fontSize: 13, letterSpacing: '.15em',
                cursor: 'pointer',
                transition: 'var(--transition)',
              }}
            >{t.label}</button>
          ))}
        </div>

        {tab === 'create' ? (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 18, textAlign: 'left' }}>
            <Label>选择模组</Label>
            <select className="input-fantasy" value={moduleId} onChange={(e) => setModuleId(e.target.value)}>
              <option value="">— 请选择 —</option>
              {modules.map(m => <option key={m.id} value={m.id}>{m.name}</option>)}
            </select>

            <Label>存档名（可选）</Label>
            <input className="input-fantasy" type="text" maxLength={50}
              value={saveName} onChange={(e) => setSaveName(e.target.value)}
              placeholder="例如：周五跑团团" />

            <Label>最大人数</Label>
            <select className="input-fantasy" value={maxPlayers}
              onChange={(e) => setMaxPlayers(Number(e.target.value))}>
              {[2, 3, 4].map(n => <option key={n} value={n}>{n} 人</option>)}
            </select>

            <button onClick={onCreate} disabled={busy} className="btn-gold"
              style={{ marginTop: 10, padding: '12px', fontSize: 14, letterSpacing: '.18em' }}>
              {busy ? '✦ 创建中… ✦' : '✦ 创建并进入房间 ✦'}
            </button>
          </div>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, marginTop: 18, textAlign: 'left' }}>
            <Label>房间码</Label>
            <input
              type="text"
              className="input-fantasy"
              autoFocus
              value={roomCode}
              onChange={(e) => setRoomCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              placeholder="6 位数字"
              style={{
                fontSize: 26, letterSpacing: 10, textAlign: 'center',
                fontFamily: 'var(--font-mono)', fontWeight: 700,
                color: 'var(--amber)', padding: '14px',
              }}
            />
            <button onClick={onJoin} disabled={busy || roomCode.length !== 6} className="btn-gold"
              style={{ marginTop: 6, padding: '12px', fontSize: 14, letterSpacing: '.18em' }}>
              {busy ? '✦ 加入中… ✦' : '✦ 加入房间 ✦'}
            </button>
          </div>
        )}

        {error && (
          <div style={{
            marginTop: 14, padding: 8, fontSize: 12, color: '#ffaaaa',
            background: 'rgba(139,32,32,.25)', border: '1px solid var(--blood)',
            borderRadius: 4, fontFamily: 'var(--font-mono)',
          }}>{error}</div>
        )}

        <button onClick={() => nav('/')} className="btn-ghost" style={{ marginTop: 16, width: '100%', fontSize: 12 }}>
          ⬅ 返回主页
        </button>
      </div>
    </div>
  )
}

function Label({ children }) {
  return (
    <label style={{
      fontSize: 10, color: 'var(--parchment-dark)',
      letterSpacing: '.2em', textTransform: 'uppercase',
      marginTop: 4, fontFamily: 'var(--font-mono)',
    }}>{children}</label>
  )
}
