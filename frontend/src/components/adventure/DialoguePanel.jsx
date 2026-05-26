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
  return (
    <div style={{ overflow: 'auto', maxHeight: '40vh' }}>
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

      <div className="crpg-dialogue" style={{ margin: '10px 24px 0', display: dialogueMode === 'stage' ? 'none' : 'block' }}>
        <DialogueResponseBox
          pendingCheck={pendingCheck}
          checkRolling={checkRolling}
          onDiceRoll={onDiceRoll}
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
