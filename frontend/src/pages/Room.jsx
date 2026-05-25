/**
 * Room — 多人房间内（游戏未开始）
 * 视觉来源：design v0.10 RoomScene
 */
import { useEffect, useState, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { roomsApi } from '../api/client'
import { useWebSocket } from '../hooks/useWebSocket'
import { useUser } from '../hooks/useUser'
import { normalizeRealtimeRoom } from '../hooks/useRoomRealtime'
import { Divider } from '../components/Ornaments'
import RoomActionsPanel from '../components/room/RoomActionsPanel'
import RoomAiCompanionsSection from '../components/room/RoomAiCompanionsSection'
import RoomMembersGrid from '../components/room/RoomMembersGrid'
import RoomMultiplayerStatusPanel from '../components/room/RoomMultiplayerStatusPanel'

export default function Room() {
  const { sessionId } = useParams()
  const nav = useNavigate()
  const [room, setRoom] = useState(null)
  const { userId: myUserId } = useUser()
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [copied, setCopied] = useState(false)

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
      case 'room_state_updated':
        if (event.room) setRoom(normalizeRealtimeRoom(event.room))
        break
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

  const onToggleStartReady = async (ready) => {
    setBusy(true); setError('')
    try {
      const updated = await roomsApi.setStartReady(sessionId, ready)
      setRoom(normalizeRealtimeRoom(updated))
    } catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }

  const onFocusGroup = async (groupId) => {
    if (!groupId) return
    setBusy(true); setError('')
    try {
      const updated = await roomsApi.focusGroup(sessionId, groupId)
      setRoom(normalizeRealtimeRoom(updated))
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

  const aiCompanions = room.ai_companions || []
  const claimedCount = (room.members || []).filter(m => m.character_id).length
  const memberCount = (room.members || []).length
  const startReadyUserIds = room.start_ready_user_ids || []
  const startReadySet = new Set(startReadyUserIds)
  const startReadyCount = (room.members || []).filter(m => startReadySet.has(m.user_id)).length
  const isStartReady = !!(myUserId && startReadySet.has(myUserId))
  const allMembersClaimed = memberCount > 0 && claimedCount === memberCount
  const allMembersStartReady = memberCount > 0 && startReadyCount === memberCount
  const canStart = isHost && allMembersClaimed && allMembersStartReady
  const slotsAvailable = Math.max(0, (room.max_players || 4) - memberCount - aiCompanions.length)

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

      {room.dm_style && (
        <div className="panel" style={{
          maxWidth: 560,
          margin: '0 auto 16px',
          padding: '10px 14px',
          textAlign: 'center',
          color: 'var(--parchment-dark)',
          fontSize: 12,
          lineHeight: 1.6,
        }}>
          <span style={{ color: 'var(--amber)', fontFamily: 'var(--font-heading)', letterSpacing: '.08em' }}>
            DM 风格：{room.dm_style.label}
          </span>
          <span style={{ marginLeft: 8 }}>{room.dm_style.summary}</span>
          <div style={{ marginTop: 4, fontSize: 10, fontFamily: 'var(--font-mono)' }}>开始后不可更改</div>
        </div>
      )}

      <Divider>❧ 冒险者们 ❧</Divider>

      <RoomMembersGrid
        members={room.members || []}
        myUserId={myUserId}
        isHost={isHost}
        onTransfer={onTransfer}
        onKick={onKick}
      />

      <Divider>❧ 联机状态 ❧</Divider>

      <RoomMultiplayerStatusPanel
        room={room}
        claimedCount={claimedCount}
        memberCount={memberCount}
        busy={busy}
        onFocusGroup={onFocusGroup}
      />

      <RoomAiCompanionsSection aiCompanions={aiCompanions} />

      <RoomActionsPanel
        isHost={isHost}
        busy={busy}
        canStart={canStart}
        slotsAvailable={slotsAvailable}
        claimedCount={claimedCount}
        memberCount={memberCount}
        startReadyCount={startReadyCount}
        isStartReady={isStartReady}
        myMember={myMember}
        onCreateChar={onCreateChar}
        onToggleStartReady={onToggleStartReady}
        onFillAi={onFillAi}
        onStart={onStart}
        onLeave={onLeave}
      />

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
