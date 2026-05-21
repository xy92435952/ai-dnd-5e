import StageBubble from './StageBubble'

export default function DialogueStagePlayer({
  dialogueQueue,
  dialogueIdx,
  typingText,
  typingDone,
  onAdvanceDialogue,
}) {
  if (!dialogueQueue[dialogueIdx]) return null

  return (
    <button
      type="button"
      aria-label="继续对话"
      onClick={onAdvanceDialogue}
      style={{
        padding: '20px 28px 10px', maxWidth: 900, margin: '0 auto',
        cursor: 'pointer', userSelect: 'none',
        display: 'block', width: '100%',
        background: 'none', border: 'none', textAlign: 'left',
      }}
    >
      <StageBubble seg={dialogueQueue[dialogueIdx]} typingText={typingText} typingDone={typingDone} />
      <div style={{
        display: 'flex', justifyContent: 'space-between', alignItems: 'center',
        marginTop: 6, fontFamily: 'var(--font-mono)', fontSize: 10,
        color: 'var(--parchment-dark)', letterSpacing: '.15em',
      }}>
        <span>{dialogueIdx + 1} / {dialogueQueue.length}</span>
        <span style={{ color: typingDone ? 'var(--arcane-light)' : 'var(--parchment-dark)' }}>
          {typingDone ? '▸ 点击继续（空格/回车）' : '… 打字中（点击跳过）'}
        </span>
      </div>
    </button>
  )
}
