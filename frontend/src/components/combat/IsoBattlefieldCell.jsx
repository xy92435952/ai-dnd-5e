export default function IsoBattlefieldCell({
  className,
  onClick,
  onMouseEnter,
  onMouseLeave,
  children,
}) {
  return (
    <div
      className={className}
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    >
      {children}
    </div>
  )
}
