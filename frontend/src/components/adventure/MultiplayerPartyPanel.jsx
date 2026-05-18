import { useMemo, useState } from 'react'
import { roomsApi } from '../../api/rooms'
import {
  getGroupMemberStatuses,
  getGroupPendingActions,
  getGroupIntentFeedback,
  getMultiplayerTableStatus,
  getMyGroup,
  getReadinessLabel,
} from '../../utils/multiplayerGroups'

export default function MultiplayerPartyPanel({
  room,
  myUserId,
  isMySpeakTurn,
  isLoading,
  onRoomUpdated,
  onError,
}) {
  const [actionText, setActionText] = useState('')
  const [groupName, setGroupName] = useState('')
  const [location, setLocation] = useState('')
  const [busy, setBusy] = useState(false)

  const myGroup = useMemo(() => getMyGroup(room, myUserId), [room, myUserId])
  if (!room?.is_multiplayer || !myUserId || !myGroup) return null

  const pending = getGroupPendingActions(room, myGroup)
  const readiness = room.group_readiness?.[myGroup.id] || {}
  const myReadiness = readiness[myUserId] || 'drafting'
  const memberStatuses = getGroupMemberStatuses(room, myGroup)
  const tableStatus = getMultiplayerTableStatus({ room, myUserId, isMySpeakTurn })
  const intentFeedback = getGroupIntentFeedback({ room, myUserId, isMySpeakTurn })

  const submitAction = async ({ confirm = false } = {}) => {
    const text = actionText.trim()
    if (!text || busy) return
    setBusy(true)
    try {
      const updated = await roomsApi.submitGroupAction(room.session_id, myGroup.id, text)
      if (confirm) {
        const confirmed = await roomsApi.setGroupReadiness(room.session_id, myGroup.id, 'ready')
        onRoomUpdated?.(confirmed)
      } else {
        onRoomUpdated?.(updated)
      }
      setActionText('')
    } catch (e) {
      onError?.(e.message || '提交分队行动失败')
    } finally {
      setBusy(false)
    }
  }

  const switchGroup = async () => {
    const name = groupName.trim()
    if (!name || busy) return
    const groupId = name
      .toLowerCase()
      .replace(/[^\p{L}\p{N}_-]+/gu, '-')
      .replace(/^-+|-+$/g, '')
      .slice(0, 40) || 'main'
    setBusy(true)
    try {
      const updated = await roomsApi.joinGroup(room.session_id, groupId, name, location.trim() || name)
      onRoomUpdated?.(updated)
      setGroupName('')
      setLocation('')
    } catch (e) {
      onError?.(e.message || '切换分队失败')
    } finally {
      setBusy(false)
    }
  }

  const focusGroup = async (groupId) => {
    if (!groupId || busy) return
    setBusy(true)
    try {
      const updated = await roomsApi.focusGroup(room.session_id, groupId)
      onRoomUpdated?.(updated)
    } catch (e) {
      onError?.(e.message || '切换焦点失败')
    } finally {
      setBusy(false)
    }
  }

  const setReadiness = async (status) => {
    if (!status || busy) return
    setBusy(true)
    try {
      const updated = await roomsApi.setGroupReadiness(room.session_id, myGroup.id, status)
      onRoomUpdated?.(updated)
    } catch (e) {
      onError?.(e.message || '更新分队确认状态失败')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={{
      margin: '8px 24px 0',
      padding: '8px 10px',
      border: '1px solid rgba(127,232,248,.28)',
      background: 'rgba(7,18,24,.72)',
      color: 'var(--parchment)',
      fontSize: 11,
      display: 'grid',
      gap: 8,
    }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--arcane-light)', letterSpacing: '.16em' }}>
          分队焦点
        </span>
        <strong style={{ color: 'var(--amber)' }}>{myGroup.name || '当前分队'}</strong>
        <span style={{ color: 'var(--parchment-dark)' }}>{myGroup.location || '当前位置'}</span>
        <span style={{ color: 'var(--parchment-dark)' }}>
          {memberStatuses.map(item => item.label).join(' / ')}
        </span>
        {intentFeedback.statusLabel && (
          <span style={{ color: 'var(--emerald-light)', marginLeft: 'auto' }}>
            {intentFeedback.statusLabel}
          </span>
        )}
        {intentFeedback.readinessLabel && (
          <span style={{ color: 'var(--parchment-dark)' }}>
            {intentFeedback.readinessLabel}
          </span>
        )}
      </div>

      {tableStatus.activeGroup && (
        <div style={{
          display: 'flex',
          gap: 8,
          alignItems: 'center',
          flexWrap: 'wrap',
          padding: '5px 7px',
          border: '1px solid rgba(240,208,96,.18)',
          background: 'rgba(240,208,96,.07)',
          color: 'var(--parchment-dark)',
        }}>
          <span style={{ color: 'var(--amber)', fontFamily: 'var(--font-mono)', letterSpacing: '.1em' }}>
            当前镜头：{tableStatus.activeGroupLabel}
          </span>
          <span>{tableStatus.activeGroup.location || '当前位置'}</span>
          {tableStatus.nextReadySummary && (
            <span style={{ color: 'var(--emerald-light)' }}>{tableStatus.nextReadySummary}</span>
          )}
        </div>
      )}

      {(room.party_groups || []).length > 1 && (
        <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
          {(room.party_groups || []).map(group => {
            const active = group.id === room.active_group_id
            return (
              <button
                key={group.id}
                onClick={() => focusGroup(group.id)}
                disabled={busy || active}
                className="btn-ghost"
                style={{
                  fontSize: 10,
                  padding: '4px 8px',
                  borderColor: active ? 'var(--amber)' : 'rgba(127,232,248,.45)',
                  color: active ? 'var(--amber)' : 'var(--arcane-light)',
                  opacity: active ? 1 : 0.86,
                }}
              >
                {active ? '焦点 · ' : '切焦点 · '}{group.name || group.id}
              </button>
            )
          })}
        </div>
      )}

      {pending.length > 0 && (
        <div style={{ display: 'grid', gap: 4 }}>
          {pending.map((action, idx) => (
            <div key={`${action.user_id}-${idx}`} style={{
              padding: '4px 6px',
              borderLeft: '2px solid var(--arcane-light)',
              background: 'rgba(127,232,248,.08)',
              color: 'var(--parchment-dark)',
            }}>
              <b style={{ color: 'var(--parchment)' }}>{action.display_name || action.user_id}</b>
              <span>：{action.text}</span>
            </div>
          ))}
        </div>
      )}

      <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
        <span style={{ color: 'var(--parchment-dark)' }}>我的状态：{getReadinessLabel(myReadiness)}</span>
        <button
          onClick={() => setReadiness('ready')}
          disabled={busy || isLoading || myReadiness === 'ready'}
          className="btn-ghost"
          style={{
            fontSize: 10,
            padding: '5px 9px',
            borderColor: (myReadiness === 'ready' || intentFeedback.needsMyConfirmation) ? 'var(--emerald)' : undefined,
            color: intentFeedback.needsMyConfirmation ? 'var(--emerald-light)' : undefined,
          }}
        >
          我已确认
        </button>
        <button
          onClick={() => setReadiness('waiting')}
          disabled={busy || isLoading || myReadiness === 'waiting'}
          className="btn-ghost"
          style={{ fontSize: 10, padding: '5px 9px' }}
        >
          等待补充
        </button>
        <button
          onClick={() => setReadiness('drafting')}
          disabled={busy || isLoading || myReadiness === 'drafting'}
          className="btn-ghost"
          style={{ fontSize: 10, padding: '5px 9px' }}
        >
          继续草拟
        </button>
      </div>

      {!isMySpeakTurn && (
        <div style={{ display: 'flex', gap: 6, alignItems: 'center' }}>
          <input
            value={actionText}
            onChange={event => setActionText(event.target.value)}
            onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); submitAction() } }}
            disabled={busy || isLoading}
            placeholder="先提交你的分队行动，当前发言者可以一起带给 DM"
            className="input-fantasy"
            style={{ flex: 1, minWidth: 180, padding: '6px 8px', fontSize: 11 }}
          />
          <button
            onClick={submitAction}
            disabled={busy || isLoading || !actionText.trim()}
            className="btn-ghost"
            style={{ fontSize: 10, padding: '6px 10px' }}
          >
            提交意图
          </button>
          <button
            onClick={() => submitAction({ confirm: true })}
            disabled={busy || isLoading || !actionText.trim()}
            className="btn-ghost"
            style={{
              fontSize: 10,
              padding: '6px 10px',
              borderColor: 'var(--emerald)',
              color: 'var(--emerald-light)',
            }}
          >
            提交并确认
          </button>
        </div>
      )}

      <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
        <input
          value={groupName}
          onChange={event => setGroupName(event.target.value)}
          disabled={busy || isLoading}
          placeholder="新分队名"
          className="input-fantasy"
          style={{ width: 120, padding: '5px 8px', fontSize: 10 }}
        />
        <input
          value={location}
          onChange={event => setLocation(event.target.value)}
          disabled={busy || isLoading}
          placeholder="位置"
          className="input-fantasy"
          style={{ width: 140, padding: '5px 8px', fontSize: 10 }}
        />
        <button
          onClick={switchGroup}
          disabled={busy || isLoading || !groupName.trim()}
          className="btn-ghost"
          style={{ fontSize: 10, padding: '5px 9px' }}
        >
          切换/创建分队
        </button>
      </div>
    </div>
  )
}
