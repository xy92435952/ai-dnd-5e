/**
 * Overlay — Adventure 场景下通用的居中弹窗外壳。
 *
 * 点击背景遮罩关闭；内部面板拦截点击以免穿透。
 * 由 RestModal / JournalModal / PrepareSpellsModal 共用。
 */
export default function Overlay({ children, onClose }) {
  return (
    <div
      onClick={onClose}
      style={{
        position: 'fixed', inset: 0, zIndex: 500,
        background: 'rgba(0,0,0,0.75)',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}
    >
      <div
        onClick={e => e.stopPropagation()}
        className="panel"
        style={{
          padding: 24,
          width: 500, maxWidth: '90vw', maxHeight: '85vh',
          display: 'flex', flexDirection: 'column', gap: 16,
          borderColor: 'var(--bark-light)',
        }}
      >
        {children}
      </div>
    </div>
  )
}
