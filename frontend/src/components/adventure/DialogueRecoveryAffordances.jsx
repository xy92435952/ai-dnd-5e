const CONTINUE_TEXT = '继续推进当前场景。'
const ASK_PREFIX = '我想询问：'
const ACT_PREFIX = '我尝试：'

function withPrefix(prefix, input) {
  const trimmed = String(input || '').trim()
  if (!trimmed) return prefix
  if (trimmed.startsWith(prefix)) return trimmed
  return `${prefix}${trimmed}`
}

export default function DialogueRecoveryAffordances({
  input = '',
  setInput,
  inputRef,
  onAction,
  disabled = false,
}) {
  const seedInput = (prefix) => {
    if (disabled) return
    setInput(withPrefix(prefix, input))
    inputRef?.current?.focus?.()
  }

  return (
    <div className="recovery-affordances" role="group" aria-label="回应快捷入口">
      <button
        type="button"
        className="recovery-affordance continue"
        aria-label="继续推进当前场景"
        title="直接请求 DM 继续推进当前场景"
        onClick={() => {
          if (!disabled) onAction(CONTINUE_TEXT, { actionSource: 'system_action' })
        }}
        disabled={disabled}
      >
        <span>▶</span>
        继续
      </button>
      <button
        type="button"
        className="recovery-affordance ask"
        aria-label="提问：填入询问前缀"
        title="在自由行动输入框中填入询问前缀"
        onClick={() => seedInput(ASK_PREFIX)}
        disabled={disabled}
      >
        <span>?</span>
        提问
      </button>
      <button
        type="button"
        className="recovery-affordance act"
        aria-label="行动：填入尝试前缀"
        title="在自由行动输入框中填入尝试行动前缀"
        onClick={() => seedInput(ACT_PREFIX)}
        disabled={disabled}
      >
        <span>!</span>
        行动
      </button>
    </div>
  )
}
