#!/usr/bin/env node
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

export const DEFAULT_HEALTH_URLS = [
  'http://127.0.0.1:8000/health',
];

export const DEFAULT_LOG_PATTERNS = [
  {
    label: 'Traceback',
    pattern: /\btraceback\b/i,
  },
  {
    label: 'ERROR',
    pattern: /\berror\b/i,
  },
  {
    label: '500',
    pattern: /\b500\b/,
  },
];

function requiredOptionValue(argv, index, optionName) {
  const value = argv[index + 1] || '';
  if (!value || value.startsWith('--')) {
    throw new Error(`${optionName} requires a value.`);
  }
  return value;
}

function requiredInlineOptionValue(value, optionName) {
  if (!value) {
    throw new Error(`${optionName} requires a value.`);
  }
  return value;
}

function parsePositiveTimeoutMs(value, optionName) {
  const timeoutMs = Number(value);
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    throw new Error(`${optionName} must be a positive number.`);
  }
  return timeoutMs;
}

export function parseArgs(argv = process.argv.slice(2)) {
  const args = {
    format: 'markdown',
    help: false,
    logFiles: [],
    output: '',
    timeoutMs: 10_000,
    urls: [],
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--help' || arg === '-h') {
      args.help = true;
      continue;
    }
    if (arg === '--json') {
      args.format = 'json';
      continue;
    }
    if (arg === '--format') {
      args.format = requiredOptionValue(argv, index, arg);
      index += 1;
      continue;
    }
    if (arg.startsWith('--format=')) {
      args.format = requiredInlineOptionValue(arg.slice('--format='.length), '--format');
      continue;
    }
    if (arg === '--output') {
      args.output = requiredOptionValue(argv, index, arg);
      index += 1;
      continue;
    }
    if (arg.startsWith('--output=')) {
      args.output = requiredInlineOptionValue(arg.slice('--output='.length), '--output');
      continue;
    }
    if (arg === '--timeout-ms') {
      args.timeoutMs = parsePositiveTimeoutMs(requiredOptionValue(argv, index, arg), arg);
      index += 1;
      continue;
    }
    if (arg.startsWith('--timeout-ms=')) {
      args.timeoutMs = parsePositiveTimeoutMs(
        requiredInlineOptionValue(arg.slice('--timeout-ms='.length), '--timeout-ms'),
        '--timeout-ms',
      );
      continue;
    }
    if (arg === '--url') {
      args.urls.push(requiredOptionValue(argv, index, arg));
      index += 1;
      continue;
    }
    if (arg.startsWith('--url=')) {
      args.urls.push(requiredInlineOptionValue(arg.slice('--url='.length), '--url'));
      continue;
    }
    if (arg === '--log-file') {
      args.logFiles.push(requiredOptionValue(argv, index, arg));
      index += 1;
      continue;
    }
    if (arg.startsWith('--log-file=')) {
      args.logFiles.push(requiredInlineOptionValue(arg.slice('--log-file='.length), '--log-file'));
      continue;
    }
    args.urls.push(arg);
  }

  args.urls = args.urls.filter(Boolean);
  args.logFiles = args.logFiles.filter(Boolean);
  return args;
}

export function usage() {
  return [
    'Usage:',
    '  node scripts/stage7_postdeploy_healthcheck.mjs [--url <health-url>...] [--log-file <file>...] [--format markdown|json] [--json] [--output <file>] [--timeout-ms <ms>]',
    '',
    'Checks the Stage 7 after-server-update gate:',
    '  - each health URL returns HTTP 2xx JSON with status="ok"',
    '  - optional log files do not contain Traceback, ERROR, or 500',
  ].join('\n');
}

function createTimeoutSignal(timeoutMs) {
  const controller = new AbortController();
  const timer = setTimeout(() => {
    controller.abort();
  }, timeoutMs);
  return {
    clear: () => clearTimeout(timer),
    signal: controller.signal,
  };
}

export async function checkHealthUrl(url, {
  fetchImpl = globalThis.fetch,
  timeoutMs = 10_000,
} = {}) {
  const result = {
    body: null,
    error: '',
    ok: false,
    status: 0,
    statusOk: false,
    url,
  };

  if (typeof fetchImpl !== 'function') {
    return {
      ...result,
      error: 'fetch is not available',
    };
  }

  const timeout = createTimeoutSignal(timeoutMs);
  try {
    const response = await fetchImpl(url, {
      headers: {
        accept: 'application/json',
      },
      signal: timeout.signal,
    });
    result.status = response.status;
    result.statusOk = response.ok;
    const body = await response.json();
    result.body = body;
    result.ok = response.ok && body && body.status === 'ok';
    if (!result.ok) {
      result.error = response.ok
        ? 'health JSON did not include status="ok"'
        : `HTTP ${response.status}`;
    }
  } catch (error) {
    result.error = error && error.name === 'AbortError'
      ? `timed out after ${timeoutMs}ms`
      : error?.message || String(error);
  } finally {
    timeout.clear();
  }

  return result;
}

export function scanLogText(text, patterns = DEFAULT_LOG_PATTERNS) {
  const lines = String(text || '').split(/\r?\n/);
  const matches = [];
  lines.forEach((line, index) => {
    patterns.forEach(({ label, pattern }) => {
      if (pattern.test(line)) {
        matches.push({
          label,
          line: index + 1,
          text: line,
        });
      }
    });
  });
  return matches;
}

export async function checkLogFile(filePath, {
  readFileImpl = readFile,
} = {}) {
  try {
    const text = await readFileImpl(filePath, 'utf8');
    const matches = scanLogText(text);
    return {
      error: '',
      file: filePath,
      matches,
      ok: matches.length === 0,
    };
  } catch (error) {
    return {
      error: error?.message || String(error),
      file: filePath,
      matches: [],
      ok: false,
    };
  }
}

export function buildPostdeployPayload({
  generatedAt = new Date().toISOString(),
  healthChecks = [],
  logChecks = [],
} = {}) {
  const healthReady = healthChecks.length > 0 && healthChecks.every(check => check.ok);
  const logsReady = logChecks.every(check => check.ok);

  return {
    generatedAt,
    healthChecks,
    healthReady,
    logChecks,
    logsReady,
    ready: healthReady && logsReady,
  };
}

function formatHealthBody(body) {
  if (body == null) return '-';
  try {
    return JSON.stringify(body);
  } catch {
    return String(body);
  }
}

function formatLogMatches(matches) {
  if (!matches.length) return '-';
  return matches
    .slice(0, 5)
    .map(match => `${match.label} at line ${match.line}`)
    .join('; ');
}

export function buildPostdeployMarkdown(payload) {
  return [
    '# Stage 7 Post-Deploy Healthcheck',
    '',
    `Generated: ${payload.generatedAt}`,
    `Ready after server update: ${payload.ready ? 'yes' : 'no'}`,
    '',
    '## Health URLs',
    '',
    '| URL | HTTP | status="ok" | Result | Body/Error |',
    '| --- | --- | --- | --- | --- |',
    ...payload.healthChecks.map(check => `| ${check.url} | ${check.status || '-'} | ${check.ok ? 'yes' : 'no'} | ${check.ok ? 'pass' : 'fail'} | ${check.error || formatHealthBody(check.body)} |`),
    '',
    '## Log Files',
    '',
    payload.logChecks.length
      ? '| File | Result | Matches/Error |\n| --- | --- | --- |\n'
        + payload.logChecks.map(check => `| ${check.file} | ${check.ok ? 'pass' : 'fail'} | ${check.error || formatLogMatches(check.matches)} |`).join('\n')
      : '_No log files checked._',
    '',
  ].join('\n');
}

export function buildPostdeployJson(payload) {
  return `${JSON.stringify(payload, null, 2)}\n`;
}

async function writeOutput(filePath, text) {
  const fullPath = path.resolve(filePath);
  await mkdir(path.dirname(fullPath), { recursive: true });
  await writeFile(fullPath, text, 'utf8');
  return fullPath;
}

export async function runCli(argv = process.argv.slice(2), {
  fetchImpl = globalThis.fetch,
  readFileImpl = readFile,
} = {}) {
  const args = parseArgs(argv);
  if (args.help) {
    console.log(usage());
    return 0;
  }
  if (args.format !== 'markdown' && args.format !== 'json') {
    throw new Error('--format must be markdown or json.');
  }

  const urls = args.urls.length ? args.urls : DEFAULT_HEALTH_URLS;
  const healthChecks = await Promise.all(urls.map(url => checkHealthUrl(url, {
    fetchImpl,
    timeoutMs: args.timeoutMs,
  })));
  const logChecks = await Promise.all(args.logFiles.map(filePath => checkLogFile(filePath, {
    readFileImpl,
  })));
  const payload = buildPostdeployPayload({
    healthChecks,
    logChecks,
  });
  const text = args.format === 'json'
    ? buildPostdeployJson(payload)
    : buildPostdeployMarkdown(payload);

  if (args.output) {
    const outputPath = await writeOutput(args.output, text);
    console.log(`Wrote ${outputPath}`);
  } else {
    console.log(text);
  }

  return payload.ready ? 0 : 1;
}

const isMain = process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href;

if (isMain) {
  runCli().then(
    code => {
      process.exitCode = code;
    },
    error => {
      console.error(error.stack || error.message || String(error));
      process.exitCode = 1;
    },
  );
}
