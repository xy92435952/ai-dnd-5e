import DialoguePendingCheck from './DialoguePendingCheck'
import DialogueChoices from './DialogueChoices'
import DialogueRecoveryAffordances from './DialogueRecoveryAffordances'
import DialogueFreeSpeak from './DialogueFreeSpeak'
import ExplorationReactionPrompt from './ExplorationReactionPrompt'

export default function DialogueResponseBox({
  pendingCheck,
  pendingExplorationReaction,
  checkRolling,
  onDiceRoll,
  onExplorationReaction,
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
        onToggleBardicInspiration={() => setPendingCheck(prev => prev ? { ...prev, use_bardic_inspiration: !prev.use_bardic_inspiration } : prev)}
      />
    )
  }

  if (pendingExplorationReaction) {
    return (
      <ExplorationReactionPrompt
        prompt={pendingExplorationReaction}
        disabled={isLoading || (room && multiplayerSyncBlocked)}
        onResolve={onExplorationReaction}
      />
    )
  }

  return (
    <section className="dialogue-response-box" aria-label="玩家回应">
      <div className="dialogue-response-header" role="status" aria-live="polite">
        <span className="dialogue-response-caret">▼</span>
        <span>你的回应</span>
        <span className="dialogue-response-rule" />
        {choices.length > 0 && (
          <span className="dialogue-response-shortcuts">1–{Math.min(choices.length, 9)} 快捷键</span>
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
    </section>
  )
}
