import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import {
  buildArtifact as buildStage8PublicArtifact,
  parseArgs as parseStage8PublicArgs,
  webSocketClientKind,
} from '../../../scripts/stage8_public_evidence_smoke.mjs'

import {
  STAGE8_REQUIRED_CI_JOBS,
  STAGE8_SUITES,
  buildStage8GatePayload,
  checkDeploymentWebSocketProxyFiles,
  checkMatrixFiles,
  evaluateStage8EvidenceManifest,
  parseArgs,
} from '../../../scripts/stage8_comprehensive_gate.mjs'

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', '..')
const stage8Script = path.join(repoRoot, 'scripts', 'stage8_comprehensive_gate.mjs')
const checkScript = path.join(repoRoot, 'scripts', 'check.sh')

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

function writePostdeployHealthArtifact(overrides = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'stage8-postdeploy-'))
  const filePath = path.join(dir, 'postdeploy-health.json')
  fs.writeFileSync(filePath, `${JSON.stringify({
    ready: true,
    healthReady: true,
    logsReady: true,
    generatedAt: '2026-06-25T00:25:59.282Z',
    healthChecks: [
      {
        url: 'https://www.ai5edm.top/api/health',
        ok: true,
        statusOk: true,
        status: 200,
        body: {
          status: 'ok',
          version: '0.1.0',
        },
      },
    ],
    logChecks: [],
    ...overrides,
  }, null, 2)}\n`, 'utf8')
  return filePath
}

function writeStage8PublicEvidenceArtifact(overrides = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'stage8-public-evidence-'))
  const filePath = path.join(dir, 'stage8-public-evidence.json')
  const base = buildStage8PublicArtifact({
    allowCombatSyncBlocker: false,
    apiOrigin: 'https://www.ai5edm.top/api',
    characterEconomy: {
      character: {
        detail_ok: true,
        hp_current: 11,
        hp_max: 11,
        id: 'character-stage8',
        name: 'Stage8 Hero',
      },
      checks: {
        character_detail_ok: true,
        fresh_character_create_ok: true,
        gold_decreased_on_buy: true,
        gold_increased_on_sell: true,
        gold_patch_ok: true,
        shop_buy_ok: true,
        shop_inventory_ok: true,
        shop_sell_ok: true,
      },
      economy: {
        buy_cost: 50,
        buy_gold_remaining: 60,
        gold_after_patch: 110,
        item_category: 'gear',
        item_name: 'Healing Potion',
        sell_gold_remaining: 85,
        sell_price: 25,
        shop_inventory_ok: true,
      },
    },
    createdAt: '2026-06-25T00:25:59.282Z',
    frontendOrigin: 'https://www.ai5edm.top',
    module: {
      id: 'module-stage8',
      name: 'Stage8 Module',
      source: 'existing',
    },
    multiplayer: {
      checks: {
        combat_sync_ok: true,
        game_started_ok: true,
        guest_joined_ok: true,
        guest_ws_pong_ok: true,
        host_ws_pong_ok: true,
        speak_turn_handoff_ok: true,
        two_browser_room_join_ok: true,
        websocket_online_ok: true,
      },
      combat_sync: {
        attempted: true,
        combat_active_guest: true,
        combat_active_host: true,
        combat_sync: true,
      },
      guest: {
        registered: true,
        user_id: 'guest-user',
        username: 'stage8_guest',
      },
      room: {
        current_speaker_after_handoff: 'guest-user',
        current_speaker_initial: 'host-user',
        guest_character_id: 'guest-character',
        host_character_id: 'host-character',
        member_count: 2,
        room_code: '234567',
        session_id: 'session-stage8',
      },
      websocket: {
        guest_event_count: 4,
        host_event_count: 4,
      },
    },
    username: 'test',
    user: {
      token: 'token',
      user_id: 'host-user',
    },
    wsApiBase: 'https://www.ai5edm.top/api',
  })
  const payload = {
    ...base,
    ...overrides,
    assertions: {
      ...base.assertions,
      ...(overrides.assertions || {}),
    },
    checks: {
      ...base.checks,
      ...(overrides.checks || {}),
    },
  }
  fs.writeFileSync(filePath, `${JSON.stringify(payload, null, 2)}\n`, 'utf8')
  return filePath
}

function writeFullStage8Manifest({ healthArtifact, mutate, publicStage8Artifact, stage75Artifact } = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'stage8-manifest-'))
  const stage75 = stage75Artifact || writeStage75SmokeArtifact()
  const health = healthArtifact || writePostdeployHealthArtifact()
  const publicStage8 = publicStage8Artifact || writeStage8PublicEvidenceArtifact()
  const filePath = path.join(dir, 'stage8-evidence-manifest.json')
  const manifest = {
    stage: 'stage8',
    generated_at: '2026-06-25T00:25:59.282Z',
    release: {
      branch: 'main',
      commit: '8c9be8b',
      frontend_origin: 'https://www.ai5edm.top',
      health_url: 'https://www.ai5edm.top/api/health',
    },
    suites: {
      'account-module-character': {
        evidence: [
          {
            id: 'deployed-login',
            result: 'pass',
            url: 'https://www.ai5edm.top/',
            notes: 'Public login/register sanity passed for the smoke account.',
          },
          {
            id: 'fresh-character-create',
            result: 'pass',
            file: publicStage8,
            notes: 'Stage 8 public API smoke created and restored a fresh character.',
          },
        ],
      },
      adventure: {
        evidence: [
          {
            id: 'exploration-tools',
            result: 'pass',
            file: stage75,
            notes: 'Stage 7.5 artifact includes Adventure, Journal, Map, and Loot screenshots.',
          },
          {
            id: 'skill-check-path',
            result: 'pass',
            command: 'npm --prefix frontend run test:stage7:reaction',
            notes: 'Adventure skill-check click path is covered by Adventure.smoke; Stage 7.5 provides the public replacement path.',
          },
        ],
      },
      combat: {
        evidence: [
          {
            id: 'stage7.5-mutating-smoke',
            result: 'pass',
            file: stage75,
          },
          {
            id: 'combat-log-reload',
            result: 'pass',
            file: stage75,
            notes: 'The mutating smoke refreshes Combat and records session log count after attack/damage/end-turn.',
          },
        ],
      },
      'loot-economy': {
        evidence: [
          {
            id: 'party-stash-claim',
            result: 'pass',
            file: stage75,
            notes: 'The mutating smoke claims loot_gear_gate_token_0 to party stash.',
          },
          {
            id: 'gold-or-shop-economy',
            result: 'pass',
            file: publicStage8,
            notes: 'Stage 8 public API smoke patched gold, bought an item, and sold it back.',
          },
        ],
      },
      multiplayer: {
        evidence: [
          {
            id: 'two-browser-room-join',
            result: 'pass',
            file: publicStage8,
            notes: 'Stage 8 public API/WS smoke connected host and guest clients in one room.',
          },
          {
            id: 'speak-turn-handoff',
            result: 'pass',
            file: publicStage8,
            notes: 'Stage 8 public API/WS smoke advanced speaker from host to guest.',
          },
          {
            id: 'combat-sync-or-blocker',
            result: 'pass',
            file: publicStage8,
            notes: 'Stage 8 public API/WS smoke verified a multiplayer combat sync artifact.',
          },
        ],
      },
      'production-parity': {
        evidence: [
          {
            id: 'github-actions-green',
            result: 'pass',
            url: 'https://github.com/xy92435952/ai-dnd-5e/actions',
            checks: {
              required_jobs_ok: true,
              jobs: STAGE8_REQUIRED_CI_JOBS,
            },
          },
          {
            id: 'postdeploy-healthcheck',
            result: 'pass',
            file: health,
            required_url: 'https://www.ai5edm.top/api/health',
          },
          {
            id: 'postgres-seed-reset',
            result: 'pass',
            command: 'python seed_smoke_scenario.py --slug stage7_5_launch --variant stage7-5 --username test --password 123456',
            checks: {
              seed_reset_ok: true,
            },
          },
        ],
      },
    },
  }

  if (mutate) mutate(manifest)
  fs.writeFileSync(filePath, `${JSON.stringify(manifest, null, 2)}\n`, 'utf8')
  return filePath
}

describe('Stage 8 comprehensive gate', () => {
  it('parses Stage 8 gate options and validates required suite registry', () => {
    const args = parseArgs([
      '--json',
      '--require-stage7-5-evidence',
      '--stage7-5-evidence',
      'artifacts/stage7_5-mutating-result-20260625.json',
      '--require-suite-evidence',
      '--evidence-manifest',
      'artifacts/stage8-evidence.json',
      '--allow-blockers',
      '--evidence-no-file-check',
    ])

    expect(args.format).toBe('json')
    expect(args.requireStage75Evidence).toBe(true)
    expect(args.stage75Evidence).toEqual(['artifacts/stage7_5-mutating-result-20260625.json'])
    expect(args.requireSuiteEvidence).toBe(true)
    expect(args.evidenceManifest).toBe('artifacts/stage8-evidence.json')
    expect(args.allowBlockers).toBe(true)
    expect(args.evidenceNoFileCheck).toBe(true)
    expect(STAGE8_SUITES).toEqual(
      expect.arrayContaining([
        expect.objectContaining({ id: 'combat' }),
        expect.objectContaining({ id: 'production-parity' }),
      ]),
    )
    expect(STAGE8_SUITES.every(suite => suite.evidenceRequirements.length > 0)).toBe(true)
  })

  it('parses the Stage 8 public evidence smoke options with API and WS defaults', () => {
    const args = parseStage8PublicArgs([
      '--frontend-origin',
      'https://www.ai5edm.top/',
      '--username',
      'test',
      '--password',
      '123456',
      '--artifact-tag',
      '20260625-test',
      '--allow-combat-sync-blocker',
    ], {})

    expect(args.frontendOrigin).toBe('https://www.ai5edm.top')
    expect(args.apiOrigin).toBe('https://www.ai5edm.top/api')
    expect(args.wsApiBase).toBe('https://www.ai5edm.top/api')
    expect(args.output).toContain('stage8-public-evidence-20260625-test.json')
    expect(args.allowCombatSyncBlocker).toBe(true)
  })

  it('falls back to the built-in Node WebSocket client when global WebSocket is unavailable', () => {
    expect(webSocketClientKind({})).toBe('node-fallback')
    expect(webSocketClientKind({ WebSocket: class FakeWebSocket {} })).toBe('native')
  })

  it('reports the required suite files that are present in the repo', () => {
    const suites = checkMatrixFiles()
    expect(suites).toHaveLength(STAGE8_SUITES.length)
    expect(suites.every(suite => suite.ok)).toBe(true)
  })

  it('keeps deployment WebSocket proxy templates wired for public multiplayer smoke', () => {
    const proxyFiles = checkDeploymentWebSocketProxyFiles()

    expect(proxyFiles).toHaveLength(3)
    expect(proxyFiles.map(file => file.file)).toEqual([
      'deploy.sh',
      'update_server.sh',
      'frontend/nginx.conf',
    ])
    expect(proxyFiles.every(file => file.ok)).toBe(true)
    for (const file of proxyFiles) {
      expect(file.checks.location).toBe(true)
      expect(file.checks.proxy_pass).toBe(true)
      expect(file.checks.upgrade_header).toBe(true)
      expect(file.checks.connection_upgrade).toBe(true)
      expect(file.checks.long_read_timeout).toBe(true)
    }
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

  it('keeps the standard check script wired to the Stage 8 suite-evidence gate', () => {
    const checkSource = fs.readFileSync(checkScript, 'utf8')

    expect(checkSource).toContain('STAGE8_REQUIRE_SUITE_EVIDENCE')
    expect(checkSource).toContain('--require-suite-evidence')
    expect(checkSource).toContain('STAGE8_EVIDENCE_MANIFEST')
    expect(checkSource).toContain('--evidence-manifest')
    expect(checkSource).toContain('STAGE8_ALLOW_BLOCKERS')
    expect(checkSource).toContain('--allow-blockers')
    expect(checkSource).toContain('STAGE8_EVIDENCE_NO_FILE_CHECK')
    expect(checkSource).toContain('--evidence-no-file-check')
  })

  it('builds a ready payload when matrix files exist and no Stage 7.5 evidence is required', () => {
    const payload = buildStage8GatePayload({
      allowBlockers: false,
      evidenceManifest: '',
      evidenceNoFileCheck: false,
      requireStage75Evidence: false,
      requireSuiteEvidence: false,
      stage75Evidence: [],
    })

    expect(payload.ok).toBe(true)
    expect(payload.matrix_ok).toBe(true)
    expect(payload.deployment_ws_proxy_ok).toBe(true)
    expect(payload.stage7_5_evidence_ok).toBeNull()
    expect(payload.suite_evidence_ok).toBeNull()
  })

  it('accepts a complete Stage 8 evidence manifest across every suite', () => {
    const manifest = writeFullStage8Manifest()
    const args = parseArgs([
      '--json',
      '--require-suite-evidence',
      '--evidence-manifest',
      manifest,
    ])
    const payload = buildStage8GatePayload(args)

    expect(payload.ok).toBe(true)
    expect(payload.suite_evidence_ok).toBe(true)
    expect(payload.suite_evidence.suites.every(suite => suite.ok)).toBe(true)
  })

  it('exposes the manifest evaluator for focused missing-requirement diagnostics', () => {
    const stage75 = writeStage75SmokeArtifact()
    const health = writePostdeployHealthArtifact()
    const manifest = JSON.parse(fs.readFileSync(writeFullStage8Manifest({
      healthArtifact: health,
      stage75Artifact: stage75,
      mutate(payload) {
        payload.suites.combat.evidence = payload.suites.combat.evidence
          .filter(item => item.id !== 'combat-log-reload')
      },
    }), 'utf8'))
    const result = evaluateStage8EvidenceManifest(manifest)

    expect(result.ok).toBe(false)
    expect(result.missing).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          suite_id: 'combat',
          requirement_id: 'combat-log-reload',
          status: 'missing',
        }),
      ]),
    )
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

  it('fails when suite evidence is required without a manifest', () => {
    const output = runStage8([
      '--json',
      '--require-suite-evidence',
    ], { expectFailure: true })

    expect(output).toContain('"suite_evidence_ok": false')
    expect(output).toContain('No Stage 8 evidence manifest provided')
  })

  it('fails when a manifest is missing a required suite evidence item', () => {
    const manifest = writeFullStage8Manifest({
      mutate(payload) {
        payload.suites['loot-economy'].evidence = payload.suites['loot-economy'].evidence
          .filter(item => item.id !== 'gold-or-shop-economy')
      },
    })
    const output = runStage8([
      '--json',
      '--require-suite-evidence',
      '--evidence-manifest',
      manifest,
    ], { expectFailure: true })

    expect(output).toContain('"suite_evidence_ok": false')
    expect(output).toContain('gold-or-shop-economy evidence is missing')
  })

  it('fails when a Stage 8 public evidence artifact is missing the required assertion', () => {
    const invalidPublicEvidence = writeStage8PublicEvidenceArtifact({
      assertions: {
        gold_or_shop_economy: false,
      },
    })
    const manifest = writeFullStage8Manifest({ publicStage8Artifact: invalidPublicEvidence })
    const output = runStage8([
      '--json',
      '--require-suite-evidence',
      '--evidence-manifest',
      manifest,
    ], { expectFailure: true })

    expect(output).toContain('"suite_evidence_ok": false')
    expect(output).toContain('assertions.gold_or_shop_economy must be true')
  })

  it('accepts documented blockers only when blocker mode is explicit', () => {
    const manifest = writeFullStage8Manifest({
      mutate(payload) {
        payload.suites.multiplayer.evidence = payload.suites.multiplayer.evidence
          .filter(item => item.id !== 'combat-sync-or-blocker')
        payload.suites.multiplayer.blockers = [
          {
            covers: ['combat-sync-or-blocker'],
            reason: 'Public two-browser combat sync needs a second disposable account on the deployed server.',
            next_action: 'Create the second smoke account, rerun room join, then replace this blocker with pass evidence.',
          },
        ]
      },
    })

    const blocked = runStage8([
      '--json',
      '--require-suite-evidence',
      '--evidence-manifest',
      manifest,
    ], { expectFailure: true })
    expect(blocked).toContain('rerun with --allow-blockers')

    const allowed = runStage8([
      '--json',
      '--require-suite-evidence',
      '--evidence-manifest',
      manifest,
      '--allow-blockers',
    ])
    expect(allowed).toContain('"suite_evidence_ok": true')
    expect(allowed).toContain('"accepted": true')
  })

  it('verifies Stage 7.5 artifacts referenced from a suite manifest', () => {
    const invalidStage75 = writeStage75SmokeArtifact({
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
    const manifest = writeFullStage8Manifest({ stage75Artifact: invalidStage75 })
    const output = runStage8([
      '--json',
      '--require-suite-evidence',
      '--evidence-manifest',
      manifest,
    ], { expectFailure: true })

    expect(output).toContain('"suite_evidence_ok": false')
    expect(output).toContain('assertions.mutating_round_trip must be true')
  })

  it('requires the exact public health URL when production evidence asks for it', () => {
    const localHealth = writePostdeployHealthArtifact({
      healthChecks: [
        {
          url: 'http://127.0.0.1:8000/health',
          ok: true,
          statusOk: true,
          status: 200,
          body: {
            status: 'ok',
          },
        },
      ],
    })
    const manifest = writeFullStage8Manifest({ healthArtifact: localHealth })
    const output = runStage8([
      '--json',
      '--require-suite-evidence',
      '--evidence-manifest',
      manifest,
    ], { expectFailure: true })

    expect(output).toContain('postdeploy-healthcheck artifact must include health URL: https://www.ai5edm.top/api/health')
  })
})
