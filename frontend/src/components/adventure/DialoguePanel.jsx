/**
 * DialoguePanel — Adventure 剧场气泡、日志、选项与自由输入区域。
 */
import DialogueStagePlayer from './DialogueStagePlayer'
import DialogueLogList from './DialogueLogList'
import DialogueResponseBox from './DialogueResponseBox'

export default function DialoguePanel({
  dialogueMode,
  dialogueQueue,
  dialogueIdx,
  typingText,
  typingDone,
  onAdvanceDialogue,
  logs,
  logsEndRef,
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
  return (
    <div
      className="adventure-dialogue-panel"
      role="region"
      aria-label="冒险对话面板"
    >
      {dialogueMode === 'stage' && dialogueQueue[dialogueIdx] && (
        <DialogueStagePlayer
          dialogueQueue={dialogueQueue}
          dialogueIdx={dialogueIdx}
          typingText={typingText}
          typingDone={typingDone}
          onAdvanceDialogue={onAdvanceDialogue}
        />
      )}

      {dialogueMode === 'chat' && (
        <DialogueLogList logs={logs} logsEndRef={logsEndRef} />
      )}

      <div className={`crpg-dialogue dialogue-response-shell ${dialogueMode === 'stage' ? 'hidden' : ''}`}>
        <DialogueResponseBox
          pendingCheck={pendingCheck}
          pendingExplorationReaction={pendingExplorationReaction}
          checkRolling={checkRolling}
          onDiceRoll={onDiceRoll}
          onExplorationReaction={onExplorationReaction}
          choices={choices}
          player={player}
          setPendingCheck={setPendingCheck}
          onAction={onAction}
          input={input}
          setInput={setInput}
          inputRef={inputRef}
          isLoading={isLoading}
          room={room}
          isMySpeakTurn={isMySpeakTurn}
          multiplayerSyncBlocked={multiplayerSyncBlocked}
        />
      </div>
    </div>
  )
}
