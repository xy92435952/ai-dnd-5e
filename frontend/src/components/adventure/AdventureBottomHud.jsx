/**
 * AdventureBottomHud — 底部队伍、目标与线索条。
 */
import AdventurePartyHud from './AdventurePartyHud'
import AdventureQuestHud from './AdventureQuestHud'

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
        <button className="skill-chip" style={{ padding: '6px 12px', fontSize: 10 }} onClick={onOpenMap} disabled={!locationGraph}>Map</button>
        <button className="skill-chip" style={{ padding: '6px 12px', fontSize: 10 }} onClick={onOpenLoot}>Loot</button>
        <button className="skill-chip" style={{ padding: '6px 12px', fontSize: 10 }} onClick={onOpenJournal}>☰ 卷宗</button>
      </div>
    </div>
  )
}
