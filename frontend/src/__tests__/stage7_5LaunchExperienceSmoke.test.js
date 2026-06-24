import { describe, expect, it } from 'vitest'

import {
  buildLaunchExperiencePayload,
  collectBlockingBrowserEvents,
  normalizeOrigin,
  parseArgs,
  validateRequiredArgs,
} from '../../../scripts/stage7_5_launch_experience_smoke.mjs'

function passingChecks(overrides = {}) {
  return {
    login_path: '/',
    login_token_present: true,
    exploration_session_api_ok: true,
    exploration_session_combat_inactive: true,
    exploration_player_present: true,
    exploration_current_scene_present: true,
    exploration_location_graph_present: true,
    adventure_path: '/adventure/explore-1',
    adventure_loaded: true,
    adventure_dialogue_panel_present: true,
    adventure_response_box_present: true,
    adventure_recovery_buttons_count: 3,
    adventure_free_speak_present: true,
    adventure_top_buttons_count: 7,
    adventure_tool_buttons_count: 3,
    journal_opened: true,
    map_opened: true,
    loot_opened: true,
    exploration_loot_api_ok: true,
    exploration_loot_items_count: 0,
    combat_path: '/combat/combat-1',
    combat_loaded: true,
    combat_session_api_ok: true,
    combat_player_present: true,
    combat_api_ok: true,
    combat_session_active: true,
    combat_round: 2,
    combat_turn_order_count: 8,
    combat_entities_count: 8,
    combat_units_dom_count: 8,
    combat_enemy_dom_count: 4,
    combat_skill_bar_api_ok: true,
    combat_skill_bar_count: 10,
    combat_skill_bar_dom_count: 10,
    combat_end_turn_present: true,
    combat_end_turn_disabled: false,
    combat_log_present: true,
    combat_log_items_count: 7,
    combat_reaction_prompt_present: false,
    ...overrides,
  }
}

describe('Stage 7.5 launch-experience smoke helper', () => {
  it('parses public launch QA options and environment fallbacks', () => {
    const args = parseArgs([
      '--frontend-origin',
      'https://example.com/',
      '--username=qa-user',
      '--password',
      'secret',
      '--exploration-session-id',
      'explore-1',
      '--combat-session-id',
      'combat-1',
      '--artifact-tag',
      'stage7_5-20260624',
      '--timeout-ms=30000',
    ], {})

    expect(args.frontendOrigin).toBe('https://example.com')
    expect(args.username).toBe('qa-user')
    expect(args.password).toBe('secret')
    expect(args.explorationSessionId).toBe('explore-1')
    expect(args.combatSessionId).toBe('combat-1')
    expect(args.artifactTag).toBe('stage7_5-20260624')
    expect(args.timeoutMs).toBe(30000)
    expect(args.mutating).toBe(false)

    const envArgs = parseArgs([], {
      STAGE7_5_FRONTEND_ORIGIN: 'https://prod.example',
      STAGE7_5_USERNAME: 'env-user',
      STAGE7_5_PASSWORD: 'env-secret',
      STAGE7_5_EXPLORATION_SESSION_ID: 'env-explore',
      STAGE7_5_COMBAT_SESSION_ID: 'env-combat',
      STAGE7_5_ARTIFACT_TAG: 'env-tag',
      STAGE7_5_MUTATING: 'true',
    })
    expect(envArgs.frontendOrigin).toBe('https://prod.example')
    expect(envArgs.username).toBe('env-user')
    expect(envArgs.password).toBe('env-secret')
    expect(envArgs.explorationSessionId).toBe('env-explore')
    expect(envArgs.combatSessionId).toBe('env-combat')
    expect(envArgs.artifactTag).toBe('env-tag')
    expect(envArgs.mutating).toBe(true)
  })

  it('supports resettable mutating Stage 7.5 options', () => {
    const args = parseArgs([
      '--mutating',
      '--frontend-origin',
      'https://example.com/',
      '--username',
      'test',
      '--password',
      '123456',
      '--exploration-session-id',
      'stage7-5-session',
      '--combat-choice-text',
      'Start the training fight',
      '--claim-loot-id',
      'loot-token',
    ], {})

    expect(args.mutating).toBe(true)
    expect(args.explorationSessionId).toBe('stage7-5-session')
    expect(args.combatSessionId).toBe('stage7-5-session')
    expect(args.combatChoiceText).toBe('Start the training fight')
    expect(args.claimLootId).toBe('loot-token')
    expect(() => validateRequiredArgs(args)).not.toThrow()
  })

  it('fails fast for invalid or missing required options', () => {
    expect(() => parseArgs(['--frontend-origin'], {})).toThrow(/--frontend-origin requires a value/)
    expect(() => parseArgs(['--combat-session-id='], {})).toThrow(/--combat-session-id requires a value/)
    expect(() => parseArgs(['--timeout-ms=0'], {})).toThrow(/--timeout-ms must be a positive number/)
    expect(() => parseArgs([], { STAGE7_5_MUTATING: 'maybe' })).toThrow(/STAGE7_5_MUTATING must be a boolean/)
    expect(() => parseArgs(['--typo'], {})).toThrow(/Unknown option: --typo/)
    expect(() => normalizeOrigin('ftp://example.com')).toThrow(/http\(s\) origin/)

    expect(() => validateRequiredArgs(parseArgs([], {}))).toThrow(
      /Missing required Stage 7\.5 smoke option/,
    )
  })

  it('marks the payload ready only when exploration tools, Combat, and browser checks pass', () => {
    const payload = buildLaunchExperiencePayload({
      browserErrors: [],
      checks: passingChecks(),
      combatSessionId: 'combat-1',
      explorationSessionId: 'explore-1',
      frontendOrigin: 'https://example.com',
      username: 'qa-user',
    })

    expect(payload.ok).toBe(true)
    expect(payload.mode).toBe('stage7.5-launch-experience-smoke')
    expect(payload.assertions).toMatchObject({
      login_ok: true,
      exploration_adventure_ready: true,
      exploration_tools_ready: true,
      combat_ready: true,
      combat_controls_ready: true,
      no_browser_errors: true,
    })

    const blocked = buildLaunchExperiencePayload({
      browserErrors: [{ method: 'Runtime.exceptionThrown', message: 'boom' }],
      checks: passingChecks({ map_opened: false, combat_skill_bar_dom_count: 0 }),
      combatSessionId: 'combat-1',
      explorationSessionId: 'explore-1',
      frontendOrigin: 'https://example.com',
      username: 'qa-user',
    })

    expect(blocked.ok).toBe(false)
    expect(blocked.assertions.exploration_tools_ready).toBe(false)
    expect(blocked.assertions.combat_controls_ready).toBe(false)
    expect(blocked.assertions.no_browser_errors).toBe(false)
  })

  it('requires mutating round-trip evidence only when mutating mode is enabled', () => {
    const payload = buildLaunchExperiencePayload({
      browserErrors: [],
      checks: passingChecks({
        mutating_enabled: true,
        mutating_exploration_choice_clicked: true,
        mutating_combat_handoff_ok: true,
        mutating_attack_roll_ok: true,
        mutating_damage_roll_ok: true,
        mutating_target_hp_reduced: true,
        mutating_end_turn_ok: true,
        mutating_turn_advanced: true,
        mutating_loot_claim_ok: true,
        mutating_session_logs_count: 6,
      }),
      combatSessionId: 'stage7-5-session',
      explorationSessionId: 'stage7-5-session',
      frontendOrigin: 'https://example.com',
      mutating: { enabled: true, target_id: 'enemy_smoke_construct' },
      username: 'test',
    })

    expect(payload.ok).toBe(true)
    expect(payload.assertions.mutating_round_trip).toBe(true)
    expect(payload.mutating.enabled).toBe(true)

    const blocked = buildLaunchExperiencePayload({
      browserErrors: [],
      checks: passingChecks({
        mutating_enabled: true,
        mutating_exploration_choice_clicked: true,
        mutating_combat_handoff_ok: true,
        mutating_attack_roll_ok: true,
        mutating_damage_roll_ok: true,
        mutating_target_hp_reduced: true,
        mutating_end_turn_ok: true,
        mutating_turn_advanced: true,
        mutating_loot_claim_ok: false,
        mutating_session_logs_count: 6,
      }),
      combatSessionId: 'stage7-5-session',
      explorationSessionId: 'stage7-5-session',
      frontendOrigin: 'https://example.com',
      mutating: { enabled: true },
      username: 'test',
    })

    expect(blocked.ok).toBe(false)
    expect(blocked.assertions.mutating_round_trip).toBe(false)
  })

  it('collects blocking browser errors while ignoring benign aborted network loads', () => {
    const errors = collectBlockingBrowserEvents([
      {
        method: 'Runtime.consoleAPICalled',
        params: { type: 'error', args: [{ value: 'console exploded' }] },
      },
      {
        method: 'Network.loadingFailed',
        params: { errorText: 'net::ERR_ABORTED' },
      },
      {
        method: 'Log.entryAdded',
        params: { entry: { level: 'error', text: 'log exploded' } },
      },
      {
        method: 'Log.entryAdded',
        params: { entry: { level: 'error', text: 'GET /favicon.ico 404' } },
      },
    ])

    expect(errors).toEqual([
      { method: 'Runtime.consoleAPICalled', message: 'console exploded' },
      { method: 'Log.entryAdded', message: 'log exploded' },
    ])
  })
})
