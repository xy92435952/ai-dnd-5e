import { getLocationGraphSummary } from '../../utils/locationGraph'
import { filterPublicClues, filterPublicRecentUpdates } from '../../utils/clueVisibility'

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
        onClick={() => onOpenJournal('companions')}
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
  const visibleClues = filterPublicClues(clues)
  const visibleRecentConsequences = filterPublicRecentUpdates(recentConsequences, clues)
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
  const encounterHudTitle = locationSummary
    ? [
        locationSummary.nextEncounterActive ? 'Active encounter' : 'Encounter',
        locationSummary.nextEncounterName,
        locationSummary.nextEncounterDifficulty,
        locationSummary.nextEncounterEnemies.join(' / '),
      ].filter(Boolean).join('\n')
    : ''
  return (
    <section className="adventure-quest-hud" aria-label="冒险目标与线索状态">
      <span className="quest-hud-label target">◆ 目标</span>
      <span
        title={questTitle}
        className={`quest-title ${questLine ? 'active' : 'empty'}`}
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
          <span className="quest-hud-separator" aria-hidden="true" />
          <span className="quest-hud-label map">◇ 地图</span>
          <span
            title={[
              locationSummary.currentDescription,
              locationSummary.linkedNames.length ? `相邻：${locationSummary.linkedNames.join(' / ')}` : '',
            ].filter(Boolean).join('\n')}
            className="quest-location-name"
          >
            {locationSummary.currentName}
          </span>
          <span className="quest-location-count" aria-label="地图探索进度">
            {locationSummary.visitedCount}/{locationSummary.totalCount}
          </span>
          {locationSummary.encounterCount > 0 && (
            <span
              className={`location-encounter-pill ${locationSummary.nextEncounterActive ? 'active' : ''}`}
              title={encounterHudTitle}
            >
              {locationSummary.nextEncounterActive ? 'ACTIVE' : 'ENC'} {locationSummary.encounterCount}
            </span>
          )}
        </>
      )}
      <span className="quest-hud-separator" aria-hidden="true" />
      <span className="quest-hud-label clues">❖ 线索 {visibleClues.length}</span>
      <div className="quest-clue-list" role="list" aria-label="公开线索">
        {visibleClues.map((c, i) => (
          <span key={i} className={`quest-clue-item${c.is_new ? ' new' : ''}`} role="listitem">
            {i > 0 ? '· ' : ''}{c.text}
            {c.is_new && (
              <span className="quest-new-badge">
                NEW
              </span>
            )}
          </span>
        ))}
      </div>
      {(npcUpdates.length > 0 || keyDecisions.length > 0) && (
        <>
          <span className="quest-hud-separator" aria-hidden="true" />
          <span className="quest-hud-label memory">记忆</span>
          <div className="quest-memory-list" role="list" aria-label="重要记忆">
            {npcUpdates.map(npc => (
              <span key={`npc-${npc.name}`} title={(npc.keyFacts || []).join('；')} className="quest-memory-item npc" role="listitem">
                {npc.name}:{npc.relationship}
              </span>
            ))}
            {keyDecisions.slice(-1).map(decision => (
              <span key={`decision-${decision}`} title={decision} className="quest-memory-item decision" role="listitem">
                · {decision}
              </span>
            ))}
          </div>
        </>
      )}
      {companionSignals.length > 0 && (
        <>
          <span className="quest-hud-separator" aria-hidden="true" />
          <span className="quest-hud-label bonds">羁绊</span>
          <div className="companion-signal-list" role="group" aria-label="队友羁绊信号">
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
      {visibleRecentConsequences.length > 0 && (
        <>
          <span className="quest-hud-separator" aria-hidden="true" />
          <span className="quest-hud-label recent">最近</span>
          <div className="quest-recent-list" role="list" aria-label="最近战役变化">
            {visibleRecentConsequences.map((item, index) => {
              const type = item.type || 'note'
              const typeLabel = RECENT_TYPE_LABELS[type] || '记录'
              const detail = item.detail ? `：${item.detail}` : ''
              return (
                <span
                  key={`${type}-${item.label}-${index}`}
                  className={`quest-recent-item ${type}`}
                  title={`${typeLabel} ${item.label}${detail}`}
                  role="listitem"
                >
                  <b>{typeLabel}</b>{item.label}{detail}
                </span>
              )
            })}
          </div>
        </>
      )}
    </section>
  )
}
