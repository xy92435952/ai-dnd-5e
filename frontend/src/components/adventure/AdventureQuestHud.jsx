import { getLocationGraphSummary } from '../../utils/locationGraph'

const RECENT_TYPE_LABELS = {
  quest: '任务',
  clue: '线索',
  companion: '队友',
  decision: '决定',
  npc: 'NPC',
  world: '后果',
}

const QUEST_STATUS_META = {
  active: { label: '进行中', tone: 'active' },
  completed: { label: '完成', tone: 'good' },
  failed: { label: '失败', tone: 'danger' },
  blocked: { label: '受阻', tone: 'danger' },
  paused: { label: '暂停', tone: 'default' },
}

function cleanText(value) {
  return String(value || '').trim()
}

function getQuestStatusMeta(questLine) {
  const status = cleanText(questLine?.status || 'active').toLowerCase()
  return QUEST_STATUS_META[status] || { label: questLine?.status || '记录', tone: 'default' }
}

function getQuestDetail(questLine) {
  return [
    questLine?.outcome,
    questLine?.next_step,
    questLine?.consequence,
    questLine?.failure_consequence,
    questLine?.fail_forward,
    questLine?.detail,
  ].map(cleanText).find(Boolean) || ''
}

function CompanionSignalChip({ signal, onOpenJournal }) {
  const content = (
    <>
      <b>{signal.name}</b>{signal.summary}
      {signal.detail && <em>{signal.detail}</em>}
    </>
  )
  if (onOpenJournal) {
    return (
      <button
        type="button"
        className={`companion-signal-item ${signal.tone}`}
        title={signal.title}
        aria-label={`打开卷宗查看${signal.name}羁绊`}
        onClick={onOpenJournal}
      >
        {content}
      </button>
    )
  }
  return (
    <span
      className={`companion-signal-item ${signal.tone}`}
      title={signal.title}
    >
      {content}
    </span>
  )
}

export default function AdventureQuestHud({
  questLine,
  clues,
  npcUpdates = [],
  keyDecisions = [],
  recentConsequences = [],
  companionSignals = [],
  locationGraph = null,
  onOpenJournal,
}) {
  const locationSummary = getLocationGraphSummary(locationGraph)
  const questStatus = getQuestStatusMeta(questLine)
  const questDetail = getQuestDetail(questLine)
  const questProgressCount = Number(questLine?.progressCount || 0)
  const questTitle = questLine
    ? [
        questLine.quest,
        `状态：${questStatus.label}`,
        questProgressCount > 0 ? `进展：${questProgressCount}` : '',
        questLine.branch ? `分支：${questLine.branch}` : '',
        questDetail ? `进展：${questDetail}` : '',
        questLine.consequence ? `后果：${questLine.consequence}` : '',
        questLine.failure_consequence ? `失败代价：${questLine.failure_consequence}` : '',
        questLine.fail_forward ? `失败推进：${questLine.fail_forward}` : '',
      ].filter(Boolean).join('\n')
    : ''
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: 10,
      padding: '6px 12px',
      background: 'linear-gradient(180deg, rgba(26,18,8,.8), rgba(10,6,4,.6))',
      border: '1px solid rgba(138,90,24,.4)',
      boxShadow: 'inset 0 1px 0 rgba(240,208,96,.12)',
      overflow: 'hidden',
    }}>
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--amber)', letterSpacing: '.2em', textTransform: 'uppercase', whiteSpace: 'nowrap' }}>◆ 目标</span>
      <span
        title={questTitle}
        style={{ color: questLine ? 'var(--blood-light)' : 'var(--parchment-dark)', fontSize: 12, fontFamily: 'var(--font-body)', whiteSpace: 'nowrap', overflow: 'hidden', textOverflow: 'ellipsis' }}
      >
        {questLine?.quest || '继续冒险'}
      </span>
      {questLine && (
        <span className={`quest-status-pill ${questStatus.tone}`} title={questTitle}>
          {questStatus.label}
        </span>
      )}
      {questLine?.branch && (
        <span className="quest-branch-pill" title={questTitle}>
          {questLine.branch}
        </span>
      )}
      {questProgressCount > 0 && (
        <span className="quest-progress-pill" title={questTitle}>
          进展 {questProgressCount}
        </span>
      )}
      {questDetail && (
        <span className={`quest-outcome-snippet ${questStatus.tone}`} title={questTitle}>
          {questDetail}
        </span>
      )}
      {locationSummary && (
        <>
          <span style={{ width: 1, alignSelf: 'stretch', background: 'rgba(138,90,24,.3)' }} />
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--emerald-light)', letterSpacing: '.2em', textTransform: 'uppercase', whiteSpace: 'nowrap' }}>◇ 地图</span>
          <span
            title={[
              locationSummary.currentDescription,
              locationSummary.linkedNames.length ? `相邻：${locationSummary.linkedNames.join(' / ')}` : '',
            ].filter(Boolean).join('\n')}
            style={{
              color: 'var(--parchment-light)',
              fontSize: 11,
              fontFamily: 'var(--font-body)',
              whiteSpace: 'nowrap',
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              maxWidth: 180,
            }}
          >
            {locationSummary.currentName}
          </span>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--parchment-dark)', whiteSpace: 'nowrap' }}>
            {locationSummary.visitedCount}/{locationSummary.totalCount}
          </span>
          {locationSummary.encounterCount > 0 && (
            <span
              title={[
                locationSummary.nextEncounterName,
                locationSummary.nextEncounterDifficulty,
                locationSummary.nextEncounterEnemies.join(' / '),
              ].filter(Boolean).join('\n')}
              style={{
                fontFamily: 'var(--font-mono)',
                fontSize: 9,
                color: 'var(--blood-light)',
                whiteSpace: 'nowrap',
              }}
            >
              ENC {locationSummary.encounterCount}
            </span>
          )}
        </>
      )}
      <span style={{ width: 1, alignSelf: 'stretch', background: 'rgba(138,90,24,.3)' }} />
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--arcane-light)', letterSpacing: '.2em', textTransform: 'uppercase', whiteSpace: 'nowrap' }}>❖ 线索 {clues.length}</span>
      <div style={{ display: 'flex', gap: 6, overflow: 'hidden', minWidth: 0 }}>
        {clues.map((c, i) => (
          <span key={i} style={{
            fontSize: 11,
            color: c.is_new ? 'var(--amber)' : 'var(--parchment-dark)',
            fontStyle: 'italic', whiteSpace: 'nowrap',
          }}>
            {i > 0 ? '· ' : ''}{c.text}
            {c.is_new && (
              <span style={{ fontSize: 8, color: 'var(--amber)', border: '1px solid var(--amber)', padding: '0 5px', letterSpacing: '.15em', fontFamily: 'var(--font-mono)', marginLeft: 4 }}>
                NEW
              </span>
            )}
          </span>
        ))}
      </div>
      {(npcUpdates.length > 0 || keyDecisions.length > 0) && (
        <>
          <span style={{ width: 1, alignSelf: 'stretch', background: 'rgba(138,90,24,.3)' }} />
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--parchment-dark)', letterSpacing: '.18em', textTransform: 'uppercase', whiteSpace: 'nowrap' }}>记忆</span>
          <div style={{ display: 'flex', gap: 6, overflow: 'hidden', minWidth: 0 }}>
            {npcUpdates.map(npc => (
              <span key={`npc-${npc.name}`} title={(npc.keyFacts || []).join('；')} style={{
                fontSize: 11,
                color: 'var(--parchment-light)',
                whiteSpace: 'nowrap',
              }}>
                {npc.name}:{npc.relationship}
              </span>
            ))}
            {keyDecisions.slice(-1).map(decision => (
              <span key={`decision-${decision}`} title={decision} style={{
                fontSize: 11,
                color: 'var(--amber)',
                whiteSpace: 'nowrap',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                maxWidth: 180,
              }}>
                · {decision}
              </span>
            ))}
          </div>
        </>
      )}
      {companionSignals.length > 0 && (
        <>
          <span style={{ width: 1, alignSelf: 'stretch', background: 'rgba(138,90,24,.3)' }} />
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--emerald-light)', letterSpacing: '.18em', textTransform: 'uppercase', whiteSpace: 'nowrap' }}>羁绊</span>
          <div className="companion-signal-list">
            {companionSignals.map(signal => (
              <CompanionSignalChip
                key={signal.id}
                signal={signal}
                onOpenJournal={onOpenJournal}
              />
            ))}
          </div>
        </>
      )}
      {recentConsequences.length > 0 && (
        <>
          <span style={{ width: 1, alignSelf: 'stretch', background: 'rgba(138,90,24,.3)' }} />
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 9, color: 'var(--amber)', letterSpacing: '.18em', textTransform: 'uppercase', whiteSpace: 'nowrap' }}>最近</span>
          <div className="quest-recent-list">
            {recentConsequences.map((item, index) => {
              const type = item.type || 'note'
              const typeLabel = RECENT_TYPE_LABELS[type] || '记录'
              const detail = item.detail ? `：${item.detail}` : ''
              return (
                <span
                  key={`${type}-${item.label}-${index}`}
                  className={`quest-recent-item ${type}`}
                  title={`${typeLabel} ${item.label}${detail}`}
                >
                  <b>{typeLabel}</b>{item.label}{detail}
                </span>
              )
            })}
          </div>
        </>
      )}
    </div>
  )
}
