import StageBubble from './StageBubble'
import CompanionReactionPanel from './CompanionReactionPanel'

export default function DialogueStagePlayer({
  dialogueQueue,
  dialogueIdx,
  typingText,
  typingDone,
  onAdvanceDialogue,
}) {
  if (!dialogueQueue[dialogueIdx]) return null
  const currentSegment = dialogueQueue[dialogueIdx]
  const progressText = `${dialogueIdx + 1} / ${dialogueQueue.length}`
  const advanceHint = typingDone ? '▸ 点击继续（空格/回车）' : '… 打字中（点击跳过）'
  const speaker = currentSegment.speaker || (currentSegment.role === 'dm' ? 'DM' : 'NPC')

  const handleKeyDown = (event) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      onAdvanceDialogue()
    }
  }

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onAdvanceDialogue}
      onKeyDown={handleKeyDown}
      className="dialogue-stage-player"
      aria-label={`${speaker}剧场对白，${progressText}，${typingDone ? '点击继续' : '点击跳过打字'}`}
    >
      <StageBubble seg={currentSegment} typingText={typingText} typingDone={typingDone} />
      <CompanionReactionPanel
        reactions={currentSegment.companionReactions}
        visible={typingDone}
      />
      <div className="dialogue-stage-progress" role="status" aria-live="polite">
        <span>{progressText}</span>
        <span className={typingDone ? 'ready' : ''}>
          {advanceHint}
        </span>
      </div>
    </div>
  )
}
