import { describe, expect, it } from 'vitest'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

import {
  buildCiBlockers,
  buildDecisionBlockers,
  buildReleaseCandidateJson,
  buildReleaseCandidatePayload,
  buildReleaseCandidateSummary,
  downloadCiBlockerLogs,
  findRunForHead,
  inferGitHubRepo,
  matchesHeadSha,
  parseArgs,
  REQUIRED_STAGE7_CI_JOBS,
  summarizeRequiredCiJobs,
  verifyEvidenceFiles,
  waitForRequiredCiJobs,
} from '../../../scripts/stage7_release_candidate_summary.mjs'

function successfulJobs() {
  return REQUIRED_STAGE7_CI_JOBS.map((name, index) => ({
    conclusion: 'success',
    html_url: `https://github.test/jobs/${name}`,
    id: 1000 + index,
    name,
    status: 'completed',
    url: `https://api.github.test/repos/xy92435952/ai-dnd-5e/actions/jobs/${1000 + index}`,
  }))
}

function responseJson(data) {
  return {
    ok: true,
    text: async () => JSON.stringify(data),
  }
}

function responseText(text, { ok = true, status = 200 } = {}) {
  return {
    ok,
    status,
    text: async () => text,
  }
}

function createFetchSequence({ runs, jobs }) {
  const runQueue = [...runs]
  const jobQueue = [...jobs]
  return async url => {
    if (url.includes('/jobs')) {
      return responseJson({ jobs: jobQueue.shift() || [] })
    }
    return responseJson(runQueue.shift() || runs.at(-1))
  }
}

function createWorkflowFetchSequence({ workflowRuns, jobs }) {
  const workflowRunQueue = [...workflowRuns]
  const jobQueue = [...jobs]
  return async url => {
    if (url.includes('/jobs')) {
      return responseJson({ jobs: jobQueue.shift() || [] })
    }
    return responseJson({ workflow_runs: workflowRunQueue.shift() || workflowRuns.at(-1) })
  }
}

function writePostdeployEvidence(overrides = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'stage7-release-evidence-'))
  const filePath = path.join(dir, 'postdeploy.json')
  const data = {
    generatedAt: '2026-06-24T00:00:00.000Z',
    healthChecks: [
      {
        body: {
          status: 'ok',
        },
        error: '',
        ok: true,
        status: 200,
        statusOk: true,
        url: 'http://127.0.0.1:8000/health',
      },
    ],
    healthReady: true,
    logChecks: [],
    logsReady: true,
    ready: true,
    ...overrides,
  }
  fs.writeFileSync(filePath, `${JSON.stringify(data, null, 2)}\n`, 'utf8')
  return filePath
}

function writePublicBrowserSmokeEvidence(overrides = {}) {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'stage7-release-public-browser-'))
  const adventurePath = path.join(dir, 'adventure.png')
  const combatPath = path.join(dir, 'combat.png')
  fs.writeFileSync(adventurePath, 'png', 'utf8')
  fs.writeFileSync(combatPath, 'png', 'utf8')
  const filePath = path.join(dir, 'public-browser-smoke.json')
  const data = {
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
      adventure: adventurePath,
      combat: combatPath,
    },
    ...overrides,
  }
  fs.writeFileSync(filePath, `${JSON.stringify(data, null, 2)}\n`, 'utf8')
  return filePath
}

describe('Stage 7 release candidate summary', () => {
  it('requires the deployment-blocking CI jobs to be completed successfully', () => {
    const summary = summarizeRequiredCiJobs(successfulJobs())

    expect(summary.ok).toBe(true)
    expect(summary.missing).toEqual([])
    expect(summary.rows.map(row => row.name)).toEqual([
      'backend',
      'frontend',
      'frontend-prod-build',
    ])
    expect(summary.rows.every(row => row.ok)).toBe(true)
  })

  it('marks missing or failed required jobs as not ready', () => {
    const summary = summarizeRequiredCiJobs([
      {
        conclusion: 'success',
        html_url: 'https://github.test/jobs/backend',
        name: 'backend',
        status: 'completed',
      },
      {
        conclusion: 'failure',
        html_url: 'https://github.test/jobs/frontend',
        name: 'frontend',
        status: 'completed',
      },
    ])

    expect(summary.ok).toBe(false)
    expect(summary.missing).toEqual(['frontend-prod-build'])
    expect(summary.rows.find(row => row.name === 'frontend')).toMatchObject({
      ok: false,
      reason: 'completed/failure',
    })
  })

  it('surfaces actionable CI blockers for failed handoff checks', () => {
    const requiredJobSummary = summarizeRequiredCiJobs([
      {
        conclusion: 'failure',
        html_url: 'https://github.test/jobs/backend',
        id: 201,
        name: 'backend',
        status: 'completed',
        url: 'https://api.github.test/repos/xy92435952/ai-dnd-5e/actions/jobs/201',
      },
      {
        conclusion: null,
        html_url: 'https://github.test/jobs/frontend',
        id: 202,
        name: 'frontend',
        status: 'in_progress',
        url: 'https://api.github.test/repos/xy92435952/ai-dnd-5e/actions/jobs/202',
      },
    ])
    const run = {
      conclusion: 'failure',
      html_url: 'https://github.test/actions/runs/99',
      id: 99,
      name: 'CI',
      status: 'completed',
    }
    const payload = buildReleaseCandidatePayload({
      branch: 'main',
      gitStatus: '',
      headSha: '85405ad',
      repo: 'xy92435952/ai-dnd-5e',
      requiredJobSummary,
      run,
    })
    const markdown = buildReleaseCandidateSummary({
      branch: 'main',
      gitStatus: '',
      headSha: '85405ad',
      repo: 'xy92435952/ai-dnd-5e',
      requiredJobSummary,
      run,
    })

    expect(buildCiBlockers({ requiredJobSummary, run })).toEqual(payload.ci.blockers)
    expect(buildDecisionBlockers({
      ciBlockers: payload.ci.blockers,
      gitStatus: '',
    })).toEqual(payload.decisionBlockers)
    expect(payload.ready).toBe(false)
    expect(payload.ci.blockers).toEqual([
      {
        conclusion: 'failure',
        id: 99,
        kind: 'workflow',
        logsUrl: '',
        name: 'CI #99',
        reason: 'completed/failure',
        status: 'completed',
        url: 'https://github.test/actions/runs/99',
      },
      {
        conclusion: 'failure',
        id: 201,
        kind: 'job',
        logsUrl: 'https://api.github.test/repos/xy92435952/ai-dnd-5e/actions/jobs/201/logs',
        name: 'backend',
        reason: 'completed/failure',
        status: 'completed',
        url: 'https://github.test/jobs/backend',
      },
      {
        conclusion: 'pending',
        id: 202,
        kind: 'job',
        logsUrl: 'https://api.github.test/repos/xy92435952/ai-dnd-5e/actions/jobs/202/logs',
        name: 'frontend',
        reason: 'in_progress/pending',
        status: 'in_progress',
        url: 'https://github.test/jobs/frontend',
      },
      {
        conclusion: 'missing',
        id: null,
        kind: 'job',
        logsUrl: '',
        name: 'frontend-prod-build',
        reason: 'missing',
        status: 'missing',
        url: '',
      },
    ])
    expect(markdown).toContain('## CI Blockers')
    expect(markdown).toContain('- [CI #99](https://github.test/actions/runs/99): completed/failure')
    expect(markdown).toContain('- [backend](https://github.test/jobs/backend): completed/failure (logs: [download](https://api.github.test/repos/xy92435952/ai-dnd-5e/actions/jobs/201/logs))')
    expect(markdown).toContain('- [frontend](https://github.test/jobs/frontend): in_progress/pending (logs: [download](https://api.github.test/repos/xy92435952/ai-dnd-5e/actions/jobs/202/logs))')
    expect(markdown).toContain('- frontend-prod-build: missing')
    expect(markdown).toContain('## Decision Blockers')
    expect(markdown).toContain('CI [backend](https://github.test/jobs/backend): completed/failure; logs: [download](https://api.github.test/repos/xy92435952/ai-dnd-5e/actions/jobs/201/logs)')
  })

  it('renders a handoff summary with CI links, evidence, and the final decision', () => {
    const requiredJobSummary = summarizeRequiredCiJobs(successfulJobs())
    const markdown = buildReleaseCandidateSummary({
      branch: 'main',
      evidenceFiles: [
        'artifacts/browser-feather-fall-adventure-manifest-20260623.json',
      ],
      generatedAt: '2026-06-23T12:00:00.000Z',
      gitStatus: '',
      headSha: '510d28ec42331da5d693375f606070406a375f07',
      repo: 'xy92435952/ai-dnd-5e',
      requiredJobSummary,
      run: {
        conclusion: 'success',
        html_url: 'https://github.test/actions/runs/1',
        id: 1,
        name: 'CI',
        status: 'completed',
      },
    })

    expect(markdown).toContain('# Stage 7 Release Candidate Summary')
    expect(markdown).toContain('Repository: xy92435952/ai-dnd-5e')
    expect(markdown).toContain('| [backend](https://github.test/jobs/backend) | completed | success | pass |')
    expect(markdown).toContain('## CI Blockers')
    expect(markdown).toContain('- None.')
    expect(markdown).toContain('## Decision Blockers')
    expect(markdown).toContain('- None.')
    expect(markdown).toContain('artifacts/browser-feather-fall-adventure-manifest-20260623.json')
    expect(markdown).toContain('Evidence verification: not checked')
    expect(markdown).toContain('Ready for deployment handoff: yes')
  })

  it('keeps dirty working trees out of deployment handoff readiness', () => {
    const markdown = buildReleaseCandidateSummary({
      branch: 'main',
      gitStatus: ' M frontend/src/App.jsx',
      headSha: 'abc123',
      repo: 'xy92435952/ai-dnd-5e',
      requiredJobSummary: summarizeRequiredCiJobs(successfulJobs()),
      run: {
        conclusion: 'success',
        id: 2,
        name: 'CI',
        status: 'completed',
      },
    })

    expect(markdown).toContain('Working tree: dirty')
    expect(markdown).toContain('## Decision Blockers')
    expect(markdown).toContain('- Working tree: dirty (M frontend/src/App.jsx)')
    expect(markdown).toContain('Ready for deployment handoff: no')
  })

  it('parses CLI options used by the Stage 7 handoff command', () => {
    expect(parseArgs([
      '--repo',
      'xy92435952/ai-dnd-5e',
      '--branch=main',
      '--format',
      'json',
      '--head',
      'abc123',
      '--wait',
      '--poll-seconds=5',
      '--run-id=42',
      '--output',
      'artifacts/summary.md',
      '--download-blocker-logs',
      'artifacts/ci-logs',
      '--timeout-seconds',
      '1200',
      '--verify-evidence',
      '--evidence-no-file-check',
      '--require-evidence',
      '--require-evidence-type',
      'public-browser-smoke',
      '--require-evidence-type=postdeploy-healthcheck',
      '--require-postdeploy-health-url',
      'https://example.com/api/health',
      '--evidence',
      'artifacts/manifest.json',
      'artifacts/load.json',
    ])).toMatchObject({
      branch: 'main',
      evidenceFiles: ['artifacts/manifest.json', 'artifacts/load.json'],
      evidenceNoFileCheck: true,
      evidenceRequired: true,
      evidenceVerified: true,
      requiredEvidenceTypes: ['public-browser-smoke', 'postdeploy-healthcheck'],
      requiredPostdeployHealthUrls: ['https://example.com/api/health'],
      format: 'json',
      headSha: 'abc123',
      blockerLogDir: 'artifacts/ci-logs',
      output: 'artifacts/summary.md',
      pollSeconds: 5,
      repo: 'xy92435952/ai-dnd-5e',
      runId: '42',
      timeoutSeconds: 1200,
      wait: true,
    })
  })

  it('fails fast when release handoff options are missing required values', () => {
    expect(() => parseArgs(['--download-blocker-logs', '--json'])).toThrow(
      '--download-blocker-logs requires a value.',
    )
    expect(() => parseArgs(['--download-blocker-logs='])).toThrow('--download-blocker-logs requires a value.')
    expect(() => parseArgs(['--format='])).toThrow('--format requires a value.')
    expect(() => parseArgs(['--repo'])).toThrow('--repo requires a value.')
    expect(() => parseArgs(['--repo='])).toThrow('--repo requires a value.')
    expect(() => parseArgs(['--branch', '--json'])).toThrow('--branch requires a value.')
    expect(() => parseArgs(['--branch='])).toThrow('--branch requires a value.')
    expect(() => parseArgs(['--head', '--wait'])).toThrow('--head requires a value.')
    expect(() => parseArgs(['--head='])).toThrow('--head requires a value.')
    expect(() => parseArgs(['--run-id', '--wait'])).toThrow('--run-id requires a value.')
    expect(() => parseArgs(['--run-id='])).toThrow('--run-id requires a value.')
    expect(() => parseArgs(['--output', '--json'])).toThrow('--output requires a value.')
    expect(() => parseArgs(['--output='])).toThrow('--output requires a value.')
    expect(() => parseArgs(['--evidence', '--verify-evidence'])).toThrow('--evidence requires a value.')
    expect(() => parseArgs(['--evidence='])).toThrow('--evidence requires a value.')
    expect(() => parseArgs(['--require-evidence-type', '--json'])).toThrow('--require-evidence-type requires a value.')
    expect(() => parseArgs(['--require-evidence-type='])).toThrow('--require-evidence-type requires a value.')
    expect(() => parseArgs(['--require-evidence-type', 'browser-smoke'])).toThrow(
      '--require-evidence-type must be one of: feather-fall, multiplayer-load, postdeploy-healthcheck, local-http-smoke, public-browser-smoke.',
    )
    expect(() => parseArgs(['--require-postdeploy-health-url', '--json'])).toThrow(
      '--require-postdeploy-health-url requires a value.',
    )
    expect(() => parseArgs(['--require-postdeploy-health-url='])).toThrow(
      '--require-postdeploy-health-url requires a value.',
    )
    expect(() => parseArgs(['--verify-evidnce'])).toThrow('Unknown option: --verify-evidnce')
  })

  it('fails fast when release handoff wait values are invalid', () => {
    expect(() => parseArgs(['--poll-seconds', '--wait'])).toThrow('--poll-seconds requires a value.')
    expect(() => parseArgs(['--poll-seconds='])).toThrow('--poll-seconds requires a value.')
    expect(() => parseArgs(['--poll-seconds', '0'])).toThrow('--poll-seconds must be a positive number.')
    expect(() => parseArgs(['--poll-seconds=not-a-number'])).toThrow('--poll-seconds must be a positive number.')
    expect(() => parseArgs(['--timeout-seconds', '--wait'])).toThrow('--timeout-seconds requires a value.')
    expect(() => parseArgs(['--timeout-seconds='])).toThrow('--timeout-seconds requires a value.')
    expect(() => parseArgs(['--timeout-seconds', '-1'])).toThrow('--timeout-seconds must be a positive number.')
    expect(() => parseArgs(['--timeout-seconds=not-a-number'])).toThrow('--timeout-seconds must be a positive number.')
  })

  it('supports the JSON output shortcut option', () => {
    expect(parseArgs(['--json', '--repo', 'xy92435952/ai-dnd-5e'])).toMatchObject({
      format: 'json',
      repo: 'xy92435952/ai-dnd-5e',
    })
  })

  it('infers owner and repository from GitHub remotes', () => {
    expect(inferGitHubRepo('git@github.com:xy92435952/ai-dnd-5e.git')).toBe('xy92435952/ai-dnd-5e')
    expect(inferGitHubRepo('https://github.com/xy92435952/ai-dnd-5e.git')).toBe('xy92435952/ai-dnd-5e')
    expect(inferGitHubRepo('https://example.test/not-github.git')).toBe('')
  })

  it('matches full and short GitHub head SHAs safely', () => {
    const fullSha = 'e82779916ef4b7db62dc106dfc7987b1be2c14dd'
    const otherSha = 'b5ebadbb4af505a7ef6728d500edab0e47b21150'

    expect(matchesHeadSha(fullSha, fullSha)).toBe(true)
    expect(matchesHeadSha(fullSha, 'e827799')).toBe(true)
    expect(matchesHeadSha(fullSha, 'e82779')).toBe(false)
    expect(matchesHeadSha(fullSha, otherSha)).toBe(false)
    expect(findRunForHead([
      { head_sha: otherSha, id: 1 },
      { head_sha: fullSha, id: 2 },
    ], 'e827799')).toMatchObject({ id: 2 })
  })

  it('waits for required GitHub Actions jobs to reach final success', async () => {
    const sleepCalls = []
    const result = await waitForRequiredCiJobs({
      branch: 'main',
      fetchImpl: createFetchSequence({
        runs: [
          {
            conclusion: null,
            id: 100,
            name: 'CI',
            status: 'in_progress',
          },
          {
            conclusion: 'success',
            id: 100,
            name: 'CI',
            status: 'completed',
          },
        ],
        jobs: [
          [
            {
              conclusion: null,
              name: 'backend',
              status: 'in_progress',
            },
            {
              conclusion: 'success',
              name: 'frontend',
              status: 'completed',
            },
            {
              conclusion: 'success',
              name: 'frontend-prod-build',
              status: 'completed',
            },
          ],
          successfulJobs(),
        ],
      }),
      headSha: 'abc123',
      pollSeconds: 1,
      repo: 'xy92435952/ai-dnd-5e',
      runId: '100',
      sleepImpl: async ms => {
        sleepCalls.push(ms)
      },
      timeoutSeconds: 60,
    })

    expect(sleepCalls).toEqual([1000])
    expect(result.run.status).toBe('completed')
    expect(result.requiredJobSummary.ok).toBe(true)
  })

  it('retries transient GitHub API failures while waiting for CI', async () => {
    const sleepCalls = []
    const fetchCalls = []
    const result = await waitForRequiredCiJobs({
      branch: 'main',
      fetchImpl: async url => {
        fetchCalls.push(url)
        if (fetchCalls.length === 1) {
          throw new TypeError('fetch failed')
        }
        if (url.includes('/jobs')) {
          return responseJson({ jobs: successfulJobs() })
        }
        return responseJson({
          conclusion: 'success',
          id: 110,
          name: 'CI',
          status: 'completed',
        })
      },
      headSha: 'abc123',
      pollSeconds: 1,
      repo: 'xy92435952/ai-dnd-5e',
      runId: '110',
      sleepImpl: async ms => {
        sleepCalls.push(ms)
      },
      timeoutSeconds: 60,
    })

    expect(sleepCalls).toEqual([1000])
    expect(fetchCalls).toHaveLength(3)
    expect(result.run.id).toBe(110)
    expect(result.requiredJobSummary.ok).toBe(true)
  })

  it('does not retry non-transient GitHub API failures', async () => {
    const sleepCalls = []

    await expect(waitForRequiredCiJobs({
      branch: 'main',
      fetchImpl: async () => responseText('not found', { ok: false, status: 404 }),
      headSha: 'abc123',
      pollSeconds: 1,
      repo: 'xy92435952/ai-dnd-5e',
      runId: '404',
      sleepImpl: async ms => {
        sleepCalls.push(ms)
      },
      timeoutSeconds: 60,
    })).rejects.toThrow('GitHub API request failed (404): not found')

    expect(sleepCalls).toEqual([])
  })

  it('builds a machine-readable release candidate payload', () => {
    const payload = buildReleaseCandidatePayload({
      branch: 'main',
      evidenceFiles: ['artifacts/load.json'],
      evidenceSummary: {
        ok: true,
        output: 'Verified 1 Stage 7 evidence file(s).',
      },
      generatedAt: '2026-06-23T12:00:00.000Z',
      gitStatus: '',
      headSha: '8e51fc0',
      repo: 'xy92435952/ai-dnd-5e',
      requiredJobSummary: summarizeRequiredCiJobs(successfulJobs()),
      run: {
        conclusion: 'success',
        head_sha: '8e51fc011111111111111111111111111111111',
        html_url: 'https://github.test/actions/runs/102',
        id: 102,
        name: 'CI',
        status: 'completed',
      },
    })

    expect(payload).toMatchObject({
      branch: 'main',
      ci: {
        checked: true,
        ready: true,
        run: {
          conclusion: 'success',
          headSha: '8e51fc011111111111111111111111111111111',
          id: 102,
          status: 'completed',
        },
      },
      evidenceFiles: ['artifacts/load.json'],
      evidenceVerification: {
        checked: true,
        ok: true,
      },
      headSha: '8e51fc0',
      ready: true,
      repo: 'xy92435952/ai-dnd-5e',
      workingTree: {
        clean: true,
      },
    })
    expect(payload.ci.requiredJobs.map(job => job.name)).toEqual([
      'backend',
      'frontend',
      'frontend-prod-build',
    ])
    expect(payload.ci.requiredJobs[0]).toMatchObject({
      id: 1000,
      logsUrl: 'https://api.github.test/repos/xy92435952/ai-dnd-5e/actions/jobs/1000/logs',
    })
  })

  it('downloads blocker job logs into a handoff directory', async () => {
    const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'stage7-ci-logs-'))
    const requiredJobSummary = summarizeRequiredCiJobs([
      {
        conclusion: 'failure',
        html_url: 'https://github.test/jobs/backend',
        id: 301,
        name: 'backend',
        status: 'completed',
        url: 'https://api.github.test/repos/xy92435952/ai-dnd-5e/actions/jobs/301',
      },
      {
        conclusion: 'failure',
        html_url: 'https://github.test/jobs/frontend',
        id: 302,
        name: 'frontend',
        status: 'completed',
        url: 'https://api.github.test/repos/xy92435952/ai-dnd-5e/actions/jobs/302/',
      },
    ])
    const blockers = buildCiBlockers({
      requiredJobSummary,
      run: {
        conclusion: 'failure',
        id: 7,
        name: 'CI',
        status: 'completed',
      },
    })
    const fetchCalls = []
    const results = await downloadCiBlockerLogs(blockers, {
      fetchImpl: async url => {
        fetchCalls.push(url)
        return responseText(`log from ${url}`)
      },
      outputDir: dir,
    })
    const markdown = buildReleaseCandidateSummary({
      branch: 'main',
      downloadedLogs: results,
      gitStatus: '',
      headSha: 'ca41259',
      repo: 'xy92435952/ai-dnd-5e',
      requiredJobSummary,
      run: {
        conclusion: 'failure',
        id: 7,
        name: 'CI',
        status: 'completed',
      },
    })

    expect(fetchCalls).toEqual([
      'https://api.github.test/repos/xy92435952/ai-dnd-5e/actions/jobs/301/logs',
      'https://api.github.test/repos/xy92435952/ai-dnd-5e/actions/jobs/302/logs',
    ])
    expect(results).toHaveLength(2)
    expect(path.basename(results[0].path)).toBe('backend-301.log')
    expect(path.basename(results[1].path)).toBe('frontend-302.log')
    expect(fs.readFileSync(results[0].path, 'utf8')).toContain('/jobs/301/logs')
    expect(markdown).toContain('## CI Log Downloads')
    expect(markdown).toContain(`- backend: saved to ${results[0].path}`)
    expect(markdown).toContain(`- frontend: saved to ${results[1].path}`)
  })

  it('blocks deployment readiness when requested evidence verification fails', () => {
    const common = {
      branch: 'main',
      evidenceFiles: ['artifacts/bad.json'],
      evidenceSummary: {
        error: 'ready must be true',
        ok: false,
      },
      gitStatus: '',
      headSha: 'f91ec63',
      repo: 'xy92435952/ai-dnd-5e',
      requiredJobSummary: summarizeRequiredCiJobs(successfulJobs()),
      run: {
        conclusion: 'success',
        id: 2,
        name: 'CI',
        status: 'completed',
      },
    }
    const payload = buildReleaseCandidatePayload(common)
    const markdown = buildReleaseCandidateSummary(common)

    expect(payload.ready).toBe(false)
    expect(payload.evidenceVerification).toMatchObject({
      checked: true,
      error: 'ready must be true',
      ok: false,
    })
    expect(payload.decisionBlockers).toContainEqual({
      category: 'evidence',
      detail: 'ready must be true',
      name: 'evidence verification',
      reason: 'failed',
    })
    expect(markdown).toContain('Evidence verification: fail: ready must be true')
    expect(markdown).toContain('- Evidence verification: ready must be true')
    expect(markdown).toContain('Ready for deployment handoff: no')
  })

  it('verifies listed Stage 7 evidence files through the shared verifier', () => {
    const goodEvidence = writePostdeployEvidence()
    const badEvidence = writePostdeployEvidence({
      healthChecks: [],
      healthReady: false,
      ready: false,
    })

    expect(verifyEvidenceFiles([goodEvidence])).toMatchObject({
      ok: true,
    })
    expect(verifyEvidenceFiles([badEvidence])).toMatchObject({
      ok: false,
    })
  })

  it('requires specific Stage 7 evidence types for final handoff readiness', () => {
    const postdeployEvidence = writePostdeployEvidence()
    const publicBrowserEvidence = writePublicBrowserSmokeEvidence()

    expect(verifyEvidenceFiles([], {
      requiredEvidenceTypes: ['public-browser-smoke'],
    })).toMatchObject({
      error: 'Missing required Stage 7 evidence type(s): public-browser-smoke',
      foundTypes: [],
      ok: false,
      requiredTypes: ['public-browser-smoke'],
    })

    expect(verifyEvidenceFiles([postdeployEvidence], {
      requiredEvidenceTypes: ['public-browser-smoke'],
    })).toMatchObject({
      error: 'Missing required Stage 7 evidence type(s): public-browser-smoke',
      foundTypes: ['postdeploy-healthcheck'],
      ok: false,
      requiredTypes: ['public-browser-smoke'],
    })

    expect(verifyEvidenceFiles([postdeployEvidence, publicBrowserEvidence], {
      requiredEvidenceTypes: ['public-browser-smoke', 'postdeploy-healthcheck'],
    })).toMatchObject({
      foundTypes: ['postdeploy-healthcheck', 'public-browser-smoke'],
      ok: true,
      requiredTypes: ['public-browser-smoke', 'postdeploy-healthcheck'],
    })
  })

  it('requires exact post-deploy health URLs for public deployment handoff readiness', () => {
    const localPostdeploy = writePostdeployEvidence()
    const publicPostdeploy = writePostdeployEvidence({
      healthChecks: [
        {
          body: {
            status: 'ok',
          },
          error: '',
          ok: true,
          status: 200,
          statusOk: true,
          url: 'https://example.com/api/health',
        },
      ],
    })

    expect(parseArgs([
      '--require-postdeploy-health-url',
      'https://example.com/api/health',
    ])).toMatchObject({
      evidenceRequired: true,
      evidenceVerified: true,
      requiredEvidenceTypes: ['postdeploy-healthcheck'],
      requiredPostdeployHealthUrls: ['https://example.com/api/health'],
    })

    expect(verifyEvidenceFiles([localPostdeploy], {
      requiredPostdeployHealthUrls: ['https://example.com/api/health'],
    })).toMatchObject({
      error: 'Missing required Stage 7 post-deploy health URL(s): https://example.com/api/health',
      foundPostdeployHealthUrls: ['http://127.0.0.1:8000/health'],
      foundTypes: ['postdeploy-healthcheck'],
      ok: false,
      requiredPostdeployHealthUrls: ['https://example.com/api/health'],
      requiredTypes: ['postdeploy-healthcheck'],
    })

    expect(verifyEvidenceFiles([publicPostdeploy], {
      requiredPostdeployHealthUrls: ['https://example.com/api/health'],
    })).toMatchObject({
      foundPostdeployHealthUrls: ['https://example.com/api/health'],
      foundTypes: ['postdeploy-healthcheck'],
      ok: true,
      requiredPostdeployHealthUrls: ['https://example.com/api/health'],
      requiredTypes: ['postdeploy-healthcheck'],
    })
  })

  it('blocks release readiness when a required evidence type is absent', () => {
    const evidenceSummary = verifyEvidenceFiles([writePostdeployEvidence()], {
      requiredEvidenceTypes: ['public-browser-smoke'],
    })
    const common = {
      branch: 'main',
      evidenceFiles: ['artifacts/postdeploy.json'],
      evidenceSummary,
      gitStatus: '',
      headSha: 'd5b9fc7',
      repo: 'xy92435952/ai-dnd-5e',
      requiredJobSummary: summarizeRequiredCiJobs(successfulJobs()),
      run: {
        conclusion: 'success',
        id: 2,
        name: 'CI',
        status: 'completed',
      },
    }
    const payload = buildReleaseCandidatePayload(common)
    const markdown = buildReleaseCandidateSummary(common)

    expect(payload.ready).toBe(false)
    expect(payload.evidenceVerification).toMatchObject({
      checked: true,
      error: 'Missing required Stage 7 evidence type(s): public-browser-smoke',
      foundTypes: ['postdeploy-healthcheck'],
      ok: false,
      requiredTypes: ['public-browser-smoke'],
    })
    expect(markdown).toContain('Evidence verification: fail: Missing required Stage 7 evidence type(s): public-browser-smoke')
    expect(markdown).toContain('Ready for deployment handoff: no')
  })

  it('blocks release readiness when a required post-deploy health URL is absent', () => {
    const evidenceSummary = verifyEvidenceFiles([writePostdeployEvidence()], {
      requiredPostdeployHealthUrls: ['https://example.com/api/health'],
    })
    const common = {
      branch: 'main',
      evidenceFiles: ['artifacts/postdeploy-local.json'],
      evidenceSummary,
      gitStatus: '',
      headSha: 'd5b9fc7',
      repo: 'xy92435952/ai-dnd-5e',
      requiredJobSummary: summarizeRequiredCiJobs(successfulJobs()),
      run: {
        conclusion: 'success',
        id: 2,
        name: 'CI',
        status: 'completed',
      },
    }
    const payload = buildReleaseCandidatePayload(common)
    const markdown = buildReleaseCandidateSummary(common)

    expect(payload.ready).toBe(false)
    expect(payload.evidenceVerification).toMatchObject({
      checked: true,
      error: 'Missing required Stage 7 post-deploy health URL(s): https://example.com/api/health',
      foundPostdeployHealthUrls: ['http://127.0.0.1:8000/health'],
      ok: false,
      requiredPostdeployHealthUrls: ['https://example.com/api/health'],
      requiredTypes: ['postdeploy-healthcheck'],
    })
    expect(markdown).toContain('Evidence verification: fail: Missing required Stage 7 post-deploy health URL(s): https://example.com/api/health')
    expect(markdown).toContain('Ready for deployment handoff: no')
  })

  it('can require at least one evidence file for release handoff readiness', () => {
    const evidenceSummary = verifyEvidenceFiles([], { requireEvidence: true })
    const payload = buildReleaseCandidatePayload({
      branch: 'main',
      evidenceFiles: [],
      evidenceSummary,
      gitStatus: '',
      headSha: 'd5b9fc7',
      repo: 'xy92435952/ai-dnd-5e',
      requiredJobSummary: summarizeRequiredCiJobs(successfulJobs()),
      run: {
        conclusion: 'success',
        id: 2,
        name: 'CI',
        status: 'completed',
      },
    })
    const markdown = buildReleaseCandidateSummary({
      branch: 'main',
      evidenceFiles: [],
      evidenceSummary,
      gitStatus: '',
      headSha: 'd5b9fc7',
      repo: 'xy92435952/ai-dnd-5e',
      requiredJobSummary: summarizeRequiredCiJobs(successfulJobs()),
      run: {
        conclusion: 'success',
        id: 2,
        name: 'CI',
        status: 'completed',
      },
    })

    expect(evidenceSummary).toMatchObject({
      error: 'At least one Stage 7 evidence file is required.',
      ok: false,
    })
    expect(payload.ready).toBe(false)
    expect(markdown).toContain('Evidence verification: fail: At least one Stage 7 evidence file is required.')
  })

  it('keeps the release candidate non-ready until the workflow run is complete', () => {
    const payload = buildReleaseCandidatePayload({
      branch: 'main',
      gitStatus: '',
      headSha: 'cff20f0',
      repo: 'xy92435952/ai-dnd-5e',
      requiredJobSummary: summarizeRequiredCiJobs(successfulJobs()),
      run: {
        conclusion: '',
        head_sha: 'cff20f064d6a2ed8620dc697674c23e022e36070',
        id: 104,
        name: 'CI',
        status: 'in_progress',
      },
    })

    expect(payload.ci.requiredJobsReady).toBe(true)
    expect(payload.ci.runReady).toBe(false)
    expect(payload.ci.ready).toBe(false)
    expect(payload.ready).toBe(false)
  })

  it('renders JSON output that automation can parse', () => {
    const json = buildReleaseCandidateJson({
      branch: 'main',
      generatedAt: '2026-06-23T12:00:00.000Z',
      gitStatus: ' M scripts/stage7_release_candidate_summary.mjs',
      headSha: '8e51fc0',
      repo: 'xy92435952/ai-dnd-5e',
      requiredJobSummary: summarizeRequiredCiJobs(successfulJobs()),
      run: {
        conclusion: 'success',
        id: 103,
        name: 'CI',
        status: 'completed',
      },
    })
    const payload = JSON.parse(json)

    expect(json.endsWith('\n')).toBe(true)
    expect(payload.ready).toBe(false)
    expect(payload.workingTree.clean).toBe(false)
    expect(payload.ci.requiredJobs.every(job => job.ok)).toBe(true)
  })

  it('waits for workflow completion after the required jobs succeed', async () => {
    const sleepCalls = []
    const result = await waitForRequiredCiJobs({
      branch: 'main',
      fetchImpl: createFetchSequence({
        runs: [
          {
            conclusion: '',
            id: 105,
            name: 'CI',
            status: 'in_progress',
          },
          {
            conclusion: 'success',
            id: 105,
            name: 'CI',
            status: 'completed',
          },
        ],
        jobs: [
          successfulJobs(),
          successfulJobs(),
        ],
      }),
      headSha: 'cff20f0',
      pollSeconds: 1,
      repo: 'xy92435952/ai-dnd-5e',
      runId: '105',
      sleepImpl: async ms => {
        sleepCalls.push(ms)
      },
      timeoutSeconds: 60,
    })

    expect(sleepCalls).toEqual([1000])
    expect(result.run.status).toBe('completed')
    expect(result.requiredJobSummary.ok).toBe(true)
  })

  it('waits for GitHub to create a run for the pushed commit', async () => {
    const sleepCalls = []
    const result = await waitForRequiredCiJobs({
      branch: 'main',
      fetchImpl: createWorkflowFetchSequence({
        workflowRuns: [
          [],
          [
            {
              conclusion: 'success',
              head_sha: 'e82779916ef4b7db62dc106dfc7987b1be2c14dd',
              id: 102,
              name: 'CI',
              status: 'completed',
            },
          ],
        ],
        jobs: [
          successfulJobs(),
        ],
      }),
      headSha: 'e827799',
      pollSeconds: 1,
      repo: 'xy92435952/ai-dnd-5e',
      sleepImpl: async ms => {
        sleepCalls.push(ms)
      },
      timeoutSeconds: 60,
    })

    expect(sleepCalls).toEqual([1000])
    expect(result.run.id).toBe(102)
    expect(result.requiredJobSummary.ok).toBe(true)
  })

  it('stops waiting when a required GitHub Actions job fails', async () => {
    const sleepCalls = []
    const result = await waitForRequiredCiJobs({
      branch: 'main',
      fetchImpl: createFetchSequence({
        runs: [
          {
            conclusion: null,
            id: 101,
            name: 'CI',
            status: 'in_progress',
          },
        ],
        jobs: [
          [
            {
              conclusion: 'failure',
              html_url: 'https://github.test/jobs/backend',
              name: 'backend',
              status: 'completed',
            },
            {
              conclusion: null,
              name: 'frontend',
              status: 'in_progress',
            },
            {
              conclusion: 'success',
              name: 'frontend-prod-build',
              status: 'completed',
            },
          ],
        ],
      }),
      headSha: 'abc123',
      pollSeconds: 1,
      repo: 'xy92435952/ai-dnd-5e',
      runId: '101',
      sleepImpl: async ms => {
        sleepCalls.push(ms)
      },
      timeoutSeconds: 60,
    })

    expect(sleepCalls).toEqual([])
    expect(result.requiredJobSummary.ok).toBe(false)
    expect(result.requiredJobSummary.rows.find(row => row.name === 'backend')).toMatchObject({
      conclusion: 'failure',
      ok: false,
      reason: 'completed/failure',
    })
  })
})
