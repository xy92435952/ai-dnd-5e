/**
 * Room — 多人房间内（游戏未开始）
 * 视觉来源：design v0.10 RoomScene
 */
import { useEffect, useState, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { roomsApi } from '../api/client'
import { useWebSocket } from '../hooks/useWebSocket'
import Portrait from '../components/Portrait'
import { classKey } from '../components/Crests'
import { Divider } from '../components/Ornaments'

export default function Room() {
  const { sessionId } = useParams()
  const nav = useNavigate()
  const [room, setRoom] = useState(null)
  const [myUserId, setMyUserId] = useState(null)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    const u = JSON.parse(localStorage.getItem('user') || 'null')
    setMyUserId(u?.user_id || u?.id || null)
  }, [])

  const refresh = useCallback(async () => {
    try {
      const r = await roomsApi.get(sessionId)
      setRoom(r)
      if (r.game_started) nav(`/adventure/${sessionId}`)
    } catch (e) { setError(e.message) }
  }, [sessionId, nav])

  useEffect(() => { refresh() }, [refresh])

  const onEvent = useCallback((event) => {
    switch (event.type) {
      case 'member_joined':
      case 'member_left':
      case 'character_claimed':
      case 'host_transferred':
      case 'member_kicked':
      case 'member_online':
      case 'member_offline':
      case 'ai_companions_filled':
        refresh(); break
      case 'game_started':
        nav(`/adventure/${sessionId}`); break
      case 'room_dissolved':
        alert('房间已被解散'); nav('/lobby'); break
      default: break
    }
  }, [refresh, nav, sessionId])

  useWebSocket(sessionId, onEvent)

  const isHost = room?.host_user_id === myUserId
  const myMember = (room?.members || []).find(m => m.user_id === myUserId)

  const copyCode = () => {
    if (!room?.room_code) return
    navigator.clipboard.writeText(room.room_code).then(() => {
      setCopied(true); setTimeout(() => setCopied(false), 1500)
    })
  }

  const onStart = async () => {
    setBusy(true); setError('')
    try { await roomsApi.start(sessionId); nav(`/adventure/${sessionId}`) }
    catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }

  const onLeave = async () => {
    if (!confirm(isHost ? '确认离开？房主将自动转让给下一位，没人时房间会解散。' : '确认离开房间？')) return
    setBusy(true)
    try { await roomsApi.leave(sessionId); nav('/lobby') }
    catch (e) { setError(e.message); setBusy(false) }
  }

  const onCreateChar = () => {
    nav(`/setup/${room.module_id}?roomSession=${sessionId}`)
  }

  const onKick = async (uid) => {
    if (!confirm('确认踢出该成员？')) return
    setBusy(true)
    try { await roomsApi.kick(sessionId, uid); await refresh() }
    catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }

  const onTransfer = async (uid) => {
    if (!confirm('确认转让房主权限？')) return
    setBusy(true)
    try { await roomsApi.transfer(sessionId, uid); await refresh() }
    catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }

  const onFillAi = async () => {
    setBusy(true); setError('')
    try {
      const r = await roomsApi.fillAi(sessionId)
      if (r.already_full) {
        setError('队伍已满，无需补位')
      }
      await refresh()
    } catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }

  if (!room) {
    return (
      <div style={{ minHeight: '100vh', display: 'grid', placeItems: 'center', position: 'relative', zIndex: 1 }}>
        <div className="panel-ornate" style={{ padding: 28, fontFamily: 'var(--font-script)', fontStyle: 'italic' }}>
          ✦ 召唤房间信息中… ✦
        </div>
      </div>
    )
  }

  const canStart = isHost && (room.members || []).some(m => m.character_id)
  const aiCompanions = room.ai_companions || []
  const claimedCount = (room.members || []).filter(m => m.character_id).length
  const slotsAvailable = Math.max(0, (room.max_players || 4) - claimedCount - aiCompanions.length)

  return (
    <div style={{ minHeight: '100vh', padding: 28, maxWidth: 900, margin: '0 auto', position: 'relative', zIndex: 1 }}>
      <div style={{ textAlign: 'center', marginBottom: 18 }}>
        <div className="eyebrow">✦ 多人房间 ✦</div>
        <div className="display-title" style={{ fontSize: 28, marginTop: 4 }}>{room.save_name || '冒险房间'}</div>
        <div style={{
          marginTop: 12, display: 'inline-flex', gap: 10, alignItems: 'center',
          padding: '6px 16px',
          background: 'rgba(10,6,2,.6)',
          border: '1px solid var(--amber)',
          borderRadius: 24,
        }}>
          <span className="eyebrow" style={{ fontSize: 10 }}>房间码</span>
          <span style={{
            fontFamily: 'var(--font-mono)', fontSize: 18,
            color: 'var(--amber)', fontWeight: 700, letterSpacing: '.3em',
          }}>{room.room_code || '—'}</span>
          <button
            onClick={copyCode}
            style={{
              background: 'transparent', border: 'none', color: 'var(--parchment-dark)',
              cursor: 'pointer', fontSize: 14, padding: '0 4px',
            }}
          >{copied ? '✓' : '⎘'}</button>
        </div>
      </div>

      <Divider>❧ 冒险者们 ❧</Divider>

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(320px, 1fr))', gap: 14, marginTop: 18 }}>
        {(room.members || []).map((m) => (
          <div
            key={m.user_id}
            className="panel-ornate"
            style={{
              padding: 14, display: 'flex', gap: 14, alignItems: 'center',
              opacity: m.is_online ? 1 : 0.5,
            }}
          >
            <div style={{ position: 'relative' }}>
              <Portrait cls={classKey(m.character_name ? 'fighter' : 'dm')} size="md" />
              <span style={{
                position: 'absolute', bottom: 0, right: 0,
                width: 14, height: 14, borderRadius: '50%',
                background: m.is_online ? 'var(--emerald-light)' : 'var(--bark-light)',
                border: '2px solid var(--void)',
                boxShadow: m.is_online ? '0 0 8px var(--emerald-light)' : 'none',
              }} />
            </div>
            <div style={{ flex: 1, minWidth: 0 }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                <span style={{
                  fontFamily: 'var(--font-heading)', color: 'var(--parchment)',
                  fontSize: 14, fontWeight: 600,
                }}>{m.display_name}</span>
                {m.role === 'host' && <span className="tag tag-gold" style={{ fontSize: 9 }}>★ 主持</span>}
                {m.user_id === myUserId && <span className="tag tag-blue" style={{ fontSize: 9 }}>我</span>}
              </div>
              <div style={{ fontSize: 11, color: 'var(--parchment-dark)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>
                {m.character_name
                  ? `角色：${m.character_name}`
                  : (m.is_online ? '○ 尚未选择角色' : '◌ 离线')}
              </div>
            </div>
            {isHost && m.user_id !== myUserId && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                <button onClick={() => onTransfer(m.user_id)} className="btn-ghost" style={{ fontSize: 10, padding: '4px 8px' }}>转让</button>
                <button onClick={() => onKick(m.user_id)} className="btn-ghost" style={{ fontSize: 10, padding: '4px 8px', borderColor: 'var(--blood)', color: '#ffaaaa' }}>踢出</button>
              </div>
            )}
          </div>
        ))}
      </div>

      {/* AI 队友列表 */}
      {aiCompanions.length > 0 && (
        <>
          <Divider>❧ AI 队友 ❧</Divider>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(240px, 1fr))', gap: 10, marginTop: 12 }}>
            {aiCompanions.map((c) => (
              <div
                key={c.id}
                className="panel-ornate"
                style={{ padding: 10, display: 'flex', gap: 10, alignItems: 'center', opacity: 0.92 }}
              >
                <Portrait cls={classKey(c.char_class || 'fighter')} size="sm" />
                <div style={{ flex: 1, minWidth: 0 }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexWrap: 'wrap' }}>
                    <span style={{ fontFamily: 'var(--font-heading)', color: 'var(--parchment)', fontSize: 13, fontWeight: 600 }}>
                      {c.name}
                    </span>
                    <span className="tag" style={{ fontSize: 9, background: 'rgba(139,110,230,.25)', border: '1px solid rgba(139,110,230,.6)', color: '#d4c2ff' }}>
                      ✦ AI
                    </span>
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--parchment-dark)', fontFamily: 'var(--font-mono)', marginTop: 2 }}>
                    {c.race} · {c.char_class} · Lv{c.level}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* 我没角色 → 创建按钮 */}
      {myMember && !myMember.character_id && (
        <div style={{ marginTop: 22, textAlign: 'center' }}>
          <button onClick={onCreateChar} disabled={busy} className="btn-gold" style={{ padding: '12px 32px', fontSize: 14 }}>
            ✦ 创建你的英雄 ✦
          </button>
        </div>
      )}

      {/* 房主：补满 AI 队友 */}
      {isHost && slotsAvailable > 0 && claimedCount >= 1 && (
        <div style={{ marginTop: 14, textAlign: 'center' }}>
          <button
            onClick={onFillAi}
            disabled={busy}
            className="btn-ghost"
            style={{ padding: '10px 22px', fontSize: 12, letterSpacing: '.14em' }}
          >
            {busy ? '✦ 召唤中… ✦' : `✦ 召唤 ${slotsAvailable} 位 AI 队友 ✦`}
          </button>
          <div style={{ fontSize: 10, color: 'var(--parchment-dark)', marginTop: 6, fontFamily: 'var(--font-script)', fontStyle: 'italic' }}>
            根据第一位玩家的职业生成互补角色
          </div>
        </div>
      )}

      {/* 房主：开始游戏 */}
      {isHost && (
        <div style={{ marginTop: 18, textAlign: 'center' }}>
          <button
            onClick={onStart}
            disabled={!canStart || busy}
            className="btn-gold"
            style={{ padding: '12px 32px', fontSize: 14, letterSpacing: '.18em', opacity: canStart ? 1 : .5 }}
          >
            {busy ? '✦ 启动中… ✦' : '✦ 开启冒险 ✦'}
          </button>
          {!canStart && (
            <div style={{ fontSize: 11, color: 'var(--parchment-dark)', marginTop: 6, fontFamily: 'var(--font-script)', fontStyle: 'italic' }}>
              至少需要一位玩家创建并认领角色
            </div>
          )}
        </div>
      )}

      {!isHost && (
        <div style={{ textAlign: 'center', marginTop: 22, opacity: 0.7, fontSize: 13, fontFamily: 'var(--font-script)', fontStyle: 'italic', color: 'var(--parchment-dark)' }}>
          ~ 等待房主开启冒险 ~
        </div>
      )}

      <div style={{ textAlign: 'center', marginTop: 24 }}>
        <button onClick={onLeave} className="btn-ghost" style={{ fontSize: 12, color: '#ffaaaa', borderColor: 'var(--blood)' }}>
          ⎋ 离开房间
        </button>
      </div>

      {error && (
        <div style={{
          marginTop: 14, padding: 10, fontSize: 12, color: '#ffaaaa',
          background: 'rgba(139,32,32,.25)', border: '1px solid var(--blood)',
          borderRadius: 4, fontFamily: 'var(--font-mono)', textAlign: 'center',
        }}>{error}</div>
      )}
    </div>
  )
}
