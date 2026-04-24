/**
 * JournalModal — 生成 / 展示冒险日志的弹窗。
 *
 * Props:
 *   text       - 当前日志文本（可为空）
 *   loading    - 生成中标志
 *   onGenerate - () => void 重新生成
 *   onClose    - () => void
 */
import Overlay from './Overlay'
import { JournalIcon } from '../Icons'

export default function JournalModal({ text, loading, onGenerate, onClose }) {
  return (
    <Overlay onClose={onClose}>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <h3 style={{ color: 'var(--amber)', margin: 0, display: 'flex', alignItems: 'center', gap: 6 }}>
          <JournalIcon size={18} color="var(--amber)" /> 冒险日志
        </h3>
        <button onClick={onClose} style={{ color: 'var(--parchment-dark)', fontSize: 22, background: 'none', border: 'none', cursor: 'pointer' }}>×</button>
      </div>
      <div style={{ flex: 1, overflowY: 'auto', minHeight: 200, maxHeight: '55vh', background: '#0a0604', borderRadius: 8, padding: 16, border: '1px solid var(--bark)' }}>
        {loading ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: 'var(--amber)' }}>
            DM 正在撰写日志...
          </div>
        ) : text ? (
          <p style={{ color: 'var(--parchment)', lineHeight: 1.9, fontSize: 14, whiteSpace: 'pre-wrap', margin: 0 }}>{text}</p>
        ) : (
          <p style={{ color: 'var(--parchment-dark)', textAlign: 'center', marginTop: 32, fontSize: 13 }}>
            点击下方按钮生成本次冒险的叙述日志
          </p>
        )}
      </div>
      <div style={{ display: 'flex', justifyContent: 'flex-end', gap: 8 }}>
        <button className="btn-fantasy" style={{ padding: '8px 16px', fontSize: 13 }} onClick={onGenerate} disabled={loading}>
          {loading ? '生成中...' : '🔄 重新生成'}
        </button>
        <button className="btn-fantasy" style={{ padding: '8px 16px', fontSize: 13 }} onClick={onClose}>关闭</button>
      </div>
    </Overlay>
  )
}
