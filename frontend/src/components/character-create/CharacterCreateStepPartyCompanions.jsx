import React from 'react'
import Portrait from '../Portrait'
import { classKey } from '../Crests'

export default function CharacterCreateStepPartyCompanions({ companions, generatingParty, handleGenerateParty, error }) {
  return (
    <>
      {generatingParty ? (
        <div style={{ textAlign: 'center', padding: '32px 0' }}>
          <p style={{ color: 'var(--amber)', animation: 'pulse 2s infinite', fontFamily: 'var(--font-script)', fontStyle: 'italic' }}>
            ✦ AI 正在为你召唤伙伴… ✦
          </p>
          <p style={{ fontSize: 12, color: 'var(--parchment-dark)', marginTop: 8 }}>
            根据你的职业分析队伍需求
          </p>
        </div>
      ) : (
        <div className="companions-grid">
          {companions.map(c => (
            <div key={c.id} className="companion-card">
              <Portrait cls={classKey(c.char_class)} size="md" />
              <div className="cc-info">
                <div className="cc-name">{c.name}</div>
                <div className="cc-sub">{c.race} · {c.char_class} · Lv {c.level || 1}</div>
                {c.personality && (
                  <div className="cc-role" style={{
                    overflow: 'hidden',
                    textOverflow: 'ellipsis',
                    display: '-webkit-box',
                    WebkitLineClamp: 2,
                    WebkitBoxOrient: 'vertical',
                  }}>
                    {c.personality}
                  </div>
                )}
              </div>
            </div>
          ))}
        </div>
      )}

      {!generatingParty && companions.length > 0 && (
        <div style={{ textAlign: 'center', marginTop: 16 }}>
          <button
            className="btn-ghost"
            style={{ fontSize: 11, padding: '6px 16px' }}
            onClick={() => handleGenerateParty()}
          >
            🔄 重新生成队伍
          </button>
        </div>
      )}

      {error && (
        <p style={{
          color: '#ffaaaa',
          fontSize: 12,
          marginTop: 12,
          padding: 8,
          background: 'rgba(139,32,32,.2)',
          border: '1px solid var(--blood)',
          borderRadius: 4,
          textAlign: 'center',
        }}>
          ! {error}
        </p>
      )}
    </>
  )
}
