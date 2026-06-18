export default function DialogueFreeSpeak({
  input,
  setInput,
  inputRef,
  onAction,
  isLoading,
  room,
  isMySpeakTurn,
  multiplayerSyncBlocked = false,
}) {
  const disabled = isLoading || (room && (!isMySpeakTurn || multiplayerSyncBlocked))
  const trimmedInput = input.trim()
  const placeholder = isLoading
    ? '✦ 地下城主正在编织命运… ✦'
    : multiplayerSyncBlocked
      ? '正在重新同步房间，恢复后可继续发言…'
      : room && !isMySpeakTurn
        ? '等待发言权…'
        : '描述你的行动，或按上方编号快捷回应'
  const statusText = isLoading
    ? '地下城主正在回应，暂时不能发送自由行动。'
    : multiplayerSyncBlocked
      ? '房间正在重新同步，恢复后可继续发言。'
      : room && !isMySpeakTurn
        ? '等待当前发言者结束回合。'
        : trimmedInput
          ? '自由行动已准备发送。'
          : '输入行动描述后即可发送。'

  return (
    <div className="free-speak" role="group" aria-label="自由行动输入">
      <label className="label" htmlFor="dialogue-free-speak-input">✎ 自由行动</label>
      <span className="free-speak-status" role="status" aria-live="polite">
        {statusText}
      </span>
      <input
        id="dialogue-free-speak-input"
        ref={inputRef}
        value={input}
        onChange={e => setInput(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); if (!disabled) onAction() } }}
        placeholder={placeholder}
        disabled={disabled}
      />
      <button
        type="button"
        className="skill-chip free-speak-send"
        onClick={() => onAction()}
        disabled={disabled || !trimmedInput}
        title={disabled ? statusText : trimmedInput ? '发送自由行动' : '请输入行动描述'}
        aria-label={trimmedInput ? '发送自由行动' : '发送自由行动（需要输入）'}
      >➤ 发送</button>
    </div>
  )
}
