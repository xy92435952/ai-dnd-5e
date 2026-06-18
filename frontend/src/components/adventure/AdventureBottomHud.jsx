/**
 * AdventureBottomHud — 底部队伍、目标与线索条。
 */
import AdventurePartyHud from './AdventurePartyHud'
import AdventureQuestHud from './AdventureQuestHud'

function AdventureToolButton({
  label,
  hint,
  badge = '',
  disabled = false,
  disabledReason = '',
  onClick,
}) {
  const title = disabled ? disabledReason : hint
  return (
    <button
      type="button"
      className="skill-chip adventure-tool-button"
      onClick={onClick}
      disabled={disabled}
      title={title}
      aria-label={`${label}${disabled ? ` unavailable: ${disabledReason}` : `: ${hint}`}`}
    >
      <span className="adventure-tool-label">{label}</span>
      {badge && <span className="adventure-tool-badge">{badge}</span>}
    </button>
  )
}

export default function AdventureBottomHud({
  allMembers,
  questLine,
  clues,
  npcUpdates,
  keyDecisions,
  recentConsequences,
  companionSignals,
  locationGraph,
  onOpenCharacter,
  onOpenJournal,
  onOpenMap,
  onOpenLoot,
}) {
  const hasLocationGraph = Boolean(locationGraph)
  const locationCount = Array.isArray(locationGraph?.nodes) ? locationGraph.nodes.length : 0
  const mapBadge = hasLocationGraph && locationCount > 0 ? `${locationCount} loc` : ''
  const mapDisabledReason = 'Map appears after the DM records at least one known location.'

  return (
    <div className="adventure-bottom-hud" role="region" aria-label="Adventure status">
      <AdventurePartyHud allMembers={allMembers} onOpenCharacter={onOpenCharacter} />
      <AdventureQuestHud
        questLine={questLine}
        clues={clues}
        npcUpdates={npcUpdates}
        keyDecisions={keyDecisions}
        recentConsequences={recentConsequences}
        companionSignals={companionSignals}
        locationGraph={locationGraph}
        onOpenJournal={onOpenJournal}
      />

      <div className="adventure-bottom-actions" aria-label="Adventure tools">
        <AdventureToolButton
          label="Map"
          hint="Open mapped locations and encounter templates."
          badge={mapBadge}
          disabled={!hasLocationGraph}
          disabledReason={mapDisabledReason}
          onClick={onOpenMap}
        />
        <AdventureToolButton
          label="Loot"
          hint="Open discovered rewards and party distribution."
          onClick={onOpenLoot}
        />
        <AdventureToolButton
          label="Journal"
          hint="Open quests, clues, companions, locations, and decisions."
          onClick={() => onOpenJournal?.()}
        />
      </div>
    </div>
  )
}
