export default function SmitePrompt({ open, playerSpellSlots, onSmite, onCancel }) {
  if (!open) return null

  const slotLabels = ['1st','2nd','3rd','4th','5th']
  const availableSlots = [1, 2, 3, 4, 5]
    .filter(level => ((playerSpellSlots || {})[slotLabels[level - 1]] || 0) > 0)
  const getDamageDice = (level) => `${level + 1}d8`

  return (
    <div className="smite-prompt-backdrop">
      <section
        className="smite-prompt-dialog"
        role="dialog"
        aria-modal="true"
        aria-labelledby="smite-prompt-title"
        aria-describedby="smite-prompt-description"
      >
        <h2 id="smite-prompt-title" className="smite-prompt-title">
          命中！是否使用神圣斩击？
        </h2>
        <p id="smite-prompt-description" className="smite-prompt-description">
          消耗 1 环法术位造成 +2d8 辐光伤害（每升一环 +1d8）
        </p>
        {availableSlots.length > 0 && (
          <div className="smite-prompt-actions" role="list" aria-label="可用神圣斩击法术位">
            {availableSlots.map(level => {
              const slotLabel = `使用 ${level} 环法术位发动神圣斩击，额外 ${getDamageDice(level)} 辐光伤害`
              return (
                <div
                  key={level}
                  className="smite-prompt-action-item"
                  role="listitem"
                  aria-label={slotLabel}
                >
                  <button
                    type="button"
                    className="btn-gold smite-prompt-slot"
                    onClick={() => onSmite(level)}
                    aria-label={slotLabel}
                  >
                    <span>{level}环</span>
                    <span className="smite-prompt-dice">+{getDamageDice(level)}</span>
                  </button>
                </div>
              )
            })}
          </div>
        )}
        {availableSlots.length === 0 && (
          <div className="smite-prompt-status" role="status" aria-live="polite">
            没有可用法术位，无法发动神圣斩击。
          </div>
        )}
        <button type="button" className="btn-ghost smite-prompt-cancel" onClick={onCancel}>
          取消
        </button>
      </section>
    </div>
  )
}
