export default function DialogueFreeSpeak({
  input,
  setInput,
  inputRef,
  onAction,
  isLoading,
  room,
  isMySpeakTurn,
}) {
  const disabled = isLoading || (room && !isMySpeakTurn)

  return (
    <div className="free-speak">
      <span className="label">✎ 自由行动</span>
      <input
        ref={inputRef}
        value={input}
        onChange={e => setInput(e.target.value)}
        onKeyDown={e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); onAction() } }}
        placeholder={isLoading ? '✦ 地下城主正在编织命运… ✦' : (room && !isMySpeakTurn ? '等待发言权…' : '描述你的行动，或按上方编号快捷回应')}
        disabled={disabled}
      />
      <button
        className="skill-chip"
        onClick={() => onAction()}
        disabled={isLoading || !input.trim() || (room && !isMySpeakTurn)}
        style={{
          padding: '4px 12px', fontSize: 10,
          background: 'linear-gradient(180deg, #3ec8d8, #14444e)',
          color: '#04181c', borderColor: '#2a7a88',
        }}
      >➤ 发送</button>
    </div>
  )
}
