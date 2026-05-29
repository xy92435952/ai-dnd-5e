# DnD Rules Coverage And Experience TODO

> Baseline date: 2026-05-27
> Scope: AI DnD 5e playable Alpha toward an AI-driven CRPG experience.
> Multiplayer target: about 50 concurrent online users on one server, across isolated rooms; each multiplayer game room remains capped around 4 players.

This document is the long-running TODO for two tracks:

- DnD 5e rule coverage: keep math, dice, resources, and state transitions in the backend rule engine.
- Experience quality: make single-player and 4-player multiplayer sessions feel stable, readable, and game-like under real use.

The percentages below are working estimates, not product promises. Update them when a feature is implemented and verified with tests or a manual playthrough.

## Current Snapshot

| Area | Current Estimate | Notes |
| --- | ---: | --- |
| Playable single-player experience | 75-80% | Core adventure, DM response, skill checks, combat entry, and character state are usable. |
| 4-player multiplayer game experience | 65-70% | Room, membership, turn ownership, WS updates, and combat sync exist; long-session recovery still needs pressure. |
| 50 online users across rooms | 65-75% | 50-user/13-room WS smoke passed twice locally on 2026-05-28 with repeated prefix/user reuse; still needs regular CI/manual repetition and failure-mode testing. |
| Core playable DnD rules | 60-70% | Common combat math, turns, reactions, death saves, conditions, key spells, spell action economy, and first monster traits are present. |
| Full DnD 5e coverage | 35-45% | Long tail remains: full spell behavior, subclasses, advanced monster traits, exploration procedures, and edge cases. |
| BG-style CRPG experience | 35-45% | The system has the right skeleton; encounter design, UI polish, tactical depth, and persistence need much more work. |

## Status Legend

| Mark | Meaning |
| --- | --- |
| `[x]` | Implemented and covered by tests or a verified playthrough. |
| `[~]` | Partially implemented or implemented but not fully verified. |
| `[ ]` | Not implemented, shallow, or not trusted yet. |

Priority:

- P0: needed for stable playable sessions.
- P1: needed for a satisfying DnD-feeling Alpha.
- P2: needed for deep 5e coverage or CRPG depth.

## Rule Coverage Matrix

### Foundation

| Status | Priority | Rule Area | Current State | Done Definition |
| --- | --- | --- | --- | --- |
| [x] | P0 | Dice rolling | Backend has local dice helpers and tests. | Dice expressions used by combat, skill checks, damage, healing, and saves never depend on LLM output. |
| [x] | P0 | Ability modifiers and proficiency | Character derived stats and skill checks exist. | Every class/race/background path produces stable modifiers, proficiency bonus, saves, and skill values. |
| [x] | P0 | Skill checks | `/game/skill-check` and Adventure skill-check choice flow exist. | Click path, manual action path, success/failure narration, and multiplayer access control are tested. |
| [~] | P1 | Advantage/disadvantage | Combat uses advantage in several paths. | One shared advantage/disadvantage resolver covers attacks, saves, checks, conditions, help, prone, invisibility, restrained, and exhaustion. |
| [~] | P1 | Difficulty class handling | DC appears in skill checks and spell saves. | DC source is visible in logs/UI and consistent across ability checks, saving throws, spell save DC, and monster abilities. |

### Character Creation And Progression

| Status | Priority | Rule Area | Current State | Done Definition |
| --- | --- | --- | --- | --- |
| [x] | P0 | Basic races/classes/backgrounds | Data tables exist for common options. | All creation options serialize cleanly and produce valid level 1 characters. |
| [~] | P0 | Starting equipment | Equipment tables and inventory services exist. | Every class/background can start with valid equipped gear, AC, weapon attacks, ammo, and pack items. |
| [~] | P1 | Level up | Level-up schema/service exists. | Level-up updates HP, proficiency, features, spells, class resources, and derived stats for all supported classes. |
| [~] | P1 | Spell learning/preparation | Known/prepared/cantrip fields exist. | Known casters, prepared casters, half casters, pact magic, and subclass spells follow 5e-like limits. |
| [ ] | P1 | Multiclass rules | Model field exists, deeper rules not complete. | Multiclass spell slots, proficiencies, prerequisites, class features, and UI are implemented and tested. |
| [ ] | P2 | Feats | Feat data exists. | Feats can be selected, persisted, applied to derived stats/actions, and tested in combat/exploration. |

### Turn Economy

| Status | Priority | Rule Area | Current State | Done Definition |
| --- | --- | --- | --- | --- |
| [x] | P0 | Initiative and turn order | Combat state tracks turn order/current turn. | Player, AI companion, and enemy turns advance deterministically in single and multiplayer. |
| [x] | P0 | Action tracking | Turn state tracks action, bonus action, reaction, movement. | Every combat endpoint refuses illegal extra use and reports clear reason to UI. |
| [x] | P0 | Movement budget | Movement used/max are tracked. | Move endpoint enforces speed, difficult terrain, prone stand-up cost, grapple/restrained speed, and opportunity triggers. |
| [~] | P1 | Dash/disengage/help/dodge | Several action keys and effects exist. | All basic actions are exposed in UI, enforce action economy, and affect attacks/movement exactly once. |
| [~] | P1 | Ready action | Not trusted as a full reaction trigger system. | Players can ready attack/spell/move with a condition; backend resolves trigger and consumes reaction. |
| [ ] | P2 | Held turns / delay | Not established. | UI and backend support waiting without corrupting initiative or multiplayer ownership. |

### Attacks And Damage

| Status | Priority | Rule Area | Current State | Done Definition |
| --- | --- | --- | --- | --- |
| [x] | P0 | Weapon attacks | Attack roll and damage roll paths exist. | Melee/ranged weapon attacks enforce range, proficiency, ability modifier, cover, and target validity. |
| [x] | P0 | Direct parsed attacks | Natural-language combat action can resolve common attacks. | Local parser handles common move+attack intent before LLM fallback and never fabricates impossible attacks. |
| [x] | P0 | Damage application | HP, healing, resistance, death save interaction exist. | Damage, healing, temp HP, resistance, vulnerability, immunity, and instant death are covered by shared services. |
| [~] | P1 | Critical hits | Likely handled in attack math, needs audit. | Crit rules double dice, not flat modifiers, across weapons, spell attacks, smite, sneak attack, and riders. |
| [~] | P1 | Cover | Cover bonus appears in AI attack path. | Half/three-quarters/full cover are calculated from grid and applied to all ranged attacks and relevant saves. |
| [~] | P1 | Opportunity attacks | Service exists. | Moving out of reach triggers correct reactions from players, AI companions, and enemies without duplicate prompts. |
| [~] | P1 | Two-weapon fighting | Offhand service exists. | Light weapon, bonus action, ability modifier, fighting style, and rider interactions are enforced. |
| [~] | P2 | Ammunition and thrown weapons | First combat slice complete: tracked bow/crossbow ammo is consumed by two-step and direct ranged attacks, empty ammo is rejected, thrown weapon copies are consumed in both attack flows, starting thrown bundles are expanded into weapon copies, new starting ammunition weapons get 20 ammo, and Combat HUD/logs surface ammo/thrown resource changes. Remaining work: weapon selection UI, recovery of thrown weapons, and AI/enemy ammo policy. | Ranged attacks consume ammo/thrown weapons and reject unavailable equipment. |

### Conditions And Life State

| Status | Priority | Rule Area | Current State | Done Definition |
| --- | --- | --- | --- | --- |
| [x] | P0 | Unconscious/dying/death saves | Death save endpoint and healing interactions exist. | 0 HP, stable, healing from 0, death save crits, and three failures are tested in combat. |
| [~] | P0 | Incapacitation gates | Action/reaction validators exist; reaction already-resolved paths now still reject 0 HP, dead, stable, or stunned actors. | Every action endpoint uses one common rule state to reject incapacitated, dead, stunned, paralyzed, etc. |
| [~] | P1 | Prone, grappled, restrained | Services exist for grapple/shove/movement impact. | Movement, attack advantage/disadvantage, escape checks, shove prone, and drag behavior are complete. |
| [~] | P1 | Concentration | Concentration checks and cleanup services exist. | Damage, voluntary new concentration, incapacitation, death, spell end, and multiplayer sync all clear effects. |
| [~] | P1 | Exhaustion | Data exists and healing tests account for HP max. | All six exhaustion levels affect checks, speed, attacks/saves, HP max, speed zero, and death. |
| [ ] | P2 | Full condition set | Partial. | Blinded, charmed, deafened, frightened, invisible, paralyzed, petrified, poisoned, prone, restrained, stunned, unconscious all have mechanical effects and UI labels. |

### Reactions

| Status | Priority | Rule Area | Current State | Done Definition |
| --- | --- | --- | --- | --- |
| [x] | P0 | Reaction usage limit | Turn state tracks `reaction_used`. | Any reaction path consumes exactly one reaction and resets at the right time. |
| [x] | P0 | Shield | Implemented as prompted reaction with slot cost and AC/damage correction. | Works in single and multiplayer, including already-applied hit correction and WS prompt ownership. |
| [x] | P0 | Hellish Rebuke | Implemented as prompted reaction with save/damage. | Attacker targeting, slot use, save DC, half damage, and broadcast are tested. |
| [x] | P0 | Counterspell | Implemented for spell-cast reaction prompts. | Range, sight, slot choice, ability check for higher-level spells, decline/resume, and multiplayer reactor ownership work. |
| [x] | P1 | Absorb Elements | Implemented for elemental attack damage and next melee rider. | Acid/cold/fire/lightning/thunder prevention, temporary resistance, slot choice, rider consumption, and multiplayer broadcast are tested. |
| [~] | P1 | Uncanny Dodge | Prompt and prevention logic exist. | Rogue level gate, damage halving, already-applied damage restoration, and all attack paths are covered. |
| [ ] | P2 | Feather Fall / other non-combat reactions | Spell data exists but trigger system not complete. | Fall trigger prompts eligible casters, consumes reaction and slot, and resolves fall damage. |

### Spells

| Status | Priority | Rule Area | Current State | Done Definition |
| --- | --- | --- | --- | --- |
| [x] | P0 | Spell catalog | About 100 spell entries exist in `backend/data/spells_srd.json`. | Spell loader tolerates comments/encoding, lists spells by class, and exposes stable frontend data. |
| [x] | P0 | Basic spell slots | Character spell slots exist and are consumed by several actions. | Slot use, upcasting, pact slots, short/long rest recovery, and unavailable-slot errors are consistent. |
| [x] | P0 | Spell action economy | 2026-05-28 verified: action cantrips consume action, bonus-action spells consume bonus action, reaction spells are blocked from ordinary spell flows. | `casting_time` determines action/bonus/reaction cost in two-step and direct spell paths, with unit and combat endpoint integration coverage. |
| [~] | P0 | Damage spells | Common direct damage and AoE data exist. | Attack-roll spells, save spells, half-on-save, multi-damage-type, upcast, and target selection are unified. |
| [~] | P0 | Healing spells | Cure/healing services exist; bonus-action casting now consumes bonus action instead of action. | Healing respects range, target validity, bonus action, downed targets, undead/construct exclusions where relevant. |
| [~] | P1 | Concentration spells | Bless/Hex/Web/Guiding Bolt style effects exist partially. | Every concentration spell applies named effects, duration, cleanup, and UI status consistently. |
| [~] | P1 | Battlefield control | Web, slow, fear, entangle-like data/effects exist partially. | Save, repeat save, movement penalty, condition, area persistence, and AI awareness are complete. |
| [ ] | P1 | Area targeting UI | Not complete enough for CRPG feel. | Frontend supports cone, line, cube, sphere, self aura, ground point, and multi-target confirmation. |
| [ ] | P2 | Summons and conjurations | Mostly narrative. | Summoned creatures enter initiative/grid, obey controller, and persist with concentration/duration. |
| [ ] | P2 | Illusion/enchantment adjudication | Mostly AI/narrative. | Rules layer tracks saves, investigation checks, charm/frighten/control limits, and social consequences. |
| [ ] | P2 | High-level spell edge cases | Partial data. | Polymorph, banishment, resurrection, wish-like effects have controlled mechanics or explicit DM adjudication gates. |

### Class And Subclass Features

| Status | Priority | Rule Area | Current State | Done Definition |
| --- | --- | --- | --- | --- |
| [x] | P0 | Fighter basics | Second Wind and Action Surge endpoint support exist. | Resources, rest recovery, action economy, and UI buttons are tested. |
| [x] | P0 | Barbarian Rage | Rage resource/damage handling exists. | Rage start/end, bonus damage, resistance, duration, and rest recovery are tested. |
| [x] | P0 | Rogue Sneak Attack | Sneak attack appears in attack resolution. | Advantage/adjacent ally conditions, once per turn, crit doubling, ranged/finesse requirement, and swashbuckler variant are tested. |
| [~] | P1 | Paladin Smite / Lay on Hands | Smite endpoint and healing pool behavior exist partially. | Divine Smite on hit, upcast, undead/fiend bonus, Lay on Hands pool, disease/poison cure, and UI are tested. |
| [~] | P1 | Monk Ki | Skill bar hints exist; deep mechanics unknown. | Flurry, Patient Defense, Step of the Wind, Stunning Strike, ki recovery, and martial arts are implemented. |
| [~] | P1 | Druid Wild Shape | Wild shape HP helpers/subclass effects exist. | Form selection, temp HP pool, attacks, AC, movement, damage carryover, concentration, and ending form are complete. |
| [~] | P1 | Warlock pact behavior | Pact slots and some subclass effects exist. | Pact magic slots, invocations, Eldritch Blast scaling, Hex, and short rest recovery are complete. |
| [ ] | P2 | Bard Inspiration | Guard policy mentions it; mechanics not trusted. | Bardic Inspiration die grant/use/expire, Cutting Words, and UI prompts are implemented. |
| [ ] | P2 | Cleric Channel Divinity | Not trusted. | Channel Divinity resources, Turn Undead, subclass options, and rest recovery work. |
| [ ] | P2 | Sorcerer Metamagic | Not trusted. | Sorcery points, metamagic options, conversion, and spell modification are implemented. |
| [ ] | P2 | Full subclass progression | Subclass effect data exists. | Each supported subclass has feature unlocks, resources, and tests at meaningful levels. |

### Monsters And Encounters

| Status | Priority | Rule Area | Current State | Done Definition |
| --- | --- | --- | --- | --- |
| [~] | P0 | Parsed monster stat blocks | Module parser fills monster defaults including vulnerabilities, condition immunities, and multiattack. | Uploaded modules produce combat-ready enemies with HP, AC, attacks, saves, speed, and abilities. |
| [~] | P0 | Enemy AI combat actions | AI turn service chooses attack/spell/actions and now uses enemy multiattack for attack count. | Enemies pick legal actions, respect resources, avoid impossible movement, and produce readable narration. |
| [~] | P1 | Monster traits | First slices complete: damage resistance/immunity/vulnerability data is preserved, condition immunity blocks control conditions, multiattack feeds AI turn limits, Pack Tactics grants attack advantage, damage-type Recharge abilities are parsed/preserved/refreshed/usable by enemy AI including cone/line/radius template targeting, area/multi-target breath-style damage, Recharge failed-save condition riders, and Legendary Resistance is parsed/preserved/consumed on failed enemy spell saves. | Resistance, immunity, condition immunity, multiattack, recharge, pack tactics, legendary resistance are represented. |
| [~] | P1 | Encounter balance | First backend estimator exists: combat init stores party size, average level, monster XP, adjusted XP, multiplier, thresholds, and easy/medium/hard/deadly difficulty in `game_state.encounter_balance`. Full encounter builder still needs terrain, roles, objectives, and action-economy tuning. | Encounter builder estimates difficulty from party size/level, action economy, and terrain. |
| [~] | P2 | Legendary/lair actions | First backend resource slice exists: legendary actions are parsed/preserved on enemies, per-round uses are initialized/refreshed, and spending is covered by unit tests. Full out-of-turn action prompts/resolution and lair actions are not implemented. | Boss encounters can act outside normal turns and show clear UI prompts/logs. |
| [ ] | P2 | Environmental hazards | Partial narrative. | Traps, surfaces, falling, fire, poison gas, difficult terrain, and cover are rule-backed. |

### Exploration And Campaign Rules

| Status | Priority | Rule Area | Current State | Done Definition |
| --- | --- | --- | --- | --- |
| [x] | P0 | DM style lock | Campaign-start style selection is persisted and injected into prompts. | Style cannot mutate mid-session and affects tone only, not core math. |
| [x] | P0 | AI companion reactions | DM agent separates main narration from companion reactions. | Companions react without crowding out main scene output or changing backend schema. |
| [~] | P0 | Campaign memory/state delta | State applicator and campaign delta services exist. | NPC registry, quest log, world flags, party resources, and consequences persist across sessions. |
| [~] | P1 | Rest rules | Rest endpoint restores long/short rest HP, hit dice, spell slots, several class resources, exhaustion reduction, interrupted rests that grant no recovery, and Wizard Arcane Recovery on short rest. Remaining work is richer rest-risk UI, duration validation, and expanded class-specific recovery coverage. | Short/long rest restore correct HP, hit dice, spell slots, features, exhaustion, and interrupted rest outcomes. |
| [~] | P1 | Inventory/equipment economy | Buy/sell/transfer/use item services exist, consumables can apply direct effects, Arrows/Bolts purchases update compatible weapon ammunition when possible, combat can consume tracked ammo/thrown weapon copies, and two-handed weapons now conflict with equipped shields. Remaining work is fuller weapon-slot/offhand enforcement, attunement if used, richer item actions, and multiplayer inventory UX. | Item ownership, equipment slots, attunement if used, consumables, gold, ammo, and multiplayer permissions are covered. |
| [~] | P1 | Stealth and perception procedures | Backend helpers exist for passive perception/investigation, best party passive score, 5e-style group stealth, surprise from ambusher Stealth totals vs passive Perception, light/darkvision visibility, noise-adjusted detection DCs, and hidden-state resolution. Remaining work is mostly frontend surfacing, scene authoring inputs, and broader playtest coverage. | Passive perception, group stealth, surprise, hidden condition, light, and noise are rule-backed. |
| [~] | P1 | Traps and investigation | Backend passive discovery exists for hidden traps, secret doors, clues, and mechanisms. Triggered trap resolution rolls saves and damage, attack-roll traps compare configured attack bonuses to target AC, and `state_delta` can apply trigger/attack/disarm/update outcomes while recording scene-level trap state. Remaining work is mostly frontend surfacing and broader playtest coverage. | Detect, disarm, trigger, save/attack, damage, and persistent trap state are represented. |
| [ ] | P2 | Travel and survival | Not systematic. | Pace, navigation, foraging, random encounters, exhaustion, weather, and mounts are implemented. |
| [ ] | P2 | Social systems | Mostly AI/narrative. | Reputation, factions, NPC disposition, persuasion/deception/intimidation consequences persist and affect options. |

## Experience Quality TODO

### P0 Stable Playable Loop

- [ ] Run a full single-player happy-path playthrough from login -> module -> character -> opening scene -> skill check -> combat -> rest -> checkpoint restore.
- [ ] Run a full 4-player multiplayer happy-path playthrough from create room -> join -> claim characters -> start -> exploration action -> combat -> reactions -> end combat.
- [ ] Verify every visible combat button either performs a legal action or shows a useful disabled/error state.
- [ ] Verify Adventure skill-check options still open the dice flow and produce success/failure state changes.
- [ ] Verify manual natural-language combat actions do not bypass movement, turn ownership, or action economy.
- [ ] Verify combat can end and return to Adventure without stale loading, stale prompts, or orphaned WS state.
- [ ] Verify page refresh during Adventure restores session state for single-player and multiplayer.
- [ ] Verify page refresh during Combat restores current turn, positions, HP, reactions, and prompts.
- [ ] Verify server restart behavior is understandable: session restore works where persisted, and WS reconnect errors are visible.

### P0 Multiplayer Isolation And Capacity

- [x] Document 50-user WebSocket smoke in `docs/multiplayer-loadtest.md`.
- [x] Run the 50-user load smoke against a fresh local backend and store the result in a dated note. 2026-05-28 local run on `127.0.0.1:8002`: 50 users, 13 rooms, 50 WS, cleanup OK, elapsed ~30.4s.
- [x] Run the 50-user load smoke twice in a row with the same prefix to test idempotent login/reuse. 2026-05-28 second run reused the same prefix/users, cleanup OK, elapsed ~55.5s.
- [x] Run 13-room test shape: 12 rooms with 4 players and 1 room with 2 players.
- [x] Verify one full room rejects overflow join while other rooms remain usable.
- [x] Verify typing, DM thinking, room state, combat update, and reaction prompt events never cross room boundaries. Load smoke verifies typing isolation and HTTP room/session isolation; 2026-05-28 integration coverage verifies DM thinking/responded, room state, combat update, and reaction prompt events stay inside the acting room. Same-room eligible-reactor-only visibility remains tracked separately as a UX/security decision.
- [x] Verify non-members cannot read another room snapshot, members list, or session restore snapshot.
- [x] Verify members leaving all rooms cleans WS state and dissolves rooms correctly when host leaves last. 2026-05-28: leave/kick now force-close affected WS connections after final broadcast; room dissolve closes all room sockets; tests cover state pruning and host-last dissolve.
- [x] Verify reconnect replaces only the same user in the same room, not another tab/user/room. 2026-05-28: `test_reconnect_replaces_only_the_same_user_in_the_same_room` covers same-user replacement without disturbing other users or rooms.
- [x] Verify one slow or broken WebSocket client does not block broadcast to the rest of the room. 2026-05-28: broadcast fan-out now runs per socket with timeout; tests cover broken send cleanup and slow-send timeout while roommates still receive events.

### P0 Multiplayer Authority And Fairness

- [x] Use voting for kick flow instead of giving host absolute unilateral removal power.
- [x] Verify kick vote threshold in 2-player, 3-player, and 4-player rooms. 2026-05-28: 2-player rooms reject kick votes, 3-player and 4-player rooms require 2 eligible yes votes, and removal clears the open vote.
- [x] Verify target cannot vote on their own kick proposal. 2026-05-28: target self-vote returns 400 and the target remains excluded from eligible voters/yes votes.
- [x] Verify host transfer works and does not grant action access to unclaimed characters. 2026-05-28: transfer keeps host permissions separate from character ownership; unclaimed `is_player=True` characters now reject member action attempts until claimed.
- [x] Verify only the character owner can act for a player character in multiplayer combat. 2026-05-28: non-owner room members are rejected from another player's `attack-roll` and `/end-turn`, and the turn index remains unchanged.
- [x] Verify players cannot skip enemy, AI companion, or other player turns through `/end-turn`. 2026-05-28: `/end-turn` rejects enemy/AI-controlled turns, AI companion turns, and non-owner attempts to end another player's turn.
- [x] Verify inactive/disconnected players have a clear takeover or timeout path. 2026-05-28: `/ai-takeover` succeeds for stale/offline current speakers, rejects online/self/single-player cases, records takeover metadata, and returns speak turn to the triggering online member.
- [x] Add audit logs for sensitive room events: kick vote, host transfer, character claim, room dissolve. 2026-05-28: sensitive room events write structured `GameLog.table_decision.audit` records with system log visibility and integration coverage.

### P1 Combat UX

- [x] Replace ambiguous combat errors with player-facing messages: out of range, no action, no slot, not your turn, target dead, blocked by condition. 2026-05-29: added frontend combat error mapping for stale turn tokens, not-your-turn, out-of-range, spent action/bonus/reaction/movement, no spell slot, invalid/dead target, and blocked-by-condition errors, with hook coverage across attack, spell, special action, movement/help, turn, death save, and skill-bar flows.
- [~] Show action economy state in UI: action, bonus action, reaction, movement remaining. Combat HUD already shows pips and movement; skill buttons now explain spent action/bonus/reaction/movement reasons.
- [ ] Show hover/selection preview for hit chance, damage range, cover, advantage/disadvantage, and resource cost.
- [ ] Show AoE templates for sphere, cone, line, cube, and aura spells.
- [ ] Make reaction prompts visually urgent but not blocking for non-reactors.
- [ ] Show clear before/after HP when Shield, Absorb Elements, Uncanny Dodge, or resistance retroactively changes damage.
- [x] Keep combat log readable: separate rules result, dice, narration, and state changes. 2026-05-29: combat HUD now renders structured log sections for rules, dice, narration, and state changes; attack, spell, AI turn, death save, reaction, maneuver, class feature, potion, grapple/shove, and offhand flows attach state-change metadata, with component and utility coverage.
- [x] Add a compact "why unavailable" tooltip to disabled skill bar actions.
- [~] Add target validation before submit, not only backend error after click. Skill bar blocks common target-required actions before submit; spell AoE and specialized actions still need deeper validation.
- [ ] Add animation/feedback for miss, hit, crit, save success, save failure, concentration break, death save result.

### P1 Adventure UX

- [ ] Make skill-check choices consistently show skill, DC, risk, and likely ability before clicking.
- [ ] Distinguish pure roleplay, dialogue, movement, investigation, rest, lore, and danger choices visually.
- [ ] Show recent consequences and quest updates after state delta is applied.
- [ ] Show party member reactions in a secondary area so they add flavor without burying main DM narration.
- [ ] Add "continue / ask / act" affordances that help players recover when unsure what to type.
- [ ] Add journal view for NPCs, quests, clues, locations, and unresolved threats.
- [ ] Add checkpoint restore UI that explains what will be restored.
- [ ] Verify long DM responses do not overflow, overlap, or freeze mobile/desktop layouts.

### P1 AI Quality

- [x] Add regression prompts for DM output schema: narrative, needs_check, state_delta, player_choices, companion_reactions. 2026-05-29: added offline DM schema regression prompts covering dialogue choices, pending skill checks, runtime wrapping, and companion handoff in `backend/tests/unit/test_dm_agent_schema_regression_prompts.py`.
- [x] Add tests that hostile prompt injection in player input cannot override rule math or JSON schema. 2026-05-29: added DM graph guard regression coverage for prompt injection and rule-cheating input, verifying blocked outputs keep the public schema and apply no state deltas; also expanded deterministic English rule-violation guard coverage.
- [x] Add scenario memory tests: NPC name, location, clue, quest state, and prior consequence survive several turns. 2026-05-29: added `test_state_applicator_preserves_scenario_memory_across_several_turns`, covering three sequential DM turns that preserve NPC facts/promises, location scene vibe, clues, quest status, world flags, and prior decisions.
- [x] Add combat narration tests that AI text never contradicts backend dice results. 2026-05-29: combat output validation now detects hit/miss/crit/save narration that contradicts backend `dice_results`, replaces conflicting text with an authoritative dice summary, and has regression coverage for player and AI-turn narration.
- [x] Add multiplayer table-decision tests where multiple groups submit actions and only the active/ready group is resolved. 2026-05-29: integration coverage exercises `/game/action` with two ready groups, verifies only the adjudicated group reaches the base DM prompt, clears only that group's pending actions/readiness, preserves the other ready group's queue, and advances focus to the next ready group.
- [x] Add fallback behavior when LLM call fails: preserve state, show retry, and avoid double-applying action. 2026-05-28: exploration `/game/action` returns retryable `llm_error` without applying state or persisting failed player logs; idempotency pending records are cleared instead of cached, and the frontend restores the submitted text while keeping existing prompts available for retry.
- [x] Add configurable model timeout and cancellation handling for DM thinking state. 2026-05-28: exploration DM calls are wrapped with `DM_AGENT_TIMEOUT_SECONDS` / `settings.dm_agent_timeout_seconds`, timeout cancels the stuck model task, returns retryable `llm_timeout`, preserves state, and clears multiplayer `dm_thinking`.

### P1 Persistence And Recovery

- [x] Audit every mutation of SQLAlchemy JSON fields for top-level assignment and `flag_modified`. 2026-05-28: added an AST regression test that derives JSON columns from SQLAlchemy models and scans `backend/api` + `backend/services` for ORM JSON in-place mutations without explicit top-level assignment or `flag_modified`.
- [x] Add tests for refresh/reconnect during pending reaction prompt.
- [x] Add tests for refresh/reconnect during DM thinking. 2026-05-28: multiplayer actions persist `dm_thinking` in room state until DM response/failure clears it; HTTP room refresh and fresh WS `room_state_updated` restore the pending indicator, with frontend hook coverage for loading recovery.
- [x] Add tests for duplicate HTTP submit on slow network. Absorb Elements reaction duplicate POST is idempotent; movement, combat action, attack-roll, and spell-roll reject stale turn tokens; 2026-05-28 exploration `/game/action` idempotency tests cover cached replay, mismatched payload rejection, and in-flight duplicate rejection.
- [x] Add idempotency keys or turn tokens to state-changing combat and exploration endpoints. Combat move/action/attack-roll/spell-roll/spell/end-turn/ai-turn accept optional turn tokens; 2026-05-28 `/game/action` accepts optional `idempotency_key`, caches completed exploration responses, and rejects pending duplicate submits.
- [~] Add cleanup for stale pending reactions, stale group readiness, and abandoned WS connections. Combat reaction decline now clears pending attack/spell prompts, and already-resolved reactions are safe to resubmit; group readiness and abandoned WS cleanup still need broader coverage.
- [x] Add database migration readiness check for local SQLite -> Postgres path. 2026-05-29: added `backend/check_migration_readiness.py`, which performs an offline preflight for PostgreSQL target URL, source SQLite table/column coverage against current ORM metadata, JSON column parseability, and Alembic single-head revision chain.
- [x] Add production-like seeded scenario that can be used for repeatable smoke tests. 2026-05-29: added `backend/seed_smoke_scenario.py` and `services/smoke_scenario_seed.py` for an idempotent parsed-module + player + AI companion + session + active combat seed, documented in `docs/smoke-seed-scenario.md`.

### P2 CRPG Depth

- [ ] Build encounter templates with terrain, cover, objectives, enemy roles, and environmental hazards.
- [ ] Add inspectable enemy sheets with known/unknown stats based on perception/investigation.
- [ ] Add loot, treasure, shop, item rarity, and consumable economy loops.
- [ ] Add tactical AI roles: striker, controller, defender, healer, skirmisher.
- [ ] Add companion approval/disapproval and personal quest hooks.
- [ ] Add branching quest state with fail-forward consequences.
- [ ] Add map/location graph so exploration choices move through places, not only text scenes.
- [ ] Add save-slot management and campaign timeline view.

## Pressure Test Checklist

### Local Preflight

- [ ] Backend starts cleanly on a chosen port.
- [ ] Frontend starts cleanly and points to the backend.
- [ ] Database is either fresh or intentionally seeded.
- [ ] A parsed module exists or load tests seed one without invoking the LLM parser.
- [ ] Model credentials are available for manual AI playthroughs.
- [ ] Browser console is open and cleared before each feature test.
- [ ] Backend terminal/log is cleared before each feature test.

### Automated Checks

- [ ] Run backend tests: `python -m pytest backend/tests -q`.
- [x] Run targeted spell action-economy tests. 2026-05-28: `python -m pytest backend/tests/unit/test_combat_spell_roll_service.py backend/tests/unit/test_combat_spell_prepare_service.py backend/tests/unit/test_combat_pending_spells.py backend/tests/unit/test_combat_direct_spell_service.py backend/tests/unit/test_combat_spell_confirm_service.py -q` passed, 34 tests.
- [x] Run combat endpoint regression after spell action-economy changes. 2026-05-28: `python -m pytest backend/tests/integration/test_combat_endpoints.py -q` passed, 36 tests.
- [x] Run targeted monster trait tests. 2026-05-28: `python -m pytest backend/tests/unit/test_module_parser_helpers.py backend/tests/unit/test_game_combat_setup_service.py backend/tests/unit/test_combat_turn_limits_service.py backend/tests/unit/test_combat_spell_effects.py backend/tests/integration/test_combat_endpoints.py -q` passed, 81 tests.
- [x] Run targeted Pack Tactics tests. 2026-05-28: `python -m pytest backend/tests/unit/test_combat_ai_attack_service.py backend/tests/unit/test_module_parser_helpers.py backend/tests/unit/test_combat_turn_limits_service.py -q` passed, 22 tests; combat endpoint regression passed, 37 tests.
- [ ] Run frontend tests: `cd frontend && npm test -- --run`.
- [ ] Run frontend build: `cd frontend && npm run build`.
- [ ] Run frontend lint when touching frontend code: `cd frontend && npm run lint`.
- [x] Run OpenAPI/type generation after backend schema changes. 2026-05-28: regenerated `backend/openapi.json` and `frontend/src/types/api.d.ts` after adding `idempotency_key` and retryable action responses.
- [ ] Run multiplayer load smoke when touching rooms, WS, access control, combat broadcast, or session restore.

### Manual Browser Flow: Single Player

- [ ] Register/login.
- [ ] Upload or select a parsed module.
- [ ] Create a character with spells/equipment.
- [ ] Start a session with a selected locked DM style.
- [ ] Click a normal choice.
- [ ] Click a skill-check choice and resolve the roll.
- [ ] Use free-text action.
- [ ] Trigger combat.
- [ ] Move, attack, cast spell, end turn.
- [ ] Take damage, react where eligible, resolve death-save edge if possible.
- [ ] End combat and return to Adventure.
- [ ] Rest/checkpoint/restore.

### Manual Browser Flow: Four Players

- [ ] Create room as host.
- [ ] Join with three guests.
- [ ] Claim one character per real player.
- [ ] Fill AI companions only when needed and verify max party shape remains sane.
- [ ] Start ready flow.
- [ ] Submit exploration actions from different players.
- [ ] Verify speaking/action ownership and group readiness.
- [ ] Trigger combat and verify each player only controls their own character.
- [ ] Decide and verify whether reaction prompts should be visible only to the eligible reactor; current backend behavior room-broadcasts `reaction_prompt` in `combat_update`, while cross-room leakage is covered by integration tests.
- [ ] Refresh one guest during combat and verify restore.
- [ ] Disconnect/reconnect one guest and verify WS online state.
- [ ] Leave room in different orders and verify cleanup.

### Manual Browser Flow: 50 Online Across Rooms

- [ ] Run scripted 50-user WS smoke.
- [ ] While load test is running, manually open one room and verify UI remains responsive.
- [ ] Trigger typing events in one room and verify no cross-room event leak.
- [ ] Trigger one combat update in a room and verify unrelated rooms do not refresh.
- [ ] Watch backend memory/CPU/log volume for obvious runaway behavior.
- [ ] Confirm all created test rooms clean up or are intentionally left as dissolved records.

## Suggested Implementation Order

1. P0 recovery and idempotency: duplicate submit, refresh during pending reaction, stale pending state cleanup. First slice complete for pending combat reactions and stale combat turn-token protection on high-frequency combat actions.
2. P0/P1 multiplayer pressure: repeat the 50-user load smoke and add missing assertions from real failures.
3. P1 combat UX: action economy display, unavailable reasons, reaction before/after HP clarity.
4. P1 spell system: unify spell target/area/slot/upcast/condition application before adding many more spells. First slice complete for action economy: action cantrips consume action, bonus-action spells consume bonus action, and reaction spells are rejected from ordinary cast flows.
5. P1 monster traits: multiattack, resistances, immunities, condition immunity, recharge. First slices complete for condition immunity, multiattack turn limits, Pack Tactics, damage-type Recharge action execution, cone/line/radius Recharge template targeting, breath-style Recharge multi-target damage, failed-save Recharge condition riders, Legendary Resistance against failed enemy spell/control/reaction saves, and Legendary Action resource initialization/refresh; non-condition Recharge rider effects and full legendary/lair action resolution remain.
6. P1 exploration rules: stealth, perception, traps, rest consequences, travel/exhaustion.
7. P2 CRPG depth: encounter templates, companion approval, branching quest state, loot economy.

## Update Rules

- When a TODO becomes implemented, add the commit or test file in a short note near the row.
- Do not mark a row `[x]` unless there is either automated coverage or a recorded manual playthrough.
- Prefer one focused feature plus tests per commit.
- Keep public API fields stable unless a schema change is deliberate and OpenAPI/types are regenerated.
- Keep AI output advisory for narration/intent; backend remains authoritative for rules and state.
