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

describe('Stage 7 evidence verifier CLI', () => {
  it('fails fast when type options are missing or invalid', () => {
    expect(() => runVerifier([])).toThrow(/At least one Stage 7 evidence file is required/)
    expect(() => runVerifier(['--typo'])).toThrow(/Unknown option: --typo/)
    expect(() => runVerifier(['--type'])).toThrow(/--type requires a value/)
    expect(() => runVerifier(['--type', '--no-file-check'])).toThrow(/--type requires a value/)
    expect(() => runVerifier(['--type='])).toThrow(/--type requires a value/)
    expect(() => runVerifier(['--type', 'browser-smoke'])).toThrow(
      /--type must be one of: auto, feather-fall, multiplayer-load, postdeploy-healthcheck, local-http-smoke, public-browser-smoke/,
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
})
