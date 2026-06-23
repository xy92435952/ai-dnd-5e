import { describe, expect, it } from 'vitest'

import {
  buildPostdeployJson,
  buildPostdeployMarkdown,
  buildPostdeployPayload,
  checkHealthUrl,
  checkLogFile,
  DEFAULT_HEALTH_URLS,
  parseArgs,
  scanLogText,
} from '../../../scripts/stage7_postdeploy_healthcheck.mjs'

function response({ body, ok = true, status = 200 }) {
  return {
    json: async () => body,
    ok,
    status,
  }
}

describe('Stage 7 post-deploy healthcheck', () => {
  it('defaults to the local backend health endpoint', () => {
    expect(DEFAULT_HEALTH_URLS).toEqual(['http://127.0.0.1:8000/health'])
  })

  it('parses health URLs, log files, JSON output, and timeout options', () => {
    expect(parseArgs([
      '--json',
      '--timeout-ms',
      '1500',
      '--url',
      'https://example.test/api/health',
      '--log-file',
      'artifacts/server.log',
      '--output',
      'artifacts/postdeploy.json',
    ])).toMatchObject({
      format: 'json',
      logFiles: ['artifacts/server.log'],
      output: 'artifacts/postdeploy.json',
      timeoutMs: 1500,
      urls: ['https://example.test/api/health'],
    })
  })

  it('accepts HTTP 2xx health JSON with status ok', async () => {
    const result = await checkHealthUrl('https://example.test/api/health', {
      fetchImpl: async () => response({
        body: {
          status: 'ok',
          version: '0.1.0',
        },
      }),
    })

    expect(result).toMatchObject({
      ok: true,
      status: 200,
      statusOk: true,
      url: 'https://example.test/api/health',
    })
  })

  it('fails health URLs when HTTP succeeds but the payload is not healthy', async () => {
    const result = await checkHealthUrl('https://example.test/api/health', {
      fetchImpl: async () => response({
        body: {
          status: 'broken',
        },
      }),
    })

    expect(result).toMatchObject({
      error: 'health JSON did not include status="ok"',
      ok: false,
      status: 200,
    })
  })

  it('detects deployment log stop-condition markers', async () => {
    const matches = scanLogText([
      'INFO boot complete',
      'Traceback (most recent call last):',
      'ERROR failed request',
      'GET /game/action 500',
    ].join('\n'))

    expect(matches.map(match => match.label)).toEqual(['Traceback', 'ERROR', '500'])

    const clean = await checkLogFile('/var/log/app.log', {
      readFileImpl: async () => 'INFO boot complete\nINFO health ok',
    })
    const dirty = await checkLogFile('/var/log/app.log', {
      readFileImpl: async () => 'ERROR request failed',
    })

    expect(clean).toMatchObject({
      ok: true,
    })
    expect(dirty).toMatchObject({
      ok: false,
      matches: [
        {
          label: 'ERROR',
          line: 1,
        },
      ],
    })
  })

  it('builds ready and blocked payloads from health and log checks', () => {
    const ready = buildPostdeployPayload({
      generatedAt: '2026-06-24T00:00:00.000Z',
      healthChecks: [
        {
          ok: true,
        },
      ],
      logChecks: [
        {
          ok: true,
        },
      ],
    })
    const blocked = buildPostdeployPayload({
      healthChecks: [
        {
          ok: true,
        },
      ],
      logChecks: [
        {
          ok: false,
        },
      ],
    })

    expect(ready).toMatchObject({
      healthReady: true,
      logsReady: true,
      ready: true,
    })
    expect(blocked).toMatchObject({
      healthReady: true,
      logsReady: false,
      ready: false,
    })
  })

  it('renders Markdown and JSON handoff output', () => {
    const payload = buildPostdeployPayload({
      generatedAt: '2026-06-24T00:00:00.000Z',
      healthChecks: [
        {
          body: {
            status: 'ok',
          },
          error: '',
          ok: true,
          status: 200,
          url: 'http://127.0.0.1:8000/health',
        },
      ],
      logChecks: [
        {
          error: '',
          file: 'artifacts/server.log',
          matches: [],
          ok: true,
        },
      ],
    })
    const markdown = buildPostdeployMarkdown(payload)
    const json = buildPostdeployJson(payload)

    expect(markdown).toContain('# Stage 7 Post-Deploy Healthcheck')
    expect(markdown).toContain('Ready after server update: yes')
    expect(markdown).toContain('| http://127.0.0.1:8000/health | 200 | yes | pass |')
    expect(JSON.parse(json)).toMatchObject({
      healthReady: true,
      logsReady: true,
      ready: true,
    })
  })
})
