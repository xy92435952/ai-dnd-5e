import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', '..')
const verifyScript = path.join(repoRoot, 'scripts', 'verify_stage7_evidence.mjs')

function runVerifier(args) {
  return execFileSync(process.execPath, [
    verifyScript,
    ...args,
  ], {
    cwd: repoRoot,
    encoding: 'utf8',
    stdio: 'pipe',
  })
}

function validFeatherFallManifest(overrides = {}) {
  return {
    ok: true,
    mode: 'feather-fall-adventure-browser-smoke',
    decision: 'accept',
    reaction_type: 'feather_fall',
    artifact_tag: 'unit',
    prompt: {
      dialogName: 'Feather Fall',
      dialogDescription: 'Mara Quickstep can protect Smoke Sentinel from Gatehouse drop shaft. Prevents 6 fall damage Costs 1st spell slot + reaction Cast prevents 6 fall damage. Decline lets Smoke Sentinel take the saved fall damage.',
    },
    resolved: {
      pending_cleared: true,
      hp_current: 28,
      caster_slots: { '1st': 0 },
    },
    assertions: {
      pending_cleared: true,
      fall_damage: 6,
      before_hp: 28,
      expected_hp: 28,
      actual_hp: 28,
      hp_max: 28,
      expected_caster_1st_slots: 0,
      actual_caster_1st_slots: 0,
    },
    screenshots: {
      prompt: 'prompt.png',
      resolved: 'resolved.png',
    },
    manifest: 'manifest.json',
    ...overrides,
  }
}

function validLocalHttpSmoke(overrides = {}) {
  return {
    ok: true,
    mode: 'stage7-local-http-smoke',
    created_at: '2026-06-24T04:40:01.2789481Z',
    base_url: 'http://127.0.0.1:8002',
    health: {
      status: 'ok',
      version: '0.1.0',
    },
    seed: {
      username: 'test_stage7_local',
      module_id: 'module-1',
      character_id: 'char-1',
      session_id: 'session-1',
      combat_state_id: 'combat-1',
    },
    checks: {
      login_token_present: true,
      session_id: 'session-1',
      session_combat_active: true,
      current_scene_present: true,
      combat_session_id: 'session-1',
      combat_round: 1,
      combat_turn_order_count: 4,
      combat_entities_count: 4,
      skill_bar_entity_id: 'char-1',
      skill_bar_count: 10,
    },
    assertions: {
      health_ok: true,
      login_ok: true,
      adventure_session_loaded: true,
      combat_loaded: true,
      skill_bar_loaded: true,
    },
    logs: {
      stdout: 'stdout.log',
      stderr: 'stderr.log',
    },
    ...overrides,
  }
}

function validPublicBrowserSmoke(overrides = {}) {
  return {
    ok: true,
    mode: 'stage7-public-browser-smoke',
    created_at: '2026-06-24T06:40:01.278Z',
    frontend_origin: 'https://example.com',
    session_id: 'session-1',
    username: 'stage7-public-user',
    checks: {
      login_path: '/',
      login_token_present: true,
      adventure_path: '/adventure/session-1',
      adventure_loaded: true,
      adventure_redirected_to_combat: false,
      adventure_route_ready: true,
      session_api_ok: true,
      session_id_matches: true,
      session_combat_active: true,
      current_scene_present: true,
      combat_path: '/combat/session-1',
      combat_loaded: true,
      combat_api_ok: true,
      combat_round: 1,
      combat_turn_order_count: 4,
      combat_entities_count: 4,
      skill_bar_entity_id: 'char-1',
      skill_bar_count: 10,
      skill_bar_dom_count: 10,
    },
    assertions: {
      login_ok: true,
      adventure_loaded: true,
      adventure_route_ready: true,
      combat_loaded: true,
      combat_session_active: true,
      skill_bar_loaded: true,
      no_browser_errors: true,
    },
    browser: {
      errors: [],
    },
    screenshots: {
      adventure: 'adventure.png',
      combat: 'combat.png',
    },
    ...overrides,
  }
}

function validStage75LaunchSmoke(overrides = {}) {
  return {
    ok: true,
    mode: 'stage7.5-launch-experience-smoke',
    created_at: '2026-06-25T00:25:59.282Z',
    frontend_origin: 'https://example.com',
    username: 'test',
    exploration_session_id: 'stage7-5-session',
    combat_session_id: 'stage7-5-session',
    checks: {
      login_path: '/',
      login_token_present: true,
      exploration_session_api_ok: true,
      exploration_session_combat_inactive: true,
      exploration_player_present: true,
      exploration_current_scene_present: true,
      exploration_location_graph_present: true,
      adventure_path: '/adventure/stage7-5-session',
      adventure_loaded: true,
      adventure_dialogue_panel_present: true,
      adventure_response_box_present: true,
      adventure_recovery_buttons_count: 3,
      adventure_free_speak_present: true,
      adventure_top_buttons_count: 6,
      adventure_tool_buttons_count: 3,
      journal_opened: true,
      map_opened: true,
      loot_opened: true,
      exploration_loot_api_ok: true,
      exploration_loot_items_count: 2,
      combat_path: '/combat/stage7-5-session',
      combat_loaded: true,
      combat_session_api_ok: true,
      combat_player_present: true,
      combat_api_ok: true,
      combat_session_active: true,
      combat_round: 1,
      combat_turn_order_count: 4,
      combat_entities_count: 4,
      combat_units_dom_count: 2,
      combat_enemy_dom_count: 0,
      combat_skill_bar_api_ok: true,
      combat_skill_bar_count: 10,
      combat_skill_bar_dom_count: 10,
      combat_end_turn_present: true,
      combat_end_turn_disabled: true,
      combat_log_present: true,
      combat_log_items_count: 16,
      combat_reaction_prompt_present: false,
      mutating_enabled: true,
      mutating_exploration_choice_clicked: true,
      mutating_combat_handoff_ok: true,
      mutating_attack_roll_ok: true,
      mutating_damage_roll_ok: true,
      mutating_target_hp_reduced: true,
      mutating_end_turn_ok: true,
      mutating_turn_advanced: true,
      mutating_loot_claim_ok: true,
      mutating_session_logs_count: 7,
    },
    assertions: {
      login_ok: true,
      exploration_adventure_ready: true,
      exploration_tools_ready: true,
      combat_ready: true,
      combat_controls_ready: true,
      mutating_round_trip: true,
      no_browser_errors: true,
    },
    browser: {
      errors: [],
    },
    mutating: {
      enabled: true,
      target_id: 'enemy-smoke',
      before_target_hp: 4,
      after_damage_target_hp: 0,
      target_hp_reduced: true,
      turn_advanced: true,
      loot_claim_ok: true,
      loot_id: 'loot_gear_gate_token_0',
    },
    screenshots: {
      exploration: 'exploration.png',
      journal: 'journal.png',
      map: 'map.png',
      loot: 'loot.png',
      combat: 'combat.png',
      combat_mutating: 'combat-mutating.png',
    },
    ...overrides,
  }
}

function writeManifest(data) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'stage7-evidence-verifier-'))
  const filePath = path.join(dir, 'manifest.json')
  fs.writeFileSync(filePath, `${JSON.stringify(data, null, 2)}\n`, 'utf8')
  return filePath
}

function writeLocalHttpSmoke(data, { stdout = '', stderr = '' } = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'stage7-local-http-smoke-'))
  const stdoutPath = path.join(dir, 'stdout.log')
  const stderrPath = path.join(dir, 'stderr.log')
  fs.writeFileSync(stdoutPath, stdout, 'utf8')
  fs.writeFileSync(stderrPath, stderr, 'utf8')
  const filePath = path.join(dir, 'local-http-smoke.json')
  fs.writeFileSync(filePath, `${JSON.stringify({
    ...data,
    logs: {
      stdout: stdoutPath,
      stderr: stderrPath,
    },
  }, null, 2)}\n`, 'utf8')
  return filePath
}

function writePublicBrowserSmoke(data, { adventure = 'png', combat = 'png' } = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'stage7-public-browser-smoke-'))
  const adventurePath = path.join(dir, 'adventure.png')
  const combatPath = path.join(dir, 'combat.png')
  fs.writeFileSync(adventurePath, adventure, 'utf8')
  fs.writeFileSync(combatPath, combat, 'utf8')
  const filePath = path.join(dir, 'public-browser-smoke.json')
  fs.writeFileSync(filePath, `${JSON.stringify({
    ...data,
    screenshots: {
      adventure: adventurePath,
      combat: combatPath,
    },
  }, null, 2)}\n`, 'utf8')
  return filePath
}

function writeStage75LaunchSmoke(data) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'stage7-5-launch-smoke-'))
  const screenshots = {}
  for (const key of ['exploration', 'journal', 'map', 'loot', 'combat', 'combat_mutating']) {
    if (!data.screenshots?.[key]) continue
    const screenshotPath = path.join(dir, `${key}.png`)
    fs.writeFileSync(screenshotPath, 'png', 'utf8')
    screenshots[key] = screenshotPath
  }
  const filePath = path.join(dir, 'stage7-5-launch-smoke.json')
  fs.writeFileSync(filePath, `${JSON.stringify({
    ...data,
    screenshots,
  }, null, 2)}\n`, 'utf8')
  return filePath
}

describe('Stage 7 evidence verifier CLI', () => {
  it('fails fast when type options are missing or invalid', () => {
    expect(() => runVerifier([])).toThrow(/At least one Stage 7 evidence file is required/)
    expect(() => runVerifier(['--typo'])).toThrow(/Unknown option: --typo/)
    expect(() => runVerifier(['--type'])).toThrow(/--type requires a value/)
    expect(() => runVerifier(['--type', '--no-file-check'])).toThrow(/--type requires a value/)
    expect(() => runVerifier(['--type='])).toThrow(/--type requires a value/)
    expect(() => runVerifier(['--type', 'browser-smoke'])).toThrow(
      /--type must be one of: auto, feather-fall, multiplayer-load, postdeploy-healthcheck, local-http-smoke, public-browser-smoke, stage7\.5-launch-smoke/,
    )
  })

  it('accepts an explicit evidence type for valid smoke artifacts', () => {
    const manifest = writeManifest(validFeatherFallManifest())

    expect(runVerifier([
      '--type',
      'feather-fall',
      '--no-file-check',
      manifest,
    ])).toContain('Verified 1 Stage 7 evidence file(s).')
  })

  it('accepts local HTTP smoke artifacts as Stage 7 evidence', () => {
    const manifest = writeLocalHttpSmoke(validLocalHttpSmoke(), {
      stdout: 'INFO: 127.0.0.1:8002 - "GET /health HTTP/1.1" 200 OK\n',
      stderr: '',
    })

    expect(runVerifier([
      '--type',
      'local-http-smoke',
      manifest,
    ])).toContain('Verified 1 Stage 7 evidence file(s).')
  })

  it('rejects local HTTP smoke logs with stop markers', () => {
    const manifest = writeLocalHttpSmoke(validLocalHttpSmoke(), {
      stdout: 'INFO: started\n',
      stderr: 'Traceback (most recent call last):\n',
    })

    expect(() => runVerifier([
      manifest,
    ])).toThrow(/stderr log contains stop markers/)
  })

  it('accepts public browser smoke artifacts as Stage 7 evidence', () => {
    const manifest = writePublicBrowserSmoke(validPublicBrowserSmoke())

    expect(runVerifier([
      '--type',
      'public-browser-smoke',
      manifest,
    ])).toContain('Verified 1 Stage 7 evidence file(s).')
  })

  it('accepts public browser smoke artifacts that hand off from Adventure to Combat', () => {
    const base = validPublicBrowserSmoke()
    const manifest = writePublicBrowserSmoke(validPublicBrowserSmoke({
      checks: {
        ...base.checks,
        adventure_path: '/combat/session-1',
        adventure_loaded: false,
        adventure_redirected_to_combat: true,
        adventure_route_ready: true,
      },
    }))

    expect(runVerifier([
      '--type',
      'public-browser-smoke',
      manifest,
    ])).toContain('Verified 1 Stage 7 evidence file(s).')
  })

  it('rejects public browser smoke artifacts with captured browser errors', () => {
    const manifest = writePublicBrowserSmoke(validPublicBrowserSmoke({
      browser: {
        errors: [{ method: 'Runtime.exceptionThrown', message: 'boom' }],
      },
    }))

    expect(() => runVerifier([
      manifest,
    ])).toThrow(/browser\.errors must be empty/)
  })

  it('accepts Stage 7.5 launch-experience mutating smoke artifacts as evidence', () => {
    const manifest = writeStage75LaunchSmoke(validStage75LaunchSmoke())

    expect(runVerifier([
      '--type',
      'stage7.5-launch-smoke',
      manifest,
    ])).toContain('Verified 1 Stage 7 evidence file(s).')
  })

  it('accepts Stage 7.5 read-only launch-experience smoke artifacts as evidence', () => {
    const base = validStage75LaunchSmoke()
    const manifest = writeStage75LaunchSmoke(validStage75LaunchSmoke({
      checks: {
        ...base.checks,
        exploration_loot_items_count: 0,
        mutating_enabled: false,
        mutating_exploration_choice_clicked: false,
        mutating_combat_handoff_ok: false,
        mutating_attack_roll_ok: false,
        mutating_damage_roll_ok: false,
        mutating_target_hp_reduced: false,
        mutating_end_turn_ok: false,
        mutating_turn_advanced: false,
        mutating_loot_claim_ok: false,
        mutating_session_logs_count: 0,
      },
      mutating: null,
      screenshots: {
        exploration: 'exploration.png',
        journal: 'journal.png',
        map: 'map.png',
        loot: 'loot.png',
        combat: 'combat.png',
      },
    }))

    expect(runVerifier([
      manifest,
    ])).toContain('Verified 1 Stage 7 evidence file(s).')
  })

  it('rejects Stage 7.5 mutating artifacts that do not prove loot persistence', () => {
    const base = validStage75LaunchSmoke()
    const manifest = writeStage75LaunchSmoke(validStage75LaunchSmoke({
      checks: {
        ...base.checks,
        mutating_loot_claim_ok: false,
      },
      assertions: {
        ...base.assertions,
        mutating_round_trip: false,
      },
      mutating: {
        ...base.mutating,
        loot_claim_ok: false,
      },
    }))

    expect(() => runVerifier([
      manifest,
    ])).toThrow(/assertions\.mutating_round_trip must be true/)
  })
})
