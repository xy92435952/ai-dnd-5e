import { JuiceAudio } from '../../juice'
import { computeChoicePreview, KIND_TO_SKILL_ZH } from '../../utils/skillCheck'

export default function DialogueChoices({
  choices,
  player,
  setPendingCheck,
  onAction,
  disabled,
}) {
  if (choices.length <= 0) return null

  return (
    <div className="choice-list">
      {choices.slice(0, 9).map((c, i) => {
        const obj = typeof c === 'string' ? { text: c, tags: [] } : c
        const preview = computeChoicePreview(obj, player)
        return (
          <button
            key={i}
            className={`choice ${obj.action ? 'action' : ''} ${obj.ended ? 'ended' : ''}`}
            onMouseEnter={() => { try { JuiceAudio.hover() } catch {} }}
            onClick={() => {
              try { JuiceAudio.select() } catch {}
              const checkTag = obj.skill_check
                ? (obj.tags || []).find(t => t.dc != null)
                : null
              if (checkTag && checkTag.dc != null) {
                const kind = (checkTag.kind || 'check').toLowerCase()
                const skillZh = KIND_TO_SKILL_ZH[kind] || checkTag.label || '检定'
                setPendingCheck({
                  check_type: skillZh,
                  dc: Number(checkTag.dc),
                  character_id: player?.id,
                  context: obj.text,
                })
                return
              }
              onAction(obj.text, { actionSource: 'ai_generated_choice' })
            }}
            disabled={disabled}
          >
            <span className="idx">{i + 1}</span>
            <span className="body">
              {obj.tags?.length > 0 && (
                <span className="tags">
                  {obj.tags.map((t, ti) => (
                    <span key={ti} className={`tag-mini tm-${t.kind || 'check'}`}>
                      [{t.label}{t.dc ? ` · DC${t.dc}` : ''}]
                    </span>
                  ))}
                </span>
              )}
              <span>{obj.text}</span>
              {obj.skill_check && (
                <span style={{ marginLeft: 8, fontSize: 10, color: 'var(--parchment-dark)' }}>🎲</span>
              )}
            </span>
            {preview && (
              <div className="choice-preview">
                <div className="pv-title">⚖ 结果预告</div>
                {preview.rows.map((r, ri) => (
                  <div key={ri} className="pv-row">
                    <span>{r.label}</span>
                    <b>{r.value}</b>
                  </div>
                ))}
                {preview.hint && (
                  <div style={{ marginTop: 6, paddingTop: 6, borderTop: '1px dashed rgba(138,90,24,.4)',
                                fontSize: 10, color: 'rgba(232,200,160,.7)', fontStyle: 'italic' }}>
                    {preview.hint}
                  </div>
                )}
              </div>
            )}
          </button>
        )
      })}
    </div>
  )
}
