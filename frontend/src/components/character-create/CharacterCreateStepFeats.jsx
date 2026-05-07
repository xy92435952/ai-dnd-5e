import React from 'react'

export default function CharacterCreateStepFeats({ ctx }) {
  const {
    form,
    needsASI,
    asiCount,
    asiLevels,
    chosenFeats,
    setChosenFeats,
    options,
  } = ctx

  if (!needsASI) return null

  return (
    <div className="step-pane">
      <div className="step-title">✧ 第六章 · 淬炼与专长 ✧</div>
      <div className="step-sub">
        Lv{form.level} — {asiCount} 次属性提升 (ASI) 或专长选择
      </div>
      {Array.from({ length: asiCount }, (_, i) => {
        const feat = chosenFeats[i]
        const isASI = feat?.name === '__ASI__'
        return (
          <div
            key={i}
            style={{
              padding: '12px 16px',
              borderRadius: '8px',
              border: '1px solid var(--wood-light)',
              background: 'rgba(10,8,6,0.3)',
            }}
          >
            <p style={{ fontSize: '0.8rem', color: 'var(--text-bright)', marginBottom: '8px', fontWeight: 600 }}>
              第 {i + 1} 次选择（Lv {asiLevels[i]}）
            </p>
            <div style={{ display: 'flex', gap: '8px', marginBottom: '8px' }}>
              <button
                className={isASI ? 'btn-gold' : 'btn-fantasy'}
                style={{ flex: 1, padding: '6px 12px', fontSize: '0.75rem' }}
                onClick={() => {
                  const next = [...chosenFeats]
                  next[i] = { name: '__ASI__', desc: '两项属性各+1' }
                  setChosenFeats(next)
                }}
              >
                +2 属性提升
              </button>
              <button
                className={(feat && !isASI) ? 'btn-gold' : 'btn-fantasy'}
                style={{ flex: 1, padding: '6px 12px', fontSize: '0.75rem' }}
                onClick={() => {
                  const usedNames = chosenFeats.filter(f => f && f.name !== '__ASI__').map(f => f.name)
                  const available = Object.keys(options.feats || {}).filter(n => !usedNames.includes(n))
                  if (available.length > 0) {
                    const next = [...chosenFeats]
                    next[i] = { name: available[0] }
                    setChosenFeats(next)
                  }
                }}
              >
                选择专长
              </button>
            </div>
            {feat && !isASI && (
              <div>
                <select
                  value={feat.name}
                  className="input-fantasy"
                  style={{ marginBottom: '4px' }}
                  onChange={e => {
                    const next = [...chosenFeats]
                    next[i] = { name: e.target.value }
                    setChosenFeats(next)
                  }}
                >
                  {Object.entries(options.feats || {}).map(([name, info]) => (
                    <option key={name} value={name}>
                      {info.zh || name} -- {info.desc?.slice(0, 30)}
                    </option>
                  ))}
                </select>
                <p style={{ fontSize: '0.7rem', color: 'var(--text-dim)', marginTop: '4px' }}>
                  {(options.feats || {})[feat.name]?.desc}
                </p>
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}
