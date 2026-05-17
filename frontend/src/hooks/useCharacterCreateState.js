import { useEffect, useState } from 'react'
import { POINT_BUY_TOTAL, SCORE_COSTS } from '../utils/characterCreate'

const EMPTY_OPTIONS = {
  races: [],
  classes: [],
  backgrounds: [],
  alignments: [],
  racial_bonuses: {},
  class_skill_choices: {},
  class_save_proficiencies: {},
  all_skills: [],
  class_cantrips: {},
  class_spells: {},
  starting_cantrips_count: {},
  starting_spells_count: {},
  spellcaster_classes: [],
}

const EMPTY_FORM = {
  name: '',
  race: '',
  char_class: '',
  subclass: '',
  level: 1,
  background: '',
  alignment: '中立善良',
  multiclassEnabled: false,
  multiclass_class: '',
  multiclass_level: 1,
}

const EMPTY_SCORES = {
  str: 8,
  dex: 8,
  con: 8,
  int: 8,
  wis: 8,
  cha: 8,
}

const EMPTY_NARRATIVE = {
  personality: '',
  backstory: '',
  speech_style: '',
  combat_preference: '',
  catchphrase: '',
}

function pointBuyPointsLeft(scores, budget) {
  return Object.values(scores).reduce(
    (remaining, score) => remaining - (SCORE_COSTS[score] || 0),
    budget,
  )
}

export function useCharacterCreateState({
  initialPointsLeft = POINT_BUY_TOTAL,
  skillLimit = 0,
  cantripLimit = 0,
  spellLimit = 0,
} = {}) {
  const [module, setModule] = useState(null)
  const [options, setOptions] = useState(EMPTY_OPTIONS)
  const [step, setStep] = useState(1)

  const [form, setForm] = useState(EMPTY_FORM)
  const [scoreMethod, setScoreMethod] = useState('pointbuy')
  const [scores, setScores] = useState(EMPTY_SCORES)
  const [standardAssigned, setStandardAssigned] = useState({})
  const [chosenSkills, setChosenSkills] = useState([])
  const [chosenCantrips, setChosenCantrips] = useState([])
  const [chosenSpells, setChosenSpells] = useState([])

  const [fightingStyle, setFightingStyle] = useState('')
  const [equipChoice, setEquipChoice] = useState(0)
  const [bonusLanguages, setBonusLanguages] = useState([])
  const [chosenFeats, setChosenFeats] = useState([])
  const [narrative, setNarrative] = useState(EMPTY_NARRATIVE)

  const [partySize, setPartySize] = useState(4)
  const [companions, setLocalCompanions] = useState([])
  const [generatingParty, setGeneratingParty] = useState(false)
  const [savedCharId, setSavedCharId] = useState(null)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState('')
  const [forgeOpen, setForgeOpen] = useState(false)
  const [forgeTargetPath, setForgeTargetPath] = useState(null)
  const [modal, setModal] = useState({ type: '', itemKey: '' })

  useEffect(() => {
    setChosenSkills([])
    setChosenCantrips([])
    setChosenSpells([])
    setForm((prev) => ({ ...prev, subclass: '' }))
  }, [form.char_class])

  const adjustScore = (ab, delta) => {
    const cur = scores[ab]
    const next = cur + delta
    if (next < 8 || next > 15) return
    const pointsLeft = pointBuyPointsLeft(scores, initialPointsLeft)
    if (delta > 0 && (SCORE_COSTS[next] - SCORE_COSTS[cur]) > pointsLeft) return
    setScores((prev) => ({ ...prev, [ab]: next }))
  }

  const assignStandard = (ab, idx) => {
    if (Object.entries(standardAssigned).some(([ability, assigned]) => ability !== ab && assigned === idx)) {
      return
    }
    setStandardAssigned((prev) => ({ ...prev, [ab]: idx }))
  }

  const toggleSkill = (skill, limit = skillLimit) => {
    setChosenSkills((prev) => (
      prev.includes(skill) ? prev.filter((value) => value !== skill) : prev.length >= limit ? prev : [...prev, skill]
    ))
  }

  const toggleCantrip = (name, limit = cantripLimit) => {
    setChosenCantrips((prev) => (
      prev.includes(name) ? prev.filter((value) => value !== name) : prev.length >= limit ? prev : [...prev, name]
    ))
  }

  const toggleSpell = (name, limit = spellLimit) => {
    setChosenSpells((prev) => (
      prev.includes(name) ? prev.filter((value) => value !== name) : prev.length >= limit ? prev : [...prev, name]
    ))
  }

  return {
    module,
    setModule,
    options,
    setOptions,
    step,
    setStep,
    form,
    setForm,
    scoreMethod,
    setScoreMethod,
    scores,
    setScores,
    standardAssigned,
    setStandardAssigned,
    chosenSkills,
    setChosenSkills,
    chosenCantrips,
    setChosenCantrips,
    chosenSpells,
    setChosenSpells,
    fightingStyle,
    setFightingStyle,
    equipChoice,
    setEquipChoice,
    bonusLanguages,
    setBonusLanguages,
    chosenFeats,
    setChosenFeats,
    narrative,
    setNarrative,
    partySize,
    setPartySize,
    companions,
    setLocalCompanions,
    generatingParty,
    setGeneratingParty,
    savedCharId,
    setSavedCharId,
    saving,
    setSaving,
    error,
    setError,
    forgeOpen,
    setForgeOpen,
    forgeTargetPath,
    setForgeTargetPath,
    modal,
    openModal: (type, itemKey) => setModal({ type, itemKey }),
    closeModal: () => setModal({ type: '', itemKey: '' }),
    adjustScore,
    assignStandard,
    toggleSkill,
    toggleCantrip,
    toggleSpell,
  }
}
