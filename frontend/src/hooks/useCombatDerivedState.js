import { useMemo } from 'react'
import {
  buildAoeCells,
  buildGridTerrainSets,
  buildInitiativeChips,
  buildThreatCells,
  canActInCombatTurn,
  getCameraWindow,
  getCombatSkillBar,
  getCurrentTurnLabel,
  getPlayerAvailableSpells,
  isMyCombatTurn,
  isPlayerCombatTurn,
} from '../utils/combat'

export function useCombatDerivedState({
  combat,
  room,
  myCharacterId,
  playerId,
  selectedTarget,
  showThreat,
  aoePreview,
  aoeHover,
  aoeLockedCenter,
  spells,
  playerKnownSpells,
  playerCantrips,
  playerClass,
  skillBarV10,
  gridWidth,
  gridHeight,
  viewWidth,
  viewHeight,
}) {
  const { entity_positions: entityPositions = {}, entities = {} } = combat || {}

  const isMyTurnMP = useMemo(() =>
    isMyCombatTurn({ room, combat, myCharacterId }),
  [room, combat, myCharacterId])

  const currentTurnLabel = useMemo(() =>
    getCurrentTurnLabel({ room, combat }),
  [room, combat])

  const playerAvailableSpells = useMemo(() =>
    getPlayerAvailableSpells({
      spells,
      knownSpells: playerKnownSpells,
      cantrips: playerCantrips,
      playerClass,
    }),
  [spells, playerKnownSpells, playerCantrips, playerClass])

  const threatCells = useMemo(() =>
    buildThreatCells({ showThreat: showThreat && !!combat, entityPositions, entities }),
  [showThreat, combat, entityPositions, entities])

  const effectivePlayerId = room && myCharacterId ? myCharacterId : playerId
  const playerPos = effectivePlayerId ? entityPositions[effectivePlayerId] : null

  const aoeCells = useMemo(() =>
    buildAoeCells({ aoePreview, aoeHover: aoeLockedCenter || aoeHover, origin: playerPos }),
  [aoePreview, aoeHover, aoeLockedCenter, playerPos])

  const cam = getCameraWindow({
    playerPos,
    totalWidth: gridWidth,
    totalHeight: gridHeight,
    viewWidth,
    viewHeight,
  })
  const currentTurnEntry = combat?.turn_order?.[combat?.current_turn_index ?? 0]
  const isPlayerTurn = isPlayerCombatTurn(combat)
  const canActThisTurn = canActInCombatTurn({ room, combat, myCharacterId })
  const { walls, hazards } = buildGridTerrainSets(combat?.grid_data || {})
  const selectedTargetEntity = selectedTarget ? entities[selectedTarget] : null
  const controlledCharacter = effectivePlayerId ? entities[effectivePlayerId] : null
  const initiativeChips = buildInitiativeChips({
    turnOrder: combat?.turn_order || [],
    currentTurnIndex: combat?.current_turn_index ?? 0,
    entities,
  })
  const skillBar = getCombatSkillBar(skillBarV10)

  return {
    entityPositions,
    entities,
    playerPos,
    effectivePlayerId,
    cam,
    currentTurnEntry,
    isPlayerTurn,
    canActThisTurn,
    isMyTurnMP,
    currentTurnLabel,
    walls,
    hazards,
    selectedTargetEntity,
    controlledCharacter,
    initiativeChips,
    skillBar,
    playerAvailableSpells,
    threatCells,
    aoeCells,
  }
}
