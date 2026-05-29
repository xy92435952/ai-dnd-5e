export default function IsoBattlefieldCell({
  className,
  gridKey,
  onClick,
  onMouseEnter,
  onMouseLeave,
  children,
}) {
  return (
    <div
      className={className}
      data-grid-key={gridKey}
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    >
      {children}
    </div>
  )
}
