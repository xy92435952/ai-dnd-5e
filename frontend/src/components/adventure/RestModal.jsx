/**
 * RestModal — 休息选择弹窗（长休 / 短休）。
 *
 * Props:
 *   onRest  - (rest_type: 'long' | 'short') => void
 *   onClose - () => void
 */
import Overlay from './Overlay'
import { RestIcon } from '../Icons'

export default function RestModal({ onRest, onClose }) {
  return (
    <Overlay onClose={onClose}>
      <h3 style={{ color: 'var(--amber)', margin: 0, fontSize: 16, display: 'flex', alignItems: 'center', gap: 6 }}>
        <RestIcon size={18} color="var(--amber)" /> 休息
      </h3>
      <button className="btn-fantasy" style={{ padding: 14, textAlign: 'left' }} onClick={() => onRest('long')}>
        <div style={{ fontWeight: 700, marginBottom: 4 }}>🌙 长休（8小时）</div>
        <div style={{ fontSize: 12, opacity: 0.6 }}>HP 全满 · 法术位全恢复 · 清除大多数状态条件</div>
      </button>
      <button className="btn-fantasy" style={{ padding: 14, textAlign: 'left' }} onClick={() => onRest('short')}>
        <div style={{ fontWeight: 700, marginBottom: 4 }}>☕ 短休（1小时）</div>
        <div style={{ fontSize: 12, opacity: 0.6 }}>消耗一颗生命骰恢复 HP · 魔契者恢复法术位</div>
      </button>
      <button className="btn-fantasy" style={{ padding: 8, opacity: 0.6 }} onClick={onClose}>取消</button>
    </Overlay>
  )
}
