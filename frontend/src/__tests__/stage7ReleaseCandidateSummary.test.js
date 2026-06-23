import { describe, expect, it } from 'vitest'
import fs from 'node:fs'
import os from 'node:os'
import path from 'node:path'

import {
  buildReleaseCandidateJson,
  buildReleaseCandidatePayload,
  buildReleaseCandidateSummary,
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
  return REQUIRED_STAGE7_CI_JOBS.map(name => ({
    conclusion: 'success',
    html_url: `https://github.test/jobs/${name}`,
    name,
    status: 'completed',
  }))
}

function responseJson(data) {
  return {
    ok: true,
    text: async () => JSON.stringify(data),
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
      '--timeout-seconds',
      '1200',
      '--verify-evidence',
      '--evidence-no-file-check',
      '--require-evidence',
      '--evidence',
      'artifacts/manifest.json',
      'artifacts/load.json',
    ])).toMatchObject({
      branch: 'main',
      evidenceFiles: ['artifacts/manifest.json', 'artifacts/load.json'],
      evidenceNoFileCheck: true,
      evidenceRequired: true,
      evidenceVerified: true,
      format: 'json',
      headSha: 'abc123',
      output: 'artifacts/summary.md',
      pollSeconds: 5,
      repo: 'xy92435952/ai-dnd-5e',
      runId: '42',
      timeoutSeconds: 1200,
      wait: true,
    })
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
    expect(markdown).toContain('Evidence verification: fail: ready must be true')
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
