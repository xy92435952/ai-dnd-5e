import DialoguePendingCheck from './DialoguePendingCheck'
import DialogueChoices from './DialogueChoices'
import DialogueRecoveryAffordances from './DialogueRecoveryAffordances'
import DialogueFreeSpeak from './DialogueFreeSpeak'

export default function DialogueResponseBox({
  pendingCheck,
  checkRolling,
  onDiceRoll,
  choices,
  player,
  setPendingCheck,
  onAction,
  input,
  setInput,
  inputRef,
  isLoading,
  room,
  isMySpeakTurn,
  multiplayerSyncBlocked = false,
}) {
  const disabled = isLoading || (room && (!isMySpeakTurn || multiplayerSyncBlocked))

  if (pendingCheck) {
    return (
      <DialoguePendingCheck
        pendingCheck={pendingCheck}
        checkRolling={checkRolling}
        onDiceRoll={onDiceRoll}
        disabled={disabled}
        player={player}
        onToggleLucky={() => setPendingCheck(prev => prev ? { ...prev, use_lucky: !prev.use_lucky } : prev)}
      />
    )
  }

  return (
    <div style={{ borderTop: '1px solid rgba(138,90,24,.35)', paddingTop: 12 }}>
      <div style={{
        fontFamily: 'var(--font-mono)', fontSize: 10,
        color: 'var(--arcane-light)', letterSpacing: '.25em',
        textTransform: 'uppercase', marginBottom: 8,
        display: 'flex', alignItems: 'center', gap: 10,
      }}>
        <span style={{ flex: 0, color: 'var(--parchment-dark)' }}>▼</span>
        <span>你的回应</span>
        <span style={{ flex: 1, height: 1, background: 'linear-gradient(90deg, rgba(127,232,248,.4), transparent)' }} />
        {choices.length > 0 && (
          <span style={{ color: 'var(--parchment-dark)' }}>1–{Math.min(choices.length, 9)} 快捷键</span>
        )}
      </div>

      <DialogueChoices
        choices={choices}
        player={player}
        setPendingCheck={setPendingCheck}
        onAction={onAction}
        disabled={disabled}
      />

      <DialogueRecoveryAffordances
        input={input}
        setInput={setInput}
        inputRef={inputRef}
        onAction={onAction}
        disabled={disabled}
      />

      <DialogueFreeSpeak
        input={input}
        setInput={setInput}
        inputRef={inputRef}
        onAction={onAction}
        isLoading={isLoading}
        room={room}
        isMySpeakTurn={isMySpeakTurn}
        multiplayerSyncBlocked={multiplayerSyncBlocked}
      />
    </div>
  )
}
