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
      <>
        <p style={{ color: 'var(--text)', opacity: 0.75, fontSize: '0.875rem', lineHeight: 1.7, marginBottom: '0.75rem' }}>{info.description}</p>
        <div style={{ marginBottom: '0.75rem', display: 'flex', gap: '0.3rem', flexWrap: 'wrap' }}>
          <span className="tag tag-info">速度 {info.speed}尺</span>
          <span className="tag tag-info">体型 {info.size}</span>
        </div>
        <p style={{ color: 'var(--gold)', fontSize: '0.8rem', fontWeight: 'bold', marginBottom: '0.4rem' }}>种族特性</p>
        {info.traits.map((t, i) => (
          <div key={i} style={{ marginBottom: '0.4rem', paddingLeft: '0.6rem', borderLeft: '2px solid var(--wood-light)' }}>
            <span style={{ color: 'var(--text-bright)', fontSize: '0.85rem', fontWeight: 600 }}>{t.name}：</span>
            <span style={{ color: 'var(--text)', opacity: 0.65, fontSize: '0.8rem' }}>{t.desc}</span>
          </div>
        ))}
        <div style={{ marginTop: '0.75rem', padding: '0.6rem', borderRadius: '0.4rem', background: 'rgba(42,90,42,0.12)', border: '1px solid var(--green)' }}>
          <p style={{ color: 'var(--green-light)', fontSize: '0.8rem' }}>提示：{info.playstyle}</p>
        </div>
      </>
    )
  } else if (type === 'class') {
    const info = CLASS_INFO[itemKey]
    if (!info) return null
    title = info.zh
    body = (
      <>
        <div style={{ marginBottom: '0.6rem', display: 'flex', gap: '0.3rem', flexWrap: 'wrap' }}>
          <span className="tag tag-level">生命骰 {info.hit_die}</span>
          <span className="tag tag-ok">{info.primary_ability}</span>
        </div>
        <p style={{ color: 'var(--text)', opacity: 0.75, fontSize: '0.875rem', lineHeight: 1.7, marginBottom: '0.6rem' }}>{info.description}</p>
        <p style={{ color: 'var(--text-dim)', fontSize: '0.75rem', marginBottom: '0.75rem' }}>
          护甲: {info.armor} | 武器: {info.weapons}
        </p>
        <p style={{ color: 'var(--gold)', fontSize: '0.8rem', fontWeight: 'bold', marginBottom: '0.4rem' }}>职业特性</p>
        {info.features.map((f, i) => (
          <div key={i} style={{ marginBottom: '0.35rem', paddingLeft: '0.6rem', borderLeft: '2px solid var(--wood-light)' }}>
            <span style={{ color: 'var(--gold)', fontSize: '0.72rem', opacity: 0.8 }}>Lv{f.level} </span>
            <span style={{ color: 'var(--text-bright)', fontSize: '0.82rem', fontWeight: 600 }}>{f.name}：</span>
            <span style={{ color: 'var(--text)', opacity: 0.65, fontSize: '0.78rem' }}>{f.desc}</span>
          </div>
        ))}
        {info.subclasses?.length > 0 && (
          <>
            <p style={{ color: 'var(--gold)', fontSize: '0.8rem', fontWeight: 'bold', margin: '0.75rem 0 0.4rem' }}>
              {info.subclass_label}（{info.subclass_unlock}级解锁）
            </p>
            {info.subclasses.map((s, i) => (
              <div key={i} style={{ marginBottom: '0.35rem', paddingLeft: '0.6rem', borderLeft: '2px solid var(--wood-light)' }}>
                <span style={{ color: 'var(--text-bright)', fontSize: '0.82rem', fontWeight: 600 }}>{s.zh}：</span>
                <span style={{ color: 'var(--text)', opacity: 0.65, fontSize: '0.78rem' }}>{s.description}</span>
              </div>
            ))}
          </>
        )}
      </>
    )
  } else if (type === 'skill') {
    const info = SKILL_INFO[itemKey]
    if (!info) return null
    title = `${itemKey}（${info.en}）`
    body = (
      <>
        <span className="tag tag-level" style={{ marginBottom: '0.75rem', display: 'inline-flex' }}>
          关联属性：{ABILITY_ZH[info.ability] || info.ability}
        </span>
        <p style={{ color: 'var(--text)', opacity: 0.75, fontSize: '0.875rem', lineHeight: 1.7 }}>{info.desc}</p>
      </>
    )
  } else if (type === 'background') {
    const info = BACKGROUND_INFO[itemKey]
    if (!info) return null
    title = info.zh
    body = <p style={{ color: 'var(--text)', opacity: 0.75, fontSize: '0.875rem', lineHeight: 1.7 }}>{info.desc}</p>
  }

  if (!body) return null

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        zIndex: 999,
        background: 'rgba(0,0,0,0.72)',
        backdropFilter: 'blur(2px)',
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        padding: '1rem',
      }}
      onClick={onClose}
    >
      <div
        className="panel"
        style={{
          padding: '1.5rem',
          maxWidth: '480px',
          width: '100%',
          maxHeight: '80vh',
          overflowY: 'auto',
          position: 'relative',
        }}
        onClick={(e) => e.stopPropagation()}
      >
        <h3 style={{ color: 'var(--gold)', fontSize: '1.1rem', fontWeight: 'bold', marginBottom: '1rem', paddingRight: '2rem' }}>
          {title}
        </h3>
        {body}
        <button
          onClick={onClose}
          style={{
            position: 'absolute',
            top: '0.75rem',
            right: '0.75rem',
            background: 'none',
            border: 'none',
            color: 'var(--text-dim)',
            cursor: 'pointer',
            fontSize: '1.1rem',
          }}
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
