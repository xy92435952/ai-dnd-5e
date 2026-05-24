# DnD Rules Backlog

> Goal: move the game toward an AI-driven Baldur's Gate style experience while keeping rules math local and deterministic.

## Principles

1. Local code owns dice, modifiers, HP, resources, action economy, conditions, spell effects, and combat legality.
2. AI owns narration, intent interpretation, NPC/companion personality, scene presentation, and ambiguous table adjudication.
3. Every new rule slice needs at least one backend rule test and one user-facing flow check when it affects Adventure or Combat.
4. Prefer low-level 5e rules that appear constantly in levels 1-5 before rare high-level features.

## Priority 1: Core Table Feel

| Rule area | Why it matters | First implementation slice | Tests |
| --- | --- | --- | --- |
| Advantage/disadvantage | Central to DnD feel and tactical choices. | Add a shared roll mode to skill checks, attacks, saves, and UI dice display. | Unit tests for roll selection; Adventure skill-check click path. |
| Saving throws | Many spells and hazards depend on saves. | Implemented shared save roll result shape, `/game/saving-throw`, and Adventure hook routing for DM-generated save requests. | `dnd_rules` unit tests; game flow endpoint tests; `useSkillCheck` saving-throw routing test. |
| Passive perception/investigation | Makes exploration feel less binary. | Expose passive scores in ContextBuilder and choice preview. | Context builder tests; Adventure choice tests. |
| Inspiration | Simple, high-impact player agency. | Store inspiration on character/session, spend for advantage. | Character/resource tests; UI spend path. |
| Group checks | Multiplayer and party exploration need fair group resolution. | Resolve majority success and aggregate dice display. | Service tests for mixed party results. |

## Priority 2: Combat Action Economy

| Rule area | First implementation slice | Tests |
| --- | --- | --- |
| Ready action | Store prepared trigger and consume reaction when triggered. | Turn-state and reaction endpoint tests. |
| Dodge | Attackers get disadvantage until next turn. | Attack roll tests. |
| Help | Existing `being_helped` should become advantage on the next relevant check/attack, then clear. | Turn-state tests. |
| Hide/search | Stealth vs passive perception, hidden target advantage rules. | Combat service tests. |
| Opportunity attacks | Expand existing reaction logic with disengage and reach checks. | Movement/reaction integration tests. |

## Priority 3: Spell System Depth

| Rule area | First implementation slice | Tests |
| --- | --- | --- |
| Concentration | Already partially present; enforce break on new concentration spell and damage checks. | Concentration service tests. |
| Area templates | Cone/line/sphere target selection and friendly-fire preview. | Spell target tests and UI preview test. |
| Save-for-half spells | Apply save result to damage scaling. | Spell resolution tests. |
| Conditions from spells | Bless, bane, restrained, frightened, blinded. | Spell effect and condition duration tests. |
| Rituals/out-of-combat spells | Let Adventure actions consume time instead of slots when ritual eligible. | Adventure action tests. |

## Priority 4: Class Identity Levels 1-5

| Class | Feature slices |
| --- | --- |
| Fighter | Second Wind, Action Surge, Battle Master maneuvers polish. |
| Rogue | Sneak Attack, Cunning Action, expertise checks. |
| Cleric | Channel Divinity, domain spells, Turn Undead baseline. |
| Wizard | Arcane Recovery, ritual casting, school features later. |
| Paladin | Lay on Hands, Divine Smite, Divine Sense, aura later. |
| Bard | Bardic Inspiration, Jack of All Trades, Song of Rest. |
| Druid | Wild Shape baseline, Natural Recovery. |
| Monk | Ki, Flurry, Patient Defense, Step of the Wind. |

## Priority 5: CRPG Layer

| System | First slice |
| --- | --- |
| Quest journal | Convert checkpoint summaries into objective states and visible journal entries. |
| NPC relationship state | Store attitude, faction, secrets, and recent promises in campaign state. |
| Companion approval | Add companion preference hooks and visible approval deltas for major choices. |
| Inventory/equipment usability | Expand item use in and out of combat. |
| Encounter scripting | Let modules define triggers, fail states, reinforcements, and environmental actions. |

## Near-Term Recommendation

Advantage/disadvantage first slice is now implemented for Adventure skill checks:

- `SkillCheckRequest` accepts `advantage` and `disadvantage`.
- `/game/skill-check` passes roll mode to local rule math.
- `roll_skill_check()` returns normalized roll-mode flags and `other_roll` when applicable.
- `useSkillCheck` rolls two d20s for advantage/disadvantage, picks the correct die, and sends the selected value to the backend.

Saving throws first slice is now implemented:

- `roll_saving_throw()` returns normalized roll-mode flags, `other_roll`, and proficiency state.
- `/game/saving-throw` applies session/character-control authorization and writes a dice log.
- `useSkillCheck` routes DM-generated `check_kind: "saving_throw"` requests to the saving throw endpoint while keeping legacy skill checks unchanged.

Next rule slice should extend the same roll-mode shape into inspiration spending, group checks, or save-for-half spell resolution.
