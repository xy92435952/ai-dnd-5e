import { useMemo, useState } from 'react'
import { roomsApi } from '../../api/client'
import {
  getGroupMemberStatuses,
  getGroupPendingActions,
  getGroupIntentFeedback,
  getGroupReadinessBreakdown,
  getMultiplayerTableStatus,
  getMyGroup,
  getReadinessLabel,
} from '../../utils/multiplayerGroups'

export default function MultiplayerPartyPanel({
  room,
  myUserId,
  isMySpeakTurn,
  isLoading,
  syncBlocked = false,
  syncBlockedReason = '',
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
  const readinessBreakdown = getGroupReadinessBreakdown(room, myGroup)
  const showReadinessBreakdown = readinessBreakdown.memberCount > 1
    && (pending.length > 0 || readinessBreakdown.readyCount > 0 || myReadiness !== 'drafting')
  const readinessChips = [
    {
      key: 'summary',
      label: readinessBreakdown.summaryLabel,
      color: readinessBreakdown.notReadyNames.length ? 'var(--amber)' : 'var(--emerald-light)',
      borderColor: readinessBreakdown.notReadyNames.length ? 'rgba(240,208,96,.28)' : 'rgba(91,214,138,.28)',
    },
    {
      key: 'ready',
      label: readinessBreakdown.readyLabel,
      color: 'var(--emerald-light)',
      borderColor: 'rgba(91,214,138,.24)',
    },
    {
      key: 'waiting',
      label: readinessBreakdown.waitingLabel,
      color: 'var(--parchment-dark)',
      borderColor: 'rgba(226,232,240,.18)',
    },
    {
      key: 'drafting',
      label: readinessBreakdown.draftingLabel,
      color: 'var(--arcane-light)',
      borderColor: 'rgba(127,232,248,.18)',
    },
  ].filter(item => item.label)
  const readinessPromptToneStyles = {
    urgent: {
      color: 'var(--amber)',
      borderColor: 'rgba(240,208,96,.34)',
      background: 'rgba(240,208,96,.08)',
    },
    pending: {
      color: 'var(--parchment-dark)',
      borderColor: 'rgba(127,232,248,.24)',
      background: 'rgba(127,232,248,.06)',
    },
    waiting: {
      color: 'var(--parchment-dark)',
      borderColor: 'rgba(226,232,240,.2)',
      background: 'rgba(226,232,240,.05)',
    },
    ready: {
      color: 'var(--emerald-light)',
      borderColor: 'rgba(91,214,138,.3)',
      background: 'rgba(91,214,138,.07)',
    },
  }
  const readinessPromptStyle = readinessPromptToneStyles[intentFeedback.readinessPromptTone]
    || readinessPromptToneStyles.pending
  const readinessPromptBadge = intentFeedback.readinessReset
    ? '需重新确认'
    : intentFeedback.readinessPromptTone === 'ready' ? '已就绪' : '确认提示'
  const controlsDisabled = busy || isLoading || syncBlocked
  const syncBlockLabel = syncBlockedReason || '房间正在重新同步，请恢复连接后再调整分队。'

  const submitAction = async ({ confirm = false } = {}) => {
    const text = actionText.trim()
    if (!text || controlsDisabled) return
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
    if (!name || controlsDisabled) return
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
    if (!groupId || controlsDisabled) return
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
    if (!status || controlsDisabled) return
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
    <section className="multiplayer-party-panel" aria-label="分队协作面板">
      <div className="multiplayer-party-head" role="group" aria-label="当前分队状态">
        <span className="multiplayer-party-kicker">
          分队焦点
        </span>
        <strong className="multiplayer-party-name">{myGroup.name || '当前分队'}</strong>
        <span className="multiplayer-party-location">{myGroup.location || '当前位置'}</span>
        <span className="multiplayer-party-members">
          {memberStatuses.map(item => item.label).join(' / ')}
        </span>
        {intentFeedback.statusLabel && (
          <span className="multiplayer-party-status" aria-live="polite">
            {intentFeedback.statusLabel}
          </span>
        )}
        {intentFeedback.readinessLabel && (
          <span className="multiplayer-party-readiness-label">
            {intentFeedback.readinessLabel}
          </span>
        )}
      </div>

      {showReadinessBreakdown && (
        <div
          aria-label="分队确认详情"
          className="multiplayer-party-readiness-detail"
        >
          {readinessChips.map(chip => (
            <span
              key={chip.key}
              title={chip.label}
              className="multiplayer-party-chip"
              style={{
                '--party-chip-border': chip.borderColor,
                color: chip.color,
              }}
            >
              {chip.label}
            </span>
          ))}
        </div>
      )}

      {intentFeedback.readinessPrompt && (
        <div
          aria-label="分队确认提示"
          className="multiplayer-party-prompt"
          style={{
            '--party-prompt-border': readinessPromptStyle.borderColor,
            '--party-prompt-bg': readinessPromptStyle.background,
            color: readinessPromptStyle.color,
          }}
        >
          <strong>{readinessPromptBadge}</strong>
          <span>{intentFeedback.readinessPrompt}</span>
        </div>
      )}

      {syncBlocked && (
        <div className="multiplayer-sync-guard" role="status">
          <strong>同步暂停</strong>
          <span>{syncBlockLabel}</span>
        </div>
      )}

      {tableStatus.activeGroup && (
        <div className="multiplayer-party-camera" aria-label="当前镜头状态">
          <span className="multiplayer-party-camera-label">
            当前镜头：{tableStatus.activeGroupLabel}
          </span>
          <span>{tableStatus.activeGroup.location || '当前位置'}</span>
          {tableStatus.nextReadySummary && (
            <span className="multiplayer-party-camera-ready">{tableStatus.nextReadySummary}</span>
          )}
          {tableStatus.processingHint && (
            <span
              aria-label="DM处理提示"
              title={tableStatus.processingHint}
              className="multiplayer-party-camera-hint"
            >
              {tableStatus.processingHint}
            </span>
          )}
        </div>
      )}

      {(room.party_groups || []).length > 1 && (
        <div className="multiplayer-party-group-switcher" role="group" aria-label="分队切换">
          {(room.party_groups || []).map(group => {
            const active = group.id === room.active_group_id
            return (
              <button
                key={group.id}
                onClick={() => focusGroup(group.id)}
                disabled={controlsDisabled || active}
                className={`btn-ghost multiplayer-party-focus-btn${active ? ' active' : ''}`}
              >
                {active ? '焦点 · ' : '切焦点 · '}{group.name || group.id}
              </button>
            )
          })}
        </div>
      )}

      {pending.length > 0 && (
        <div className="multiplayer-party-pending-list" role="list" aria-label="分队待处理意图">
          {pending.map((action, idx) => (
            <div key={`${action.user_id}-${idx}`} className="multiplayer-party-pending-item" role="listitem">
              <b>{action.display_name || action.user_id}</b>
              <span>：{action.text}</span>
            </div>
          ))}
        </div>
      )}

      <div className="multiplayer-party-actions" role="group" aria-label="分队确认操作">
        <span className="multiplayer-party-status-label">我的状态：{getReadinessLabel(myReadiness)}</span>
        <button
          onClick={() => setReadiness('ready')}
          disabled={controlsDisabled || myReadiness === 'ready'}
          className={`btn-ghost multiplayer-party-action-btn${
            (myReadiness === 'ready' || intentFeedback.needsMyConfirmation) ? ' needs-confirmation' : ''
          }`}
        >
          我已确认
        </button>
        <button
          onClick={() => setReadiness('waiting')}
          disabled={controlsDisabled || myReadiness === 'waiting'}
          className="btn-ghost multiplayer-party-action-btn"
        >
          等待补充
        </button>
        <button
          onClick={() => setReadiness('drafting')}
          disabled={controlsDisabled || myReadiness === 'drafting'}
          className="btn-ghost multiplayer-party-action-btn"
        >
          继续草拟
        </button>
      </div>

      {!isMySpeakTurn && (
        <div className="multiplayer-party-intent" role="group" aria-label="分队意图提交">
          <input
            value={actionText}
            onChange={event => setActionText(event.target.value)}
            onKeyDown={event => { if (event.key === 'Enter') { event.preventDefault(); submitAction() } }}
            disabled={controlsDisabled}
            placeholder="先提交你的分队行动，当前发言者可以一起带给 DM"
            className="input-fantasy multiplayer-party-intent-input"
          />
          <button
            onClick={submitAction}
            disabled={controlsDisabled || !actionText.trim()}
            className="btn-ghost multiplayer-party-submit-btn"
          >
            提交意图
          </button>
          <button
            onClick={() => submitAction({ confirm: true })}
            disabled={controlsDisabled || !actionText.trim()}
            className="btn-ghost multiplayer-party-submit-btn confirm"
          >
            提交并确认
          </button>
        </div>
      )}

      <div className="multiplayer-party-create-group" role="group" aria-label="创建或切换分队">
        <input
          value={groupName}
          onChange={event => setGroupName(event.target.value)}
          disabled={controlsDisabled}
          placeholder="新分队名"
          className="input-fantasy multiplayer-party-name-input"
        />
        <input
          value={location}
          onChange={event => setLocation(event.target.value)}
          disabled={controlsDisabled}
          placeholder="位置"
          className="input-fantasy multiplayer-party-location-input"
        />
        <button
          onClick={switchGroup}
          disabled={controlsDisabled || !groupName.trim()}
          className="btn-ghost multiplayer-party-action-btn"
        >
          切换/创建分队
        </button>
      </div>
    </section>
  )
}
