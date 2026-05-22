export default function IsoBattlefieldCell({
  testId,
  className,
  onClick,
  onMouseEnter,
  onMouseLeave,
  children,
}) {
  return (
    <div
      data-testid={testId}
      className={className}
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    >
      {children}
    </div>
  )
}
