import { describe, expect, it } from 'vitest'
import { execFileSync } from 'node:child_process'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', '..')
const verifyScript = path.join(repoRoot, 'scripts', 'verify_stage7_evidence.mjs')
const smokeScript = path.join(repoRoot, 'scripts', 'feather_fall_adventure_browser_smoke.mjs')

function readSmokeScript() {
  return fs.readFileSync(smokeScript, 'utf8')
}

function runSmokeScript(args) {
  return execFileSync(process.execPath, [
    smokeScript,
    ...args,
  ], {
    cwd: repoRoot,
    env: {
      ...process.env,
      PYTHON_EXE: process.execPath,
    },
    stdio: 'pipe',
  })
}

function validManifest(overrides = {}) {
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
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'stage7-feather-fall-'))
  const filePath = path.join(dir, 'manifest.json')
  fs.writeFileSync(filePath, `${JSON.stringify(data, null, 2)}\n`, 'utf8')
  return filePath
}

describe('Feather Fall browser smoke selector contract', () => {
  it('tracks the ExplorationReactionPrompt dialog semantics', () => {
    const source = readSmokeScript()

    expect(source).toContain('querySelectorAll(\'[role="dialog"].exploration-reaction-prompt\')')
    expect(source).toContain("textFromIds(candidate.getAttribute('aria-labelledby')).includes('Feather Fall')")
    expect(source).toContain('dialogName: promptState.dialogName')
    expect(source).toContain('dialogDescription: promptState.dialogDescription')
    expect(source).toContain("state.dialogName.includes('Feather Fall')")
    expect(source).toContain("state.dialogDescription.includes('Prevents 6 fall damage')")
    expect(source).not.toContain('[role="dialog"][aria-label="Exploration reaction prompt"]')
  })

  it('fails fast when smoke option values are missing', () => {
    expect(() => runSmokeScript(['--decision'])).toThrow(/--decision requires a value/)
    expect(() => runSmokeScript(['--decision', '--artifact-tag', 'unit'])).toThrow(/--decision requires a value/)
    expect(() => runSmokeScript(['--decision='])).toThrow(/--decision requires a value/)
    expect(() => runSmokeScript(['--artifact-tag'])).toThrow(/--artifact-tag requires a value/)
    expect(() => runSmokeScript(['--artifact-tag='])).toThrow(/--artifact-tag requires a value/)
  })

  it('requires dialog name and description in release evidence manifests', () => {
    const goodManifest = writeManifest(validManifest())

    expect(() => execFileSync(process.execPath, [
      verifyScript,
      '--no-file-check',
      goodManifest,
    ], { cwd: repoRoot, stdio: 'pipe' })).not.toThrow()

    const staleManifest = writeManifest(validManifest({
      prompt: {
        dialogText: 'REACTION Feather Fall Mara Quickstep can protect Smoke Sentinel.',
      },
    }))

    expect(() => execFileSync(process.execPath, [
      verifyScript,
      '--no-file-check',
      staleManifest,
    ], { cwd: repoRoot, stdio: 'pipe' })).toThrow(/prompt\.dialogName must include Feather Fall/)
  })
})
