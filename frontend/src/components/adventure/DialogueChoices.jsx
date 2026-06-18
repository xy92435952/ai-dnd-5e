import { JuiceAudio } from '../../juice'
import { getChoiceIntent, getChoiceLocationExit } from '../../utils/adventureChoices'
import { computeChoicePreview, getChoiceCheckTag, KIND_TO_SKILL_ZH } from '../../utils/skillCheck'

export default function DialogueChoices({
  choices,
  player,
  setPendingCheck,
  onAction,
  disabled,
}) {
  if (choices.length <= 0) return null

  return (
    <div className="choice-list" role="list" aria-label="可选行动">
      {choices.slice(0, 9).map((c, i) => {
        const obj = typeof c === 'string' ? { text: c, tags: [] } : c
        const preview = computeChoicePreview(obj, player)
        const intent = getChoiceIntent(obj)
        const locationExit = getChoiceLocationExit(obj)
        const choiceId = `dialogue-choice-${i + 1}`
        const previewId = preview ? `${choiceId}-preview` : undefined
        const exitId = locationExit ? `${choiceId}-exit` : undefined
        const describedBy = [exitId, previewId].filter(Boolean).join(' ') || undefined
        return (
          <div key={i} className="choice-list-item" role="listitem">
            <button
              className={`choice choice-intent-${intent.type} ${obj.action ? 'action' : ''} ${obj.ended ? 'ended' : ''}`}
              aria-describedby={describedBy}
              title={preview ? `${preview.summary.skill} · DC ${preview.summary.dc} · ${preview.summary.risk} · ${preview.summary.success}` : undefined}
              onMouseEnter={() => { try { JuiceAudio.hover() } catch {} }}
              onClick={() => {
                try { JuiceAudio.select() } catch {}
                const checkTag = getChoiceCheckTag(obj)
                if (checkTag && checkTag.dc != null) {
                  const kind = String(checkTag.kind || 'check').toLowerCase()
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
                <span className="choice-mainline">
                  <span className={`choice-intent-badge ${intent.type}`}>{intent.label}</span>
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
                  {obj.skill_check && !preview && (
                    <span className="choice-check-flag">检定</span>
                  )}
                </span>

                {locationExit && (
                  <span id={exitId} className={`choice-exit-summary ${locationExit.tone}`} aria-label="地图出口">
                    <span>出口</span>
                    <b>{locationExit.destination}</b>
                    {locationExit.flags.map(flag => <em key={flag}>{flag}</em>)}
                  </span>
                )}

                {preview && (
                  <span id={previewId} className="choice-check-summary" aria-label="技能检定预览">
                    <span className="choice-check-pill skill">
                      <span>技能</span><b>{preview.summary.skill}</b>
                    </span>
                    <span className="choice-check-pill ability">
                      <span>属性</span><b>{preview.summary.ability}</b>
                    </span>
                    <span className="choice-check-pill dc">
                      <span>难度</span><b>DC {preview.summary.dc}</b>
                    </span>
                    <span className={`choice-check-pill risk ${preview.summary.riskTone}`}>
                      <span>风险</span><b>{preview.summary.risk} · {preview.summary.success}</b>
                    </span>
                  </span>
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
                    <div className="choice-preview-hint">
                      {preview.hint}
                    </div>
                  )}
                </div>
              )}
            </button>
          </div>
        )
      })}
    </div>
  )
}
