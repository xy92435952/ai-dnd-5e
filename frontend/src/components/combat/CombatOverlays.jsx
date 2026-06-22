import SpellModal from './SpellModal'
import ManeuverModal from './ManeuverModal'
import SmitePrompt from './SmitePrompt'
import ReactionPrompt from './ReactionPrompt'
import LegendaryActionPrompt from './LegendaryActionPrompt'

export default function CombatOverlays({
  smitePrompt,
  playerSpellSlots,
  onSmite,
  onCancelSmite,
  spellModalOpen,
  spellQuickPick,
  playerAvailableSpells,
  playerCantrips,
  selectedTarget,
  playerId,
  combat,
  aoeHover,
  aoeLockedCenter,
  onResetAoeCenter,
  onCastSpell,
  onCloseSpell,
  onSpellHover,
  useBardicSpellSave,
  onToggleBardicSpellSave,
  maneuverModalOpen,
  playerSubclassEffects,
  classResources,
  onUseManeuver,
  onCloseManeuver,
  reactionPrompt,
  lairActionPrompt,
  legendaryActionPrompt,
  currentCharacterId,
  onReact,
  onCancelReaction,
  onUseLairAction,
  onSkipLairAction,
  onUseLegendaryAction,
  onSkipLegendaryAction,
  forceEndConfirmOpen,
  onConfirmForceEndCombat,
  onCancelForceEndCombat,
  error,
}) {
  return (
    <>
      <SmitePrompt
        open={!!smitePrompt?.show}
        playerSpellSlots={playerSpellSlots}
        onSmite={onSmite}
        onCancel={onCancelSmite}
      />

      {spellModalOpen && (
        <SpellModal
          spells={playerAvailableSpells}
          cantrips={playerCantrips}
          slots={playerSpellSlots}
          quickPick={spellQuickPick}
          selectedTarget={selectedTarget}
          playerId={playerId}
          combat={combat}
          aoeHover={aoeLockedCenter || aoeHover}
          aoeLockedCenter={aoeLockedCenter}
          onCast={onCastSpell}
          onClose={onCloseSpell}
          onSpellHover={onSpellHover}
          onResetAoeCenter={onResetAoeCenter}
          useBardicSpellSave={useBardicSpellSave}
          onToggleBardicSpellSave={onToggleBardicSpellSave}
        />
      )}

      {maneuverModalOpen && (
        <ManeuverModal
          diceType={playerSubclassEffects?.superiority_die || 'd8'}
          remaining={classResources?.superiority_dice_remaining ?? 0}
          onUse={onUseManeuver}
          onClose={onCloseManeuver}
        />
      )}

      <ReactionPrompt
        prompt={reactionPrompt}
        currentCharacterId={currentCharacterId}
        onReact={onReact}
        onCancel={onCancelReaction}
      />

      <LegendaryActionPrompt
        prompt={lairActionPrompt}
        variant="lair"
        onUse={onUseLairAction}
        onSkip={onSkipLairAction}
      />

      <LegendaryActionPrompt
        prompt={lairActionPrompt ? null : legendaryActionPrompt}
        onUse={onUseLegendaryAction}
        onSkip={onSkipLegendaryAction}
      />

      {forceEndConfirmOpen && (
        <div
          className="combat-force-end-confirm"
          role="dialog"
          aria-modal="true"
          aria-labelledby="combat-force-end-confirm-title"
          aria-describedby="combat-force-end-confirm-desc"
        >
          <div className="combat-force-end-confirm-panel">
            <h2 id="combat-force-end-confirm-title">强制结束战斗</h2>
            <p id="combat-force-end-confirm-desc">
              这会立即结束当前战斗并返回冒险场景。
            </p>
            <div className="combat-force-end-confirm-actions" role="group" aria-label="强制结束战斗操作">
              <button
                type="button"
                className="btn-ghost combat-force-end-confirm-cancel"
                onClick={onCancelForceEndCombat}
              >
                取消
              </button>
              <button
                type="button"
                className="btn-gold combat-force-end-confirm-submit"
                onClick={onConfirmForceEndCombat}
              >
                确认结束
              </button>
            </div>
          </div>
        </div>
      )}

      {error && (
        <div className="combat-overlay-error" role="alert">
          <span aria-hidden="true">⚠</span>
          <span>{error}</span>
        </div>
      )}
    </>
  )
}
