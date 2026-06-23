import { readFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

import { describe, expect, it } from 'vitest'

import {
  buildPreflightJson,
  buildPreflightMarkdown,
  buildPreflightPayload,
  DEFAULT_DEPLOY_IGNORE_PATHS,
  parseArgs,
  parseCheckIgnoreOutput,
} from '../../../scripts/stage7_deploy_preflight.mjs'

function ignored(path, pattern = '.env') {
  return {
    ignored: true,
    matchedPath: path,
    path,
    pattern,
    source: '.gitignore:5',
  }
}

describe('Stage 7 deploy preflight', () => {
  it('tracks the local-only paths from the deployment checklist', () => {
    expect(DEFAULT_DEPLOY_IGNORE_PATHS).toEqual([
      'backend/.env',
      'frontend/dist',
      'backend/.venv',
    ])
  })

  it('parses git check-ignore output into a stable result shape', () => {
    expect(parseCheckIgnoreOutput('.gitignore:5:.env\tbackend/.env')).toEqual({
      matchedPath: 'backend/.env',
      pattern: '.env',
      source: '.gitignore:5',
    })
  })

  it('marks clean working trees with ignored local-only paths as ready', () => {
    const payload = buildPreflightPayload({
      generatedAt: '2026-06-24T00:00:00.000Z',
      gitStatus: '',
      ignoreResults: DEFAULT_DEPLOY_IGNORE_PATHS.map(path => ignored(path)),
    })

    expect(payload.ready).toBe(true)
    expect(payload.ignoredPathsReady).toBe(true)
    expect(payload.workingTree).toMatchObject({
      clean: true,
      ready: true,
    })
  })

  it('blocks preflight when the working tree is dirty or a required path is not ignored', () => {
    const payload = buildPreflightPayload({
      gitStatus: ' M frontend/src/App.jsx',
      ignoreResults: [
        ignored('backend/.env'),
        ignored('frontend/dist', 'dist'),
        {
          ignored: false,
          matchedPath: '',
          path: 'backend/.venv',
          pattern: '',
          source: '',
        },
      ],
    })

    expect(payload.ready).toBe(false)
    expect(payload.ignoredPathsReady).toBe(false)
    expect(payload.workingTree.ready).toBe(false)
  })

  it('supports an explicit dirty-worktree override for draft local checks', () => {
    const payload = buildPreflightPayload({
      allowDirty: true,
      gitStatus: ' M docs/stage7-deployment-smoke-checklist.md',
      ignoreResults: DEFAULT_DEPLOY_IGNORE_PATHS.map(path => ignored(path)),
    })

    expect(payload.ready).toBe(true)
    expect(payload.workingTree).toMatchObject({
      allowDirty: true,
      clean: false,
      ready: true,
    })
  })

  it('renders markdown and JSON summaries for handoff logs', () => {
    const payload = buildPreflightPayload({
      generatedAt: '2026-06-24T00:00:00.000Z',
      gitStatus: '',
      ignoreResults: DEFAULT_DEPLOY_IGNORE_PATHS.map(path => ignored(path)),
    })
    const markdown = buildPreflightMarkdown(payload)
    const json = buildPreflightJson(payload)

    expect(markdown).toContain('# Stage 7 Deploy Preflight')
    expect(markdown).toContain('| backend/.env | yes | .gitignore:5 .env |')
    expect(markdown).toContain('Ready for server update: yes')
    expect(JSON.parse(json)).toMatchObject({
      ready: true,
      workingTree: {
        clean: true,
      },
    })
  })

  it('parses CLI options for JSON output and custom paths', () => {
    expect(parseArgs([
      '--json',
      '--allow-dirty',
      '--output',
      'artifacts/preflight.json',
      '--path',
      'backend/.env',
      'frontend/dist',
    ])).toMatchObject({
      allowDirty: true,
      format: 'json',
      output: 'artifacts/preflight.json',
      paths: ['backend/.env', 'frontend/dist'],
    })
  })

  it('exposes the deploy preflight as an opt-in check.sh gate', () => {
    const repoRoot = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', '..')
    const checkScript = readFileSync(path.join(repoRoot, 'scripts', 'check.sh'), 'utf8')

    expect(checkScript).toContain('RUN_STAGE7_DEPLOY_PREFLIGHT')
    expect(checkScript).toContain('STAGE7_DEPLOY_PREFLIGHT_ALLOW_DIRTY')
    expect(checkScript).toContain('STAGE7_DEPLOY_PREFLIGHT_FORMAT')
    expect(checkScript).toContain('STAGE7_DEPLOY_PREFLIGHT_OUTPUT')
    expect(checkScript).toContain('node scripts/stage7_deploy_preflight.mjs')
  })
})
