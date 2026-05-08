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
  onOpenCharacter,
  onOpenJournal,
}) {
  return (
    <div style={{
      display: 'grid',
      gridTemplateColumns: 'auto 1fr auto',
      gap: 12,
      padding: '10px 20px 12px',
      background: 'linear-gradient(180deg, transparent, rgba(10,6,4,.95) 40%, rgba(10,6,4,1) 100%)',
      borderTop: '1px solid rgba(138,90,24,.5)',
      boxShadow: 'inset 0 1px 0 rgba(240,208,96,.15)',
      flexShrink: 0,
    }}>
      <AdventurePartyHud allMembers={allMembers} onOpenCharacter={onOpenCharacter} />
      <AdventureQuestHud
        questLine={questLine}
        clues={clues}
        npcUpdates={npcUpdates}
        keyDecisions={keyDecisions}
      />

      <div style={{ display: 'flex', gap: 4 }}>
        <button className="skill-chip" style={{ padding: '6px 12px', fontSize: 10 }} onClick={onOpenJournal}>☰ 卷宗</button>
      </div>
    </div>
  )
}
