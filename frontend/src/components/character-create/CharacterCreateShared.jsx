import {
  BACKGROUND_INFO,
  CLASS_INFO,
  SKILL_INFO,
  RACE_INFO,
  ABILITY_ZH,
} from '../../data/dnd5e.js'

export function CharacterCreateInfoModal({ type, itemKey, onClose }) {
  if (!itemKey || !type) return null

  let title = ''
  let body = null

  if (type === 'race') {
    const info = RACE_INFO[itemKey]
    if (!info) return null
    title = info.zh
    body = (
      <div id="create-info-modal-desc" className="create-info-modal-body">
        <p className="create-info-modal-copy">{info.description}</p>
        <div className="create-info-modal-tag-row" aria-label="Race summary">
          <span className="tag tag-info">速度 {info.speed}尺</span>
          <span className="tag tag-info">体型 {info.size}</span>
        </div>
        <p className="create-info-modal-section-title">种族特性</p>
        <div className="create-info-modal-item-list" role="list" aria-label="Race traits">
          {info.traits.map((t, i) => (
            <div key={i} className="create-info-modal-item" role="listitem">
              <span className="create-info-modal-item-name">{t.name}：</span>
              <span className="create-info-modal-item-copy">{t.desc}</span>
            </div>
          ))}
        </div>
        <div className="create-info-modal-note">
          <p className="create-info-modal-note-copy">提示：{info.playstyle}</p>
        </div>
      </div>
    )
  } else if (type === 'class') {
    const info = CLASS_INFO[itemKey]
    if (!info) return null
    title = info.zh
    body = (
      <div id="create-info-modal-desc" className="create-info-modal-body">
        <div className="create-info-modal-tag-row" aria-label="Class summary">
          <span className="tag tag-level">生命骰 {info.hit_die}</span>
          <span className="tag tag-ok">{info.primary_ability}</span>
        </div>
        <p className="create-info-modal-copy">{info.description}</p>
        <p className="create-info-modal-meta">
          护甲: {info.armor} | 武器: {info.weapons}
        </p>
        <p className="create-info-modal-section-title">职业特性</p>
        <div className="create-info-modal-item-list" role="list" aria-label="Class features">
          {info.features.map((f, i) => (
            <div key={i} className="create-info-modal-item" role="listitem">
              <span className="create-info-modal-level">Lv{f.level} </span>
              <span className="create-info-modal-item-name">{f.name}：</span>
              <span className="create-info-modal-item-copy">{f.desc}</span>
            </div>
          ))}
        </div>
        {info.subclasses?.length > 0 && (
          <>
            <p className="create-info-modal-section-title create-info-modal-section-title-spaced">
              {info.subclass_label}（{info.subclass_unlock}级解锁）
            </p>
            <div className="create-info-modal-item-list" role="list" aria-label="Subclass options">
              {info.subclasses.map((s, i) => (
                <div key={i} className="create-info-modal-item" role="listitem">
                  <span className="create-info-modal-item-name">{s.zh}：</span>
                  <span className="create-info-modal-item-copy">{s.description}</span>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    )
  } else if (type === 'skill') {
    const info = SKILL_INFO[itemKey]
    if (!info) return null
    title = `${itemKey}（${info.en}）`
    body = (
      <div id="create-info-modal-desc" className="create-info-modal-body">
        <span className="tag tag-level create-info-modal-inline-tag">
          关联属性：{ABILITY_ZH[info.ability] || info.ability}
        </span>
        <p className="create-info-modal-copy">{info.desc}</p>
      </div>
    )
  } else if (type === 'background') {
    const info = BACKGROUND_INFO[itemKey]
    if (!info) return null
    title = info.zh
    body = (
      <div id="create-info-modal-desc" className="create-info-modal-body">
        <p className="create-info-modal-copy">{info.desc}</p>
      </div>
    )
  }

  if (!body) return null

  return (
    <div
      className="create-info-modal-backdrop"
      role="dialog"
      aria-modal="true"
      aria-labelledby="create-info-modal-title"
      aria-describedby="create-info-modal-desc"
      onClick={onClose}
    >
      <div
        className="panel create-info-modal-panel"
        onClick={(e) => e.stopPropagation()}
      >
        <h3 id="create-info-modal-title" className="create-info-modal-title">
          {title}
        </h3>
        {body}
        <button
          type="button"
          className="create-info-modal-close"
          aria-label="Close details"
          onClick={onClose}
        >
          &#x2715;
        </button>
      </div>
    </div>
  )
}

export function CharacterCreateInfoBtn({ onClick }) {
  return (
    <button
      type="button"
      className="create-shared-info-button"
      onClick={onClick}
      title="查看详情"
    >
      &#x2139;
    </button>
  )
}

export function CharacterCreateField({ label, children }) {
  return (
    <div className="create-shared-field">
      <label className="create-shared-field-label">
        {label}
      </label>
      {children}
    </div>
  )
}

export function CharacterCreateSelect({ value, options, placeholder, onChange }) {
  return (
    <select
      className="input-fantasy create-shared-select"
      data-selected={value ? 'true' : 'false'}
      value={value}
      onChange={(e) => onChange(e.target.value)}
    >
      <option value="">{placeholder}</option>
      {options.map((o) => (
        <option key={o} value={o} className="create-shared-select-option">
          {o}
        </option>
      ))}
    </select>
  )
}
