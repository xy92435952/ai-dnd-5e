import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import {
  buildPublicBrowserPayload,
  collectBlockingBrowserEvents,
  normalizeOrigin,
  parseArgs,
  validateRequiredArgs,
} from '../../../scripts/stage7_public_browser_smoke.mjs'

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', '..')

function passingChecks(overrides = {}) {
  return {
    login_path: '/',
    login_token_present: true,
    adventure_loaded: true,
    session_api_ok: true,
    session_id_matches: true,
    session_combat_active: true,
    current_scene_present: true,
    combat_loaded: true,
    combat_api_ok: true,
    combat_round: 1,
    combat_turn_order_count: 4,
    combat_entities_count: 4,
    skill_bar_count: 10,
    skill_bar_dom_count: 10,
    ...overrides,
  }
}

describe('Stage 7 public browser smoke helper', () => {
  it('parses public deployment smoke options and environment fallbacks', () => {
    const args = parseArgs([
      '--frontend-origin',
      'https://example.com/',
      '--username=stage7-user',
      '--password',
      'secret',
      '--session-id',
      'session-1',
      '--artifact-tag',
      'deploy-20260624',
      '--timeout-ms=30000',
    ], {})

    expect(args.frontendOrigin).toBe('https://example.com')
    expect(args.username).toBe('stage7-user')
    expect(args.password).toBe('secret')
    expect(args.sessionId).toBe('session-1')
    expect(args.artifactTag).toBe('deploy-20260624')
    expect(args.timeoutMs).toBe(30000)

    const envArgs = parseArgs([], {
      STAGE7_PUBLIC_FRONTEND_ORIGIN: 'https://prod.example',
      STAGE7_PUBLIC_USERNAME: 'env-user',
      STAGE7_PUBLIC_PASSWORD: 'env-secret',
      STAGE7_PUBLIC_SESSION_ID: 'env-session',
      STAGE7_PUBLIC_BROWSER_SMOKE_ARTIFACT_TAG: 'env-tag',
    })
    expect(envArgs.frontendOrigin).toBe('https://prod.example')
    expect(envArgs.username).toBe('env-user')
    expect(envArgs.password).toBe('env-secret')
    expect(envArgs.sessionId).toBe('env-session')
    expect(envArgs.artifactTag).toBe('env-tag')
  })

  it('fails fast for invalid or missing required options', () => {
    expect(() => parseArgs(['--frontend-origin'], {})).toThrow(/--frontend-origin requires a value/)
    expect(() => parseArgs(['--frontend-origin='], {})).toThrow(/--frontend-origin requires a value/)
    expect(() => parseArgs(['--timeout-ms=0'], {})).toThrow(/--timeout-ms must be a positive number/)
    expect(() => parseArgs(['--typo'], {})).toThrow(/Unknown option: --typo/)
    expect(() => normalizeOrigin('ftp://example.com')).toThrow(/http\(s\) origin/)

    expect(() => validateRequiredArgs(parseArgs([], {}))).toThrow(
      /Missing required public browser smoke option/,
    )
  })

  it('marks the payload ready only when public login, Adventure, Combat, skill-bar, and browser checks pass', () => {
    const payload = buildPublicBrowserPayload({
      browserErrors: [],
      checks: passingChecks(),
      frontendOrigin: 'https://example.com',
      sessionId: 'session-1',
      username: 'stage7-user',
    })

    expect(payload.ok).toBe(true)
    expect(payload.mode).toBe('stage7-public-browser-smoke')
    expect(payload.assertions).toMatchObject({
      login_ok: true,
      adventure_loaded: true,
      combat_loaded: true,
      combat_session_active: true,
      skill_bar_loaded: true,
      no_browser_errors: true,
    })

    const blocked = buildPublicBrowserPayload({
      browserErrors: [{ method: 'Runtime.exceptionThrown', message: 'boom' }],
      checks: passingChecks({ skill_bar_dom_count: 0 }),
      frontendOrigin: 'https://example.com',
      sessionId: 'session-1',
      username: 'stage7-user',
    })

    expect(blocked.ok).toBe(false)
    expect(blocked.assertions.skill_bar_loaded).toBe(false)
    expect(blocked.assertions.no_browser_errors).toBe(false)
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

  it('is wired into the Stage 7 check entrypoint and frontend gate', () => {
    const checkScript = fs.readFileSync(path.join(repoRoot, 'scripts', 'check.sh'), 'utf8')
    const packageJson = fs.readFileSync(path.join(repoRoot, 'frontend', 'package.json'), 'utf8')

    expect(checkScript).toContain('RUN_STAGE7_PUBLIC_BROWSER_SMOKE')
    expect(checkScript).toContain('node scripts/stage7_public_browser_smoke.mjs')
    expect(checkScript).toContain('STAGE7_PUBLIC_FRONTEND_ORIGIN')
    expect(checkScript).toContain('STAGE7_PUBLIC_SESSION_ID')
    expect(checkScript).toContain('add_stage7_evidence_file "$STAGE7_PUBLIC_BROWSER_SMOKE_OUTPUT"')
    expect(packageJson).toContain('src/__tests__/stage7PublicBrowserSmoke.test.js')
  })
})
