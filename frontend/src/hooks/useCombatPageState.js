import { useRef, useState } from 'react'

export function useCombatPageState() {
  const [combat, setCombat] = useState(null)
  const [isProcessing, setIsProcessing] = useState(false)
  const [combatOver, setCombatOver] = useState(null)
  const [error, setError] = useState('')
  const [spellModalOpen, setSpellModalOpen] = useState(false)
  const [playerSpellSlots, setPlayerSpellSlots] = useState({})
  const [playerKnownSpells, setPlayerKnownSpells] = useState([])
  const [playerCantrips, setPlayerCantrips] = useState([])
  const [playerId, setPlayerId] = useState(null)
  const [turnState, setTurnState] = useState(null)
  const [smitePrompt, setSmitePrompt] = useState(null)
  const [playerClass, setPlayerClass] = useState('')
  const [playerLevel, setPlayerLevel] = useState(1)
  const [classResources, setClassResources] = useState({})
  const [playerSubclass, setPlayerSubclass] = useState('')
  const [playerSubclassEffects, setPlayerSubclassEffects] = useState({})
  const [maneuverModalOpen, setManeuverModalOpen] = useState(false)
  const [reactionPrompt, setReactionPrompt] = useState(null)
  const [initiativeShown, setInitiativeShown] = useState(false)
  const [session, setSession] = useState(null)

  const aiTimer = useRef(null)
  const processingRef = useRef(false)

  return {
    combat, setCombat,
    isProcessing, setIsProcessing,
    combatOver, setCombatOver,
    error, setError,
    spellModalOpen, setSpellModalOpen,
    playerSpellSlots, setPlayerSpellSlots,
    playerKnownSpells, setPlayerKnownSpells,
    playerCantrips, setPlayerCantrips,
    playerId, setPlayerId,
    turnState, setTurnState,
    smitePrompt, setSmitePrompt,
    playerClass, setPlayerClass,
    playerLevel, setPlayerLevel,
    classResources, setClassResources,
    playerSubclass, setPlayerSubclass,
    playerSubclassEffects, setPlayerSubclassEffects,
    maneuverModalOpen, setManeuverModalOpen,
    reactionPrompt, setReactionPrompt,
    initiativeShown, setInitiativeShown,
    session, setSession,
    aiTimer,
    processingRef,
  }
}
