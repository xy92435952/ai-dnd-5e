/**
 * AdventureStage — 剧场舞台区。
 */
import DMThinkingOverlay from '../DMThinkingOverlay'
import StageLeftFigure from './StageLeftFigure'

function getTensionTone(tension) {
  if (tension === '平静') return 'calm'
  if (tension === '危险' || tension === '致命') return 'danger'
  return 'watch'
}

export default function AdventureStage({
  dialogueMode,
  currentSeg,
  companions,
  player,
  hasDmContent,
  sceneVibe = {},
  isLoading,
}) {
  const playerName = player?.name || '我'
  const tensionTone = getTensionTone(sceneVibe.tension)

  return (
    <section className="dialogue-stage" role="region" aria-label="冒险剧场舞台">
      <div className="stage-letterbox top" />

      <StageLeftFigure
        dialogueMode={dialogueMode}
        currentSeg={currentSeg}
        companions={companions}
        player={player}
        hasDmContent={hasDmContent}
      />

      {player && (
        <div className="stage-figure right stage-figure-player" role="group" aria-label={`玩家角色：${playerName}`}>
          <div className="silhouette player-silhouette">
            <div className="stage-figure-initial">{playerName.slice(0, 1)}</div>
          </div>
          <div className="nameplate player-nameplate">
            ◈ {playerName}
          </div>
        </div>
      )}

      <div className="stage-focus-glow" aria-hidden="true">
        <div className="stage-focus-glow-core" />
      </div>

      <div className="scene-vibe-strip" role="status" aria-live="polite" aria-label="当前场景状态">
        {sceneVibe.location && <span className="scene-vibe-item location">🜂 {sceneVibe.location}</span>}
        {sceneVibe.time_of_day && <><span className="scene-vibe-separator" aria-hidden="true">|</span><span className="scene-vibe-item time">☀ {sceneVibe.time_of_day}</span></>}
        {sceneVibe.tension && (<><span className="scene-vibe-separator" aria-hidden="true">|</span>
          <span className={`scene-vibe-item tension ${tensionTone}`}>
            ⚠ {sceneVibe.tension}
          </span></>)}
      </div>

      <div className="stage-letterbox bottom" />
      <DMThinkingOverlay visible={isLoading} />
    </section>
  )
}
