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
import { DM_STYLES, DEFAULT_DM_STYLE } from '../data/dmStyles'

export default function RoomLobby() {
  const nav = useNavigate()
  const [modules, setModules] = useState([])
  const [tab, setTab] = useState('create') // 'create' | 'join'
  const [moduleId, setModuleId] = useState('')
  const [saveName, setSaveName] = useState('')
  const [maxPlayers, setMaxPlayers] = useState(4)
  const [dmStyle, setDmStyle] = useState(DEFAULT_DM_STYLE)
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
      const r = await roomsApi.create(moduleId, saveName.trim() || null, maxPlayers, dmStyle)
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
    <main className="room-lobby-page" aria-label="多人联机大厅">
      <section className="panel-ornate room-lobby-panel" aria-label="多人房间入口">
        <div className="room-lobby-icon" aria-hidden="true">🎲</div>
        <div className="display-title room-lobby-title">多人联机大厅</div>
        <div className="eyebrow room-lobby-subtitle">✦ 与朋友一起进行 AI 跑团 ✦</div>

        <Divider>❧</Divider>

        {/* 切换 */}
        <div className="room-lobby-tabs" role="tablist" aria-label="房间入口模式">
          {[
            { key: 'create', label: '创建房间' },
            { key: 'join',   label: '加入房间' },
          ].map(t => (
            <button
              key={t.key}
              type="button"
              role="tab"
              aria-selected={tab === t.key}
              data-active={tab === t.key ? 'true' : 'false'}
              className="room-lobby-tab"
              onClick={() => { setTab(t.key); setError('') }}
            >{t.label}</button>
          ))}
        </div>

        {tab === 'create' ? (
          <div className="room-lobby-form" role="group" aria-label="创建房间表单">
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

            <Label>DM 风格（开始后不可更改）</Label>
            <div className="room-lobby-dm-style-list" role="list" aria-label="DM 风格选项">
              {DM_STYLES.map(style => {
                const selected = dmStyle === style.key
                return (
                  <div key={style.key} role="listitem" className="room-lobby-dm-style-item">
                    <button
                      type="button"
                      className="room-lobby-dm-style"
                      aria-pressed={selected}
                      data-selected={selected ? 'true' : 'false'}
                      data-style-key={style.key}
                      onClick={() => setDmStyle(style.key)}
                    >
                      <span className="room-lobby-dm-style-label">
                        {style.label}
                      </span>
                      <span className="room-lobby-dm-style-summary">
                        {style.summary}
                      </span>
                    </button>
                  </div>
                )
              })}
            </div>

            <button onClick={onCreate} disabled={busy} className="btn-gold room-lobby-submit">
              {busy ? '✦ 创建中… ✦' : '✦ 创建并进入房间 ✦'}
            </button>
          </div>
        ) : (
          <div className="room-lobby-form" role="group" aria-label="加入房间表单">
            <Label>房间码</Label>
            <input
              type="text"
              className="input-fantasy room-lobby-code-input"
              autoFocus
              value={roomCode}
              onChange={(e) => setRoomCode(e.target.value.replace(/\D/g, '').slice(0, 6))}
              placeholder="6 位数字"
            />
            <button onClick={onJoin} disabled={busy || roomCode.length !== 6} className="btn-gold room-lobby-submit room-lobby-join-submit">
              {busy ? '✦ 加入中… ✦' : '✦ 加入房间 ✦'}
            </button>
          </div>
        )}

        {error && (
          <div className="room-lobby-error" role="alert">{error}</div>
        )}

        <button onClick={() => nav('/')} className="btn-ghost room-lobby-back">
          ⬅ 返回主页
        </button>
      </section>
    </main>
  )
}

function Label({ children }) {
  return (
    <label className="room-lobby-label">{children}</label>
  )
}
