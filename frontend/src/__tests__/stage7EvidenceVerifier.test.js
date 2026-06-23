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

function writeManifest(data) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'stage7-evidence-verifier-'))
  const filePath = path.join(dir, 'manifest.json')
  fs.writeFileSync(filePath, `${JSON.stringify(data, null, 2)}\n`, 'utf8')
  return filePath
}

describe('Stage 7 evidence verifier CLI', () => {
  it('fails fast when type options are missing or invalid', () => {
    expect(() => runVerifier(['--type'])).toThrow(/--type requires a value/)
    expect(() => runVerifier(['--type', '--no-file-check'])).toThrow(/--type requires a value/)
    expect(() => runVerifier(['--type='])).toThrow(/--type requires a value/)
    expect(() => runVerifier(['--type', 'browser-smoke'])).toThrow(
      /--type must be one of: auto, feather-fall, multiplayer-load, postdeploy-healthcheck/,
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
})
