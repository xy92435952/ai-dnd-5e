/**
 * RestModal — rest selection for single-player and multiplayer rooms.
 */
import Overlay from './Overlay'
import { RestIcon } from '../Icons'

const REST_LABEL = {
  long: '长休',
  short: '短休',
}

export default function RestModal({
  onRest,
  onClose,
  room = null,
  myUserId = null,
  onCreateVote,
  onVote,
  onCancelVote,
  busy = false,
}) {
  const vote = room?.rest_vote || null
  const isMultiplayer = Boolean(room?.is_multiplayer)
  const myVote = vote?.votes?.[myUserId] || null
  const canCancel = vote && (
    vote.proposer_user_id === myUserId ||
    room?.host_user_id === myUserId
  )

  return (
    <Overlay onClose={onClose}>
      <h3 style={{ color: 'var(--amber)', margin: 0, fontSize: 16, display: 'flex', alignItems: 'center', gap: 6 }}>
        <RestIcon size={18} color="var(--amber)" /> 休息
      </h3>

      {isMultiplayer && vote ? (
        <div style={{ display: 'grid', gap: 10 }}>
          <div style={{
            padding: 12,
            border: '1px solid rgba(240,208,96,.35)',
            background: 'rgba(20,14,6,.86)',
            color: 'var(--parchment)',
            fontSize: 12,
          }}>
            <div style={{ color: 'var(--amber)', fontWeight: 700, marginBottom: 6 }}>
              {vote.proposer_name || '队友'} 发起了{REST_LABEL[vote.rest_type] || '休息'}投票
            </div>
            <div style={{ color: 'var(--parchment-dark)' }}>
              赞成 {vote.yes_count || 0} / {vote.required_yes || 1}，反对 {vote.no_count || 0}
              {typeof vote.remaining_seconds === 'number' ? `，剩余 ${vote.remaining_seconds}s` : ''}
            </div>
            {myVote && (
              <div style={{ color: 'var(--arcane-light)', marginTop: 6 }}>
                你的选择：{myVote === 'yes' ? '赞成' : '反对'}
              </div>
            )}
          </div>

          <button
            data-testid="rest-vote-yes"
            className="btn-fantasy"
            style={{ padding: 12, textAlign: 'left', borderColor: 'var(--emerald)', color: 'var(--emerald-light)' }}
            disabled={busy || myVote === 'yes'}
            onClick={() => onVote?.('yes')}
          >
            赞成休息
          </button>
          <button
            data-testid="rest-vote-no"
            className="btn-fantasy"
            style={{ padding: 12, textAlign: 'left' }}
            disabled={busy || myVote === 'no'}
            onClick={() => onVote?.('no')}
          >
            反对休息
          </button>
          {canCancel && (
            <button
              data-testid="rest-vote-cancel"
              className="btn-fantasy"
              style={{ padding: 8, opacity: 0.75 }}
              disabled={busy}
              onClick={onCancelVote}
            >
              取消投票
            </button>
          )}
        </div>
      ) : (
        <>
          <button
            data-testid="rest-long"
            className="btn-fantasy"
            style={{ padding: 14, textAlign: 'left' }}
            disabled={busy}
            onClick={() => (isMultiplayer ? onCreateVote?.('long') : onRest('long'))}
          >
            <div style={{ fontWeight: 700, marginBottom: 4 }}>🌙 长休（8小时）</div>
            <div style={{ fontSize: 12, opacity: 0.6 }}>
              {isMultiplayer ? '发起队伍投票；多数同意后生效' : 'HP 全满 · 法术位全恢复 · 清除大多数状态条件'}
            </div>
          </button>
          <button
            data-testid="rest-short"
            className="btn-fantasy"
            style={{ padding: 14, textAlign: 'left' }}
            disabled={busy}
            onClick={() => (isMultiplayer ? onCreateVote?.('short') : onRest('short'))}
          >
            <div style={{ fontWeight: 700, marginBottom: 4 }}>☕ 短休（1小时）</div>
            <div style={{ fontSize: 12, opacity: 0.6 }}>
              {isMultiplayer ? '发起队伍投票；多数同意后生效' : '消耗一颗生命骰恢复 HP · 魔契者恢复法术位'}
            </div>
          </button>
        </>
      )}

      <button className="btn-fantasy" style={{ padding: 8, opacity: 0.6 }} onClick={onClose}>关闭</button>
    </Overlay>
  )
}
