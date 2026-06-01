/**
 * AdventureTopBar — Adventure 顶部章节条。
 */
export default function AdventureTopBar({
  session,
  player,
  isLoading,
  canPrepareSpells,
  syncBlocked = false,
  syncBlockedReason = '',
  onHome,
  onCheckpoint,
  onShowHistory,
  onOpenJournal,
  onOpenRest,
  onOpenPrepare,
  onOpenCharacter,
}) {
  const mutationDisabled = isLoading || syncBlocked
  const mutationTitle = syncBlocked ? syncBlockedReason || '房间正在重新同步，请恢复连接后再操作。' : undefined

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
      <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
        <button className="btn-ghost" style={{ padding: '4px 10px', fontSize: 10 }} onClick={onHome}>◄ 主页</button>
        <button
          className="btn-ghost"
          style={{ padding: '4px 10px', fontSize: 10 }}
          onClick={onCheckpoint}
          disabled={mutationDisabled}
          title={mutationTitle || '保存战役 checkpoint'}
        >
          ● 存档
        </button>
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
      <div style={{ display: 'flex', gap: 4, justifyContent: 'flex-end' }}>
        <button
          className="btn-ghost"
          style={{ padding: '4px 10px', fontSize: 10, borderColor: 'rgba(127,232,248,.5)', color: 'var(--arcane-light)' }}
          onClick={onShowHistory}
        >☰ 对话历史</button>
        <button className="btn-ghost" style={{ padding: '4px 10px', fontSize: 10 }} onClick={onOpenJournal}>✎ 日志</button>
        <button
          className="btn-ghost"
          style={{ padding: '4px 10px', fontSize: 10 }}
          onClick={onOpenRest}
          disabled={mutationDisabled}
          title={mutationTitle || '短休或长休'}
        >
          ☾ 休息
        </button>
        {canPrepareSpells && (
          <button
            className="btn-ghost"
            style={{ padding: '4px 10px', fontSize: 10 }}
            onClick={onOpenPrepare}
            disabled={mutationDisabled}
            title={mutationTitle || '准备法术'}
          >
            ✧ 备法
          </button>
        )}
        {player && (
          <button className="btn-ghost" style={{ padding: '4px 10px', fontSize: 10 }} onClick={onOpenCharacter}>⚜ 角色</button>
        )}
      </div>
    </div>
  )
}
