import React from 'react'
import {
  ABILITY_KEYS,
  POINT_BUY_TOTAL,
  SCORE_COSTS,
  STANDARD_ARRAY,
  modifier,
  modStr,
} from '../../utils/characterCreate'
import { ABILITY_ZH, CLASS_INFO } from '../../data/dnd5e.js'

export default function CharacterCreateStepAbilities({ ctx }) {
  const {
    form,
    setScoreMethod,
    scoreMethod,
    pointsLeft,
    baseScores,
    racialBonuses,
    finalScores,
    adjustScore,
    assignStandard,
    standardAssigned,
    multiReqs,
    multiReqMet,
    multiclassEnKey,
  } = ctx

  return (
    <div className="step-pane">
      <div className="step-title">✧ 第二章 · 天赋与禀性 ✧</div>
      <div className="step-sub">六项能力决定你能做什么、擅长什么。</div>

      <div className="method-tabs">
        {[
          ['pointbuy', '点数购买', `更自由 · ${POINT_BUY_TOTAL} 点`],
          ['standard', '标准数组', `经典 · ${STANDARD_ARRAY.join('/')}`],
        ].map(([k, n, d]) => (
          <div
            key={k}
            className={`method-tab ${scoreMethod === k ? 'sel' : ''}`}
            onClick={() => { setScoreMethod(k); ctx.setStandardAssigned({}) }}
          >
            <div className="n">{n}</div>
            <div className="d">{d}</div>
          </div>
        ))}
      </div>

      {scoreMethod === 'pointbuy' && (
        <div className="points-bar">
          <div className="label">剩余点数</div>
          <div className="points-big" style={{ color: pointsLeft === 0 ? 'var(--emerald-light)' : 'var(--amber)' }}>
            {pointsLeft}
          </div>
          <div className="track">
            <div
              className="fill"
              style={{
                width: `${((POINT_BUY_TOTAL - pointsLeft) / POINT_BUY_TOTAL) * 100}%`,
                background: pointsLeft === 0 ? 'var(--emerald-light)' : 'var(--gold-gradient)',
              }}
            />
          </div>
          <div className="label">
            {pointsLeft === 0 ? '✓ 已分配完毕' : `${POINT_BUY_TOTAL - pointsLeft} / ${POINT_BUY_TOTAL}`}
          </div>
        </div>
      )}

      <div className="ability-grid">
        {ABILITY_KEYS.map(key => {
          const base = baseScores[key]
          const bonus = racialBonuses[key] || 0
          const final = finalScores[key]
          const mod = modifier(final)
          return (
            <div key={key} className="ability-plaque">
              <div className="plaque-top">
                <div className="ab-name">{ABILITY_ZH[key] || key}</div>
                <div className="ab-key">{key.toUpperCase()}</div>
              </div>
              <div className="plaque-main">
                <div className="score">{final}</div>
                <div className="mod">{modStr(mod)}</div>
              </div>
              {bonus > 0 && (
                <div className="bonus-badge">基础 {base} · 种族 +{bonus}</div>
              )}
              {scoreMethod === 'pointbuy' && (
                <div className="adj">
                  <button onClick={() => adjustScore(key, -1)} disabled={base <= 8}>−</button>
                  <div className="val">{base}</div>
                  <button
                    onClick={() => adjustScore(key, 1)}
                    disabled={base >= 15 || pointsLeft < (SCORE_COSTS[base + 1] - SCORE_COSTS[base])}
                  >
                    +
                  </button>
                </div>
              )}
              {scoreMethod === 'standard' && (
                <div className="array-row">
                  {STANDARD_ARRAY.map((v, idx) => {
                    const used = Object.entries(standardAssigned).some(([a, i]) => a !== key && i === idx)
                    const sel = standardAssigned[key] === idx
                    return (
                      <button
                        key={idx}
                        disabled={used}
                        className={`arr ${sel ? 'sel' : ''}`}
                        onClick={() => assignStandard(key, idx)}
                      >
                        {v}
                      </button>
                    )
                  })}
                </div>
              )}
            </div>
          )
        })}
      </div>

      {form.char_class && (() => {
        const prof = 2 + Math.floor((form.level - 1) / 4)
        const conMod = modifier(finalScores.con || 10)
        const dexMod = modifier(finalScores.dex || 10)
        const strMod = modifier(finalScores.str || 10)
        const hitDie = CLASS_INFO[ctx.classEnKey]?.hit_die || 8
        const hp = hitDie + conMod + Math.max(0, form.level - 1) * (Math.floor(hitDie / 2) + 1 + conMod)
        return (
          <div className="derived-row">
            <div className="der"><div className="t">最大生命</div><div className="v">{Math.max(1, hp)}</div></div>
            <div className="der"><div className="t">先攻</div><div className="v">{modStr(dexMod)}</div></div>
            <div className="der"><div className="t">熟练</div><div className="v">+{prof}</div></div>
            <div className="der"><div className="t">攻击</div><div className="v">{modStr(prof + Math.max(strMod, dexMod))}</div></div>
            <div className="der"><div className="t">AC</div><div className="v">{10 + dexMod}</div></div>
          </div>
        )
      })()}

      {form.multiclassEnabled && form.multiclass_class && Object.keys(multiReqs).length > 0 && (
        <div
          style={{
            fontSize: '0.75rem',
            padding: '8px',
            borderRadius: '6px',
            background: multiReqMet ? 'rgba(42,90,42,0.12)' : 'rgba(139,32,32,0.12)',
            border: `1px solid ${multiReqMet ? 'var(--green)' : 'var(--red)'}`,
          }}
        >
          <span style={{ color: multiReqMet ? 'var(--green-light)' : 'var(--red-light)' }}>
            双职业（{CLASS_INFO[multiclassEnKey]?.zh || form.multiclass_class}）要求：
          </span>
          {Object.entries(multiReqs).map(([ab, min]) => {
            const met = (finalScores[ab] || 0) >= min
            return (
              <span key={ab} style={{ marginLeft: '8px', color: met ? 'var(--green-light)' : 'var(--red-light)' }}>
                {ABILITY_ZH[ab] || ab}&gt;={min}（{finalScores[ab] || 8}）
              </span>
            )
          })}
        </div>
      )}
    </div>
  )
}
