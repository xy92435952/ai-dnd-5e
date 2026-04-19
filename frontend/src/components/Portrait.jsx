/**
 * Portrait — 职业纹章肖像
 * size: sm / md(default) / lg / xl
 * wounded: 受伤时加红光晕（HP < 35%）
 *
 * 使用 components.css 提供的 .portrait + .portrait-{cls} 样式
 */
import { Crest, classKey } from './Crests'

export default function Portrait({ cls = 'fighter', size = 'md', wounded = false, style, onClick }) {
  const key = classKey(cls)
  const sizeClass = { sm: 'portrait-sm', md: '', lg: 'portrait-lg', xl: 'portrait-xl' }[size] || ''
  return (
    <div
      className={`portrait portrait-${key} ${sizeClass} ${wounded ? 'is-wounded' : ''}`}
      style={style}
      onClick={onClick}
    >
      {Crest[key] || Crest.fighter}
    </div>
  )
}
