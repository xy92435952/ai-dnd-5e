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

      {error && (
        <div style={{
          position: 'fixed',
          bottom: 16,
          left: '50%',
          transform: 'translateX(-50%)',
          padding: '8px 16px',
          background: 'rgba(139,32,32,.9)',
          color: '#fff',
          border: '1px solid var(--blood)',
          borderRadius: 4,
          zIndex: 999,
          fontSize: 12,
        }}>
          ⚠ {error}
        </div>
      )}
    </>
  )
}
