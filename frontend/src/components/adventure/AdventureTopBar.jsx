/**
 * AdventureTopBar — Adventure 顶部章节条。
 */
function TopBarButton({
  children,
  label,
  title,
  onClick,
  disabled = false,
  tone = '',
}) {
  return (
    <button
      type="button"
      className={`btn-ghost adventure-topbar-button ${tone}`.trim()}
      onClick={onClick}
      disabled={disabled}
      title={title}
      aria-label={label || title || String(children || '')}
    >
      {children}
    </button>
  )
}

export default function AdventureTopBar({
  session,
  player,
  isLoading,
  canPrepareSpells,
  syncBlocked = false,
  syncBlockedReason = '',
  sharedMutationBlocked = false,
  sharedMutationBlockedReason = '',
  onHome,
  onCheckpoint,
  onShowHistory,
  onOpenJournal,
  onOpenRest,
  onOpenPrepare,
  onOpenCharacter,
}) {
  const syncTitle = syncBlocked ? syncBlockedReason || '房间正在重新同步，请恢复连接后再操作。' : undefined
  const sharedTitle = sharedMutationBlocked ? sharedMutationBlockedReason || 'Only the current speaker can change shared campaign state.' : undefined
  const sharedMutationDisabled = isLoading || syncBlocked || sharedMutationBlocked
  const personalMutationDisabled = isLoading || syncBlocked
  const sharedMutationTitle = sharedTitle || syncTitle
  const loadingTitle = isLoading ? 'Adventure is loading.' : ''

  return (
    <div style={{
      position: 'relative',
      padding: '10px 20px',
      display: 'grid',
      gridTemplateColumns: '1fr auto 1fr',
      alignItems: 'center',
      background: 'linear-gradient(180deg, rgba(16,10,4,.95), rgba(10,6,2,.7))',
      borderBottom: '1px solid rgba(138,90,24,.4)',
      boxShadow: 'inset 0 1px 0 rgba(240,208,96,.15)',
      zIndex: 4,
      flexShrink: 0,
    }}>
      <div className="adventure-topbar-actions">
        <TopBarButton
          label="Home"
          title="Return to the home screen."
          onClick={onHome}
        >
          ◄ 主页
        </TopBarButton>
        <TopBarButton
          label="Save checkpoint"
          onClick={onCheckpoint}
          disabled={sharedMutationDisabled}
          title={sharedMutationTitle || loadingTitle || '保存战役 checkpoint'}
        >
          ● 存档
        </TopBarButton>
      </div>
      <div style={{ textAlign: 'center', minWidth: 0, maxWidth: '60vw' }}>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--amber)', letterSpacing: '.3em', opacity: .7 }}>
          {session.save_name || '我的冒险'}
        </div>
        <div className="display-title" style={{
          fontSize: 18, letterSpacing: '.12em',
          overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap',
        }}>
          {session.module_name || '未知模组'}
        </div>
      </div>
      <div className="adventure-topbar-actions right">
        <TopBarButton
          label="Dialogue history"
          title="Review recent dialogue."
          tone="arcane"
          onClick={onShowHistory}
        >
          ☰ 对话历史
        </TopBarButton>
        <TopBarButton
          label="Open journal"
          title="Open the generated adventure journal."
          onClick={onOpenJournal}
        >
          ✎ 日志
        </TopBarButton>
        <TopBarButton
          label="Open rest menu"
          onClick={onOpenRest}
          disabled={sharedMutationDisabled}
          title={sharedMutationTitle || loadingTitle || '短休或长休'}
        >
          ☾ 休息
        </TopBarButton>
        {canPrepareSpells && (
          <TopBarButton
            label="Prepare spells"
            onClick={onOpenPrepare}
            disabled={personalMutationDisabled}
            title={syncTitle || loadingTitle || '准备法术'}
          >
            ✧ 备法
          </TopBarButton>
        )}
        {player && (
          <TopBarButton
            label="Open character sheet"
            title="Open your character sheet."
            onClick={onOpenCharacter}
          >
            ⚜ 角色
          </TopBarButton>
        )}
      </div>
    </div>
  )
}
