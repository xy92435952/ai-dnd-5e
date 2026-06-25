import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import {
  STAGE8_SUITES,
  buildStage8GatePayload,
  checkMatrixFiles,
  parseArgs,
} from '../../../scripts/stage8_comprehensive_gate.mjs'

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', '..')
const stage8Script = path.join(repoRoot, 'scripts', 'stage8_comprehensive_gate.mjs')

function runStage8(args, { expectFailure = false } = {}) {
  try {
    return execFileSync(process.execPath, [stage8Script, ...args], {
      cwd: repoRoot,
      encoding: 'utf8',
      stdio: 'pipe',
    })
  } catch (error) {
    if (!expectFailure) throw error
    return `${error.stdout || ''}${error.stderr || ''}`
  }
}

function writeStage75SmokeArtifact(overrides = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'stage8-stage7-5-'))
  const screenshotPaths = {}
  for (const name of ['exploration', 'journal', 'map', 'loot', 'combat']) {
    const screenshotPath = path.join(dir, `${name}.png`)
    fs.writeFileSync(screenshotPath, 'png', 'utf8')
    screenshotPaths[name] = screenshotPath
  }
  const combatMutatingPath = path.join(dir, 'combat-mutating.png')
  fs.writeFileSync(combatMutatingPath, 'png', 'utf8')
  screenshotPaths.combat_mutating = combatMutatingPath
  const filePath = path.join(dir, 'stage7_5-mutating.json')
  fs.writeFileSync(filePath, `${JSON.stringify({
    ok: true,
    mode: 'stage7.5-launch-experience-smoke',
    created_at: '2026-06-25T00:25:59.282Z',
    frontend_origin: 'https://www.ai5edm.top',
    username: 'test',
    exploration_session_id: 'session-1',
    combat_session_id: 'session-1',
    checks: {
      login_path: '/',
      login_token_present: true,
      exploration_session_api_ok: true,
      exploration_session_combat_inactive: true,
      exploration_player_present: true,
      exploration_current_scene_present: true,
      exploration_location_graph_present: true,
      adventure_path: '/adventure/session-1',
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
      combat_path: '/combat/session-1',
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
    screenshots: screenshotPaths,
    ...overrides,
  }, null, 2)}\n`, 'utf8')
  return filePath
}

describe('Stage 8 comprehensive gate', () => {
  it('parses Stage 8 gate options and validates required suite registry', () => {
    const args = parseArgs([
      '--json',
      '--require-stage7-5-evidence',
      '--stage7-5-evidence',
      'artifacts/stage7_5-mutating-result-20260625.json',
    ])

    expect(args.format).toBe('json')
    expect(args.requireStage75Evidence).toBe(true)
    expect(args.stage75Evidence).toEqual(['artifacts/stage7_5-mutating-result-20260625.json'])
    expect(STAGE8_SUITES).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ id: 'combat' }),
        expect.objectContaining({ id: 'production-parity' }),
      ]),
    )
  })

  it('reports the required suite files that are present in the repo', () => {
    const suites = checkMatrixFiles()
    expect(suites).toHaveLength(STAGE8_SUITES.length)
    expect(suites.every(suite => suite.ok)).toBe(true)
  })

  it('reports missing files in a custom suite without hiding the missing paths', () => {
    const suites = checkMatrixFiles([
      {
        id: 'missing-suite',
        requiredPaths: [
          'frontend/src/__tests__/stage8ComprehensiveGate.test.js',
          'missing/stage8-required-file.test.js',
        ],
      },
    ])

    expect(suites).toEqual([
      {
        id: 'missing-suite',
        ok: false,
        required_count: 2,
        missing: ['missing/stage8-required-file.test.js'],
      },
    ])
  })

  it('builds a ready payload when matrix files exist and no Stage 7.5 evidence is required', () => {
    const payload = buildStage8GatePayload({
      requireStage75Evidence: false,
      stage75Evidence: [],
    })

    expect(payload.ok).toBe(true)
    expect(payload.matrix_ok).toBe(true)
    expect(payload.stage7_5_evidence_ok).toBeNull()
  })

  it('verifies a Stage 7.5 mutating evidence artifact through the gate CLI', () => {
    const evidence = writeStage75SmokeArtifact()

    expect(runStage8([
      '--json',
      '--require-stage7-5-evidence',
      '--stage7-5-evidence',
      evidence,
    ])).toContain('"stage7_5_evidence_ok": true')
  })

  it('fails when Stage 7.5 evidence is required but missing', () => {
    expect(runStage8([
      '--json',
      '--require-stage7-5-evidence',
    ], { expectFailure: true })).toContain('"stage7_5_evidence_ok": false')
  })

  it('fails when provided Stage 7.5 evidence does not satisfy the shared verifier', () => {
    const evidence = writeStage75SmokeArtifact({
      assertions: {
        login_ok: true,
        exploration_adventure_ready: true,
        exploration_tools_ready: true,
        combat_ready: true,
        combat_controls_ready: true,
        mutating_round_trip: false,
        no_browser_errors: true,
      },
    })

    const output = runStage8([
      '--json',
      '--stage7-5-evidence',
      evidence,
    ], { expectFailure: true })

    expect(output).toContain('"stage7_5_evidence_ok": false')
    expect(output).toContain('assertions.mutating_round_trip must be true')
  })
})
