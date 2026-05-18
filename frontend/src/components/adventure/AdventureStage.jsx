/**
 * AdventureStage — 剧场舞台区。
 */
import DMThinkingOverlay from '../DMThinkingOverlay'
import StageLeftFigure from './StageLeftFigure'

export default function AdventureStage({
  dialogueMode,
  currentSeg,
  companions,
  player,
  hasDmContent,
  sceneVibe,
  isLoading,
  streamingNarrative,
}) {
  return (
    <div className="dialogue-stage" style={{ position: 'relative' }}>
      <div className="stage-letterbox top" />

      <StageLeftFigure
        dialogueMode={dialogueMode}
        currentSeg={currentSeg}
        companions={companions}
        player={player}
        hasDmContent={hasDmContent}
      />

      {player && (
        <div className="stage-figure right">
          <div className="silhouette" style={{ background: 'radial-gradient(circle at 40% 30%, #e8d070, #6a5020 75%)' }}>
            <div style={{
              position: 'absolute', inset: 0,
              display: 'grid', placeItems: 'center',
              fontFamily: 'var(--font-display)', fontSize: 72,
              color: '#fff8dd', textShadow: '0 4px 12px #000',
            }}>{(player.name || '我').slice(0, 1)}</div>
          </div>
          <div className="nameplate" style={{ background: 'linear-gradient(180deg, #3ec8d8, #14444e)', color: '#04181c', boxShadow: '0 0 0 1px rgba(127,232,248,.6), 0 0 12px -2px var(--arcane-light)' }}>
            ◈ {player.name}
          </div>
        </div>
      )}

      <div style={{ position: 'absolute', left: '50%', top: '50%', transform: 'translate(-50%,-50%)', pointerEvents: 'none' }}>
        <div style={{
          width: 54, height: 54, borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(127,232,248,.8), transparent 70%)',
          filter: 'blur(6px)', animation: 'breathe 2s ease-in-out infinite',
        }} />
      </div>

      <div style={{
        position: 'absolute', top: 12, left: 16, display: 'flex', gap: 10,
        fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--parchment-dark)',
        letterSpacing: '.15em', zIndex: 4,
      }}>
        {sceneVibe.location && <span>🜂 {sceneVibe.location}</span>}
        {sceneVibe.time_of_day && <><span style={{ opacity: .5 }}>|</span><span>☀ {sceneVibe.time_of_day}</span></>}
        {sceneVibe.tension && (<><span style={{ opacity: .5 }}>|</span>
          <span style={{ color: sceneVibe.tension === '平静' ? 'var(--emerald-light)' : sceneVibe.tension === '危险' || sceneVibe.tension === '致命' ? 'var(--blood-light)' : 'var(--amber)' }}>
            ⚠ {sceneVibe.tension}
          </span></>)}
      </div>

      <div className="stage-letterbox bottom" />
      <DMThinkingOverlay visible={isLoading} streamingNarrative={streamingNarrative} />
    </div>
  )
}
