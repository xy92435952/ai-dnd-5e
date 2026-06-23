import { describe, expect, it } from 'vitest'

import {
  buildReleaseCandidateSummary,
  inferGitHubRepo,
  parseArgs,
  REQUIRED_STAGE7_CI_JOBS,
  summarizeRequiredCiJobs,
} from '../../../scripts/stage7_release_candidate_summary.mjs'

function successfulJobs() {
  return REQUIRED_STAGE7_CI_JOBS.map(name => ({
    conclusion: 'success',
    html_url: `https://github.test/jobs/${name}`,
    name,
    status: 'completed',
  }))
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
      '--head',
      'abc123',
      '--run-id=42',
      '--output',
      'artifacts/summary.md',
      '--evidence',
      'artifacts/manifest.json',
      'artifacts/load.json',
    ])).toMatchObject({
      branch: 'main',
      evidenceFiles: ['artifacts/manifest.json', 'artifacts/load.json'],
      headSha: 'abc123',
      output: 'artifacts/summary.md',
      repo: 'xy92435952/ai-dnd-5e',
      runId: '42',
    })
  })

  it('infers owner and repository from GitHub remotes', () => {
    expect(inferGitHubRepo('git@github.com:xy92435952/ai-dnd-5e.git')).toBe('xy92435952/ai-dnd-5e')
    expect(inferGitHubRepo('https://github.com/xy92435952/ai-dnd-5e.git')).toBe('xy92435952/ai-dnd-5e')
    expect(inferGitHubRepo('https://example.test/not-github.git')).toBe('')
  })
})
