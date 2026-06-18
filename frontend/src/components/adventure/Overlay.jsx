/**
 * Overlay — Adventure 场景下通用的居中弹窗外壳。
 *
 * 点击背景遮罩关闭；内部面板拦截点击以免穿透。
 * 由 RestModal / JournalModal / PrepareSpellsModal 共用。
 */
export default function Overlay({ children, onClose }) {
  return (
    <div
      className="adventure-overlay-backdrop"
      role="presentation"
      onClick={onClose}
    >
      <div
        onClick={e => e.stopPropagation()}
        className="panel adventure-overlay-panel"
        role="document"
      >
        {children}
      </div>
    </div>
  )
}
