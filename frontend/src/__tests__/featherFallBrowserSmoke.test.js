import { describe, expect, it } from 'vitest'
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', '..')

function readSmokeScript() {
  return fs.readFileSync(path.join(repoRoot, 'scripts', 'feather_fall_adventure_browser_smoke.mjs'), 'utf8')
}

describe('Feather Fall browser smoke selector contract', () => {
  it('tracks the ExplorationReactionPrompt dialog semantics', () => {
    const source = readSmokeScript()

    expect(source).toContain('querySelectorAll(\'[role="dialog"].exploration-reaction-prompt\')')
    expect(source).toContain("textFromIds(candidate.getAttribute('aria-labelledby')).includes('Feather Fall')")
    expect(source).toContain("state.dialogName.includes('Feather Fall')")
    expect(source).toContain("state.dialogDescription.includes('Prevents 6 fall damage')")
    expect(source).not.toContain('[role="dialog"][aria-label="Exploration reaction prompt"]')
  })
})
