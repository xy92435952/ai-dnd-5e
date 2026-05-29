export default function IsoBattlefieldCell({
  className,
  gridKey,
  onClick,
  onMouseEnter,
  onMouseLeave,
  title = '',
  interactive = false,
  disabledReason = '',
  children,
}) {
  const isDisabled = Boolean(disabledReason)

  return (
    <div
      className={className}
      data-grid-key={gridKey}
      role={interactive || isDisabled ? 'button' : undefined}
      tabIndex={interactive && !isDisabled ? 0 : undefined}
      aria-disabled={isDisabled || undefined}
      title={disabledReason || title}
      onClick={isDisabled ? undefined : onClick}
      onKeyDown={(event) => {
        if (!interactive || isDisabled) return
        if (event.key === 'Enter' || event.key === ' ') {
          event.preventDefault()
          onClick?.(event)
        }
      }}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    >
      {children}
    </div>
  )
}
