/**
 * Room — 多人房间内（游戏未开始）
 * 视觉来源：design v0.10 RoomScene
 */
import { useEffect, useState, useCallback } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { roomsApi } from '../api/client'
import { useWebSocket } from '../hooks/useWebSocket'
import { useUser } from '../hooks/useUser'
import { mergeRealtimeRoomEvent, normalizeRealtimeRoom } from '../hooks/useRoomRealtime'
import { useRoomReconnectRefresh } from '../hooks/useRoomReconnectRefresh'
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
  const [roomConfirmAction, setRoomConfirmAction] = useState(null)

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
      case 'member_kicked':
      case 'member_online':
      case 'member_offline':
        if (Array.isArray(event.members)) {
          setRoom(prev => {
            const merged = mergeRealtimeRoomEvent(prev, event)
            if (!merged) return merged
            return event.host_transferred_to
              ? { ...merged, host_user_id: event.host_transferred_to }
              : merged
          })
          break
        }
        refresh(); break
      case 'host_transferred':
        setRoom(prev => prev ? {
          ...prev,
          host_user_id: event.new_host_user_id,
          members: (prev.members || []).map(member => ({
            ...member,
            role: member.user_id === event.new_host_user_id ? 'host' : 'player',
          })),
        } : prev)
        break
      case 'ai_companions_filled':
        refresh(); break
      case 'game_started':
        nav(`/adventure/${sessionId}`); break
      case 'room_dissolved':
        nav('/lobby', { state: { roomNotice: '房间已被解散' } }); break
      default: break
    }
  }, [refresh, nav, sessionId])

  const { connected: wsConnected, status: wsStatus } = useWebSocket(sessionId, onEvent)
  useRoomReconnectRefresh({
    room,
    wsConnected,
    refresh,
  })

  const isHost = room?.host_user_id === myUserId
  const myMember = (room?.members || []).find(m => m.user_id === myUserId)
  const roomSyncBlocked = !!room && !wsConnected
  const roomSyncBlockedReason = '房间正在重新同步，请恢复连接后再调整准备、分组或启动冒险。'

  const copyCode = () => {
    if (!room?.room_code) return
    navigator.clipboard.writeText(room.room_code).then(() => {
      setCopied(true); setTimeout(() => setCopied(false), 1500)
    })
  }

  const onStart = async () => {
    if (roomSyncBlocked) { setError(roomSyncBlockedReason); return }
    setBusy(true); setError('')
    try { await roomsApi.start(sessionId); nav(`/adventure/${sessionId}`) }
    catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }

  const cancelRoomConfirm = () => {
    setRoomConfirmAction(null)
  }

  const confirmRoomAction = async () => {
    const action = roomConfirmAction
    if (!action) return
    setRoomConfirmAction(null)
    if (action.type !== 'leave' && roomSyncBlocked) {
      setError(roomSyncBlockedReason)
      return
    }

    setBusy(true); setError('')
    try {
      if (action.type === 'leave') {
        await roomsApi.leave(sessionId)
        nav('/lobby')
        return
      }
      if (action.type === 'kick') {
        await roomsApi.kick(sessionId, action.userId)
        await refresh()
      } else if (action.type === 'transfer') {
        await roomsApi.transfer(sessionId, action.userId)
        await refresh()
      }
    } catch (e) {
      setError(e.message)
      if (action.type === 'leave') setBusy(false)
    } finally {
      if (action.type !== 'leave') setBusy(false)
    }
  }

  const onLeave = () => {
    setError('')
    setRoomConfirmAction({
      type: 'leave',
      title: '离开房间',
      description: isHost
        ? '房主离开后会自动转让给下一位成员；如果没有其他成员，房间会解散。'
        : '你将离开当前房间并返回多人大厅。',
      actionLabel: '离开房间确认操作',
      submitLabel: '确认离开',
    })
  }

  const onCreateChar = () => {
    if (roomSyncBlocked) { setError(roomSyncBlockedReason); return }
    nav(`/setup/${room.module_id}?roomSession=${sessionId}`)
  }

  const onKick = (uid) => {
    if (roomSyncBlocked) { setError(roomSyncBlockedReason); return }
    setError('')
    setRoomConfirmAction({
      type: 'kick',
      userId: uid,
      title: '移出成员投票',
      description: '这会发起或赞成移出该成员的投票，达到多数后才会执行。',
      actionLabel: '移出成员确认操作',
      submitLabel: '确认投票',
    })
  }

  const onTransfer = (uid) => {
    if (roomSyncBlocked) { setError(roomSyncBlockedReason); return }
    setError('')
    setRoomConfirmAction({
      type: 'transfer',
      userId: uid,
      title: '转让房主',
      description: '确认后该成员会成为新的房主，并接手启动冒险与成员管理权限。',
      actionLabel: '转让房主确认操作',
      submitLabel: '确认转让',
    })
  }

  const onFillAi = async () => {
    if (roomSyncBlocked) { setError(roomSyncBlockedReason); return }
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
    if (roomSyncBlocked) { setError(roomSyncBlockedReason); return }
    setBusy(true); setError('')
    try {
      const updated = await roomsApi.setStartReady(sessionId, ready)
      setRoom(normalizeRealtimeRoom(updated))
    } catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }

  const onFocusGroup = async (groupId) => {
    if (!groupId) return
    if (roomSyncBlocked) { setError(roomSyncBlockedReason); return }
    setBusy(true); setError('')
    try {
      const updated = await roomsApi.focusGroup(sessionId, groupId)
      setRoom(normalizeRealtimeRoom(updated))
    } catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }

  if (!room) {
    return (
      <div className="room-loading-shell">
        <div className="panel-ornate room-loading-panel" role="status" aria-live="polite">
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
    <main className="room-page" aria-label="多人房间大厅">
      <header className="room-page-header" aria-label="房间摘要">
        <div className="eyebrow">✦ 多人房间 ✦</div>
        <div className="display-title room-page-title">{room.save_name || '冒险房间'}</div>
        <div className="room-code-pill" role="group" aria-label="房间码">
          <span className="eyebrow room-code-label">房间码</span>
          <span className="room-code-value">{room.room_code || '—'}</span>
          <button
            type="button"
            onClick={copyCode}
            className="room-code-copy"
            aria-label={copied ? '房间码已复制' : '复制房间码'}
            title={copied ? '房间码已复制' : '复制房间码'}
          >{copied ? '✓' : '⎘'}</button>
        </div>
      </header>

      {room.dm_style && (
        <div className="panel room-dm-style" role="note" aria-label="DM 风格">
          <span className="room-dm-style-label">
            DM 风格：{room.dm_style.label}
          </span>
          <span className="room-dm-style-summary">{room.dm_style.summary}</span>
          <div className="room-dm-style-lock">开始后不可更改</div>
        </div>
      )}

      <Divider>❧ 冒险者们 ❧</Divider>

      <RoomMembersGrid
        members={room.members || []}
        myUserId={myUserId}
        isHost={isHost}
        roomVotes={room.room_votes || []}
        disabledHostControls={busy || roomSyncBlocked}
        disabledReason={roomSyncBlocked ? roomSyncBlockedReason : '房间操作处理中，请稍候。'}
        onTransfer={onTransfer}
        onKick={onKick}
      />

      <Divider>❧ 联机状态 ❧</Divider>

      <RoomMultiplayerStatusPanel
        room={room}
        claimedCount={claimedCount}
        memberCount={memberCount}
        busy={busy}
        wsConnected={wsConnected}
        wsStatus={wsStatus}
        syncBlocked={roomSyncBlocked}
        syncBlockedReason={roomSyncBlockedReason}
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
        syncBlocked={roomSyncBlocked}
        syncBlockedReason={roomSyncBlockedReason}
        onCreateChar={onCreateChar}
        onToggleStartReady={onToggleStartReady}
        onFillAi={onFillAi}
        onStart={onStart}
        onLeave={onLeave}
      />

      {roomConfirmAction && (
        <div
          className="room-confirm-dialog"
          role="dialog"
          aria-modal="true"
          aria-labelledby="room-confirm-title"
          aria-describedby="room-confirm-desc"
        >
          <div className="room-confirm-panel" data-action={roomConfirmAction.type}>
            <h2 id="room-confirm-title">
              {roomConfirmAction.title}
            </h2>
            <p id="room-confirm-desc">
              {roomConfirmAction.description}
            </p>
            <div className="room-confirm-actions" role="group" aria-label={roomConfirmAction.actionLabel}>
              <button
                type="button"
                className="btn-ghost room-confirm-cancel"
                onClick={cancelRoomConfirm}
              >
                取消
              </button>
              <button
                type="button"
                className="btn-gold room-confirm-submit"
                onClick={confirmRoomAction}
              >
                {roomConfirmAction.submitLabel}
              </button>
            </div>
          </div>
        </div>
      )}

      {error && (
        <div className="room-error" role="alert">{error}</div>
      )}
    </main>
  )
}
