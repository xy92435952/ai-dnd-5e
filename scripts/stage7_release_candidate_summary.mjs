#!/usr/bin/env node
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

export const REQUIRED_STAGE7_CI_JOBS = ['backend', 'frontend', 'frontend-prod-build'];
export const VALID_STAGE7_EVIDENCE_TYPES = [
  'feather-fall',
  'multiplayer-load',
  'postdeploy-healthcheck',
  'local-http-smoke',
  'public-browser-smoke',
];

const SCRIPT_DIR = path.dirname(fileURLToPath(import.meta.url));
const ROOT_DIR = path.resolve(SCRIPT_DIR, '..');

function runGit(args, fallback = '') {
  try {
    return execFileSync('git', args, {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    }).trim();
  } catch {
    return fallback;
  }
}

function sanitizeRepoName(value) {
  if (!value) return '';
  return value.replace(/\.git$/, '').trim();
}

export function inferGitHubRepo(remoteUrl) {
  const remote = sanitizeRepoName(remoteUrl);
  const match = remote.match(/github\.com[:/]([^/\s]+)\/([^/\s]+)$/i);
  if (!match) return '';
  return `${match[1]}/${match[2]}`;
}

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

function parsePositiveSeconds(value, optionName) {
  const seconds = Number(value);
  if (!Number.isFinite(seconds) || seconds <= 0) {
    throw new Error(`${optionName} must be a positive number.`);
  }
  return seconds;
}

function normalizeRequiredEvidenceTypes(types = []) {
  return [...new Set(types.filter(Boolean))];
}

function validateRequiredEvidenceType(type) {
  if (!VALID_STAGE7_EVIDENCE_TYPES.includes(type)) {
    throw new Error(`--require-evidence-type must be one of: ${VALID_STAGE7_EVIDENCE_TYPES.join(', ')}.`);
  }
  return type;
}

export function parseArgs(argv = process.argv.slice(2)) {
  const args = {
    blockerLogDir: '',
    branch: '',
    evidenceFiles: [],
    evidenceNoFileCheck: false,
    evidenceRequired: false,
    evidenceVerified: false,
    format: 'markdown',
    headSha: '',
    help: false,
    noCi: false,
    output: '',
    pollSeconds: 20,
    repo: '',
    requiredEvidenceTypes: [],
    runId: '',
    timeoutSeconds: 1800,
    wait: false,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--help' || arg === '-h') {
      args.help = true;
      continue;
    }
    if (arg === '--no-ci') {
      args.noCi = true;
      continue;
    }
    if (arg === '--verify-evidence') {
      args.evidenceVerified = true;
      continue;
    }
    if (arg === '--evidence-no-file-check') {
      args.evidenceNoFileCheck = true;
      continue;
    }
    if (arg === '--require-evidence') {
      args.evidenceRequired = true;
      continue;
    }
    if (arg === '--require-evidence-type') {
      args.requiredEvidenceTypes.push(validateRequiredEvidenceType(requiredOptionValue(argv, index, arg)));
      index += 1;
      continue;
    }
    if (arg.startsWith('--require-evidence-type=')) {
      args.requiredEvidenceTypes.push(validateRequiredEvidenceType(
        requiredInlineOptionValue(arg.slice('--require-evidence-type='.length), '--require-evidence-type'),
      ));
      continue;
    }
    if (arg === '--download-blocker-logs') {
      args.blockerLogDir = requiredOptionValue(argv, index, arg);
      index += 1;
      continue;
    }
    if (arg.startsWith('--download-blocker-logs=')) {
      args.blockerLogDir = requiredInlineOptionValue(arg.slice('--download-blocker-logs='.length), '--download-blocker-logs');
      continue;
    }
    if (arg === '--wait') {
      args.wait = true;
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
    if (arg === '--repo') {
      args.repo = requiredOptionValue(argv, index, arg);
      index += 1;
      continue;
    }
    if (arg.startsWith('--repo=')) {
      args.repo = requiredInlineOptionValue(arg.slice('--repo='.length), '--repo');
      continue;
    }
    if (arg === '--branch') {
      args.branch = requiredOptionValue(argv, index, arg);
      index += 1;
      continue;
    }
    if (arg.startsWith('--branch=')) {
      args.branch = requiredInlineOptionValue(arg.slice('--branch='.length), '--branch');
      continue;
    }
    if (arg === '--head') {
      args.headSha = requiredOptionValue(argv, index, arg);
      index += 1;
      continue;
    }
    if (arg.startsWith('--head=')) {
      args.headSha = requiredInlineOptionValue(arg.slice('--head='.length), '--head');
      continue;
    }
    if (arg === '--run-id') {
      args.runId = requiredOptionValue(argv, index, arg);
      index += 1;
      continue;
    }
    if (arg.startsWith('--run-id=')) {
      args.runId = requiredInlineOptionValue(arg.slice('--run-id='.length), '--run-id');
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
    if (arg === '--poll-seconds') {
      args.pollSeconds = parsePositiveSeconds(requiredOptionValue(argv, index, arg), arg);
      index += 1;
      continue;
    }
    if (arg.startsWith('--poll-seconds=')) {
      args.pollSeconds = parsePositiveSeconds(
        requiredInlineOptionValue(arg.slice('--poll-seconds='.length), '--poll-seconds'),
        '--poll-seconds',
      );
      continue;
    }
    if (arg === '--timeout-seconds') {
      args.timeoutSeconds = parsePositiveSeconds(requiredOptionValue(argv, index, arg), arg);
      index += 1;
      continue;
    }
    if (arg.startsWith('--timeout-seconds=')) {
      args.timeoutSeconds = parsePositiveSeconds(
        requiredInlineOptionValue(arg.slice('--timeout-seconds='.length), '--timeout-seconds'),
        '--timeout-seconds',
      );
      continue;
    }
    if (arg === '--evidence') {
      args.evidenceFiles.push(requiredOptionValue(argv, index, arg));
      index += 1;
      continue;
    }
    if (arg.startsWith('--evidence=')) {
      args.evidenceFiles.push(requiredInlineOptionValue(arg.slice('--evidence='.length), '--evidence'));
      continue;
    }
    if (arg.startsWith('--')) {
      throw new Error(`Unknown option: ${arg}`);
    }
    args.evidenceFiles.push(arg);
  }

  args.evidenceFiles = args.evidenceFiles.filter(Boolean);
  args.requiredEvidenceTypes = normalizeRequiredEvidenceTypes(args.requiredEvidenceTypes);
  if (args.requiredEvidenceTypes.length) {
    args.evidenceRequired = true;
    args.evidenceVerified = true;
  }
  return args;
}

export function usage() {
  return [
    'Usage:',
    '  node scripts/stage7_release_candidate_summary.mjs [--format markdown|json] [--json] [--wait] [--poll-seconds 20] [--timeout-seconds 1800] [--repo owner/name] [--branch main] [--head <sha>] [--run-id <id>] [--output <file>] [--evidence <file>...] [--verify-evidence] [--require-evidence] [--require-evidence-type <type>] [--evidence-no-file-check] [--download-blocker-logs <dir>]',
    '',
    'Checks the latest GitHub Actions run for the selected commit and requires:',
    `  ${REQUIRED_STAGE7_CI_JOBS.join(', ')}`,
    '',
    'Use --no-ci only to draft a local summary without contacting GitHub.',
    'Use --verify-evidence to require the listed Stage 7 JSON evidence files to pass scripts/verify_stage7_evidence.mjs.',
    'Use --require-evidence when the release handoff must include at least one listed evidence file.',
    `Use --require-evidence-type to require specific verified evidence types: ${VALID_STAGE7_EVIDENCE_TYPES.join(', ')}.`,
    'Use --download-blocker-logs to save logs for failed or pending required CI job blockers.',
  ].join('\n');
}

export function getLocalReleaseContext() {
  const remote = runGit(['remote', 'get-url', 'origin']);
  return {
    branch: runGit(['rev-parse', '--abbrev-ref', 'HEAD'], 'main'),
    headSha: runGit(['rev-parse', 'HEAD']),
    repo: process.env.GITHUB_REPOSITORY || inferGitHubRepo(remote),
    status: runGit(['status', '--short', '--untracked-files=all']),
  };
}

function githubHeaders(token = process.env.GITHUB_TOKEN || '') {
  const headers = {
    Accept: 'application/vnd.github+json',
    'User-Agent': 'codex-stage7-release-candidate-summary',
  };
  if (token) headers.Authorization = `Bearer ${token}`;
  return headers;
}

class GitHubApiRequestError extends Error {
  constructor(message, { status = 0, transient = false } = {}) {
    super(message);
    this.name = 'GitHubApiRequestError';
    this.status = status;
    this.transient = transient;
  }
}

function isRetryableStatus(status) {
  return status === 429 || status >= 500;
}

function transientErrorCode(error) {
  return error?.code || error?.cause?.code || '';
}

function isTransientGitHubApiError(error) {
  if (error instanceof GitHubApiRequestError) {
    return error.transient;
  }
  const message = error?.message || String(error || '');
  const code = transientErrorCode(error);
  return (
    error?.name === 'AbortError'
    || error?.name === 'TimeoutError'
    || error?.name === 'TypeError'
    || /fetch failed|network|socket|timeout|ECONNRESET|ETIMEDOUT|ENOTFOUND|EAI_AGAIN/i.test(message)
    || /ECONNRESET|ETIMEDOUT|ENOTFOUND|EAI_AGAIN/i.test(code)
  );
}

function errorMessage(error) {
  return error?.message || String(error || 'unknown error');
}

async function githubJson(url, { fetchImpl = globalThis.fetch, token } = {}) {
  if (typeof fetchImpl !== 'function') {
    throw new Error('No fetch implementation available for GitHub API requests.');
  }
  const response = await fetchImpl(url, { headers: githubHeaders(token) });
  const text = await response.text();
  if (!response.ok) {
    throw new GitHubApiRequestError(`GitHub API request failed (${response.status}): ${text}`, {
      status: response.status,
      transient: isRetryableStatus(response.status),
    });
  }
  return JSON.parse(text);
}

async function githubText(url, { fetchImpl = globalThis.fetch, token } = {}) {
  if (typeof fetchImpl !== 'function') {
    throw new Error('No fetch implementation available for GitHub API requests.');
  }
  const response = await fetchImpl(url, { headers: githubHeaders(token) });
  const text = await response.text();
  if (!response.ok) {
    throw new GitHubApiRequestError(`GitHub API request failed (${response.status}): ${text}`, {
      status: response.status,
      transient: isRetryableStatus(response.status),
    });
  }
  return text;
}

export class RunNotFoundError extends Error {
  constructor({ branch, headSha }) {
    super(`No GitHub Actions run found for ${headSha} on ${branch}.`);
    this.name = 'RunNotFoundError';
  }
}

export function matchesHeadSha(candidateSha, requestedSha) {
  if (!candidateSha || !requestedSha) return false;
  if (candidateSha === requestedSha) return true;
  return requestedSha.length >= 7 && candidateSha.startsWith(requestedSha);
}

export function findRunForHead(runs, headSha) {
  return runs.find(candidate => matchesHeadSha(candidate.head_sha, headSha));
}

export async function fetchRunForHead({
  repo,
  branch,
  headSha,
  runId,
  fetchImpl = globalThis.fetch,
  token,
}) {
  if (runId) {
    return githubJson(`https://api.github.com/repos/${repo}/actions/runs/${runId}`, { fetchImpl, token });
  }

  const query = new URLSearchParams({ branch, per_page: '20' });
  const data = await githubJson(`https://api.github.com/repos/${repo}/actions/runs?${query}`, { fetchImpl, token });
  const runs = Array.isArray(data.workflow_runs) ? data.workflow_runs : [];
  const run = findRunForHead(runs, headSha);
  if (!run) {
    throw new RunNotFoundError({ branch, headSha });
  }
  return run;
}

export async function fetchRunJobs({ repo, runId, fetchImpl = globalThis.fetch, token }) {
  const data = await githubJson(`https://api.github.com/repos/${repo}/actions/runs/${runId}/jobs?per_page=100`, {
    fetchImpl,
    token,
  });
  return Array.isArray(data.jobs) ? data.jobs : [];
}

function normalizeCiConclusion(conclusion, status) {
  if (conclusion) return conclusion;
  if (!status || status === 'missing') return 'missing';
  return status !== 'completed' ? 'pending' : 'missing';
}

function jobLogsUrl(job) {
  if (!job?.url) return '';
  return `${job.url.replace(/\/$/, '')}/logs`;
}

export function summarizeRequiredCiJobs(jobs, requiredJobs = REQUIRED_STAGE7_CI_JOBS) {
  const rows = requiredJobs.map(name => {
    const job = jobs.find(candidate => candidate.name === name);
    const status = job?.status || 'missing';
    const conclusion = normalizeCiConclusion(job?.conclusion, status);
    const ok = status === 'completed' && conclusion === 'success';
    const reason = job
      ? (ok ? 'success' : `${status}/${conclusion}`)
      : 'missing';

    return {
      conclusion,
      id: job?.id || null,
      logsUrl: jobLogsUrl(job),
      name,
      ok,
      reason,
      status,
      url: job?.html_url || '',
    };
  });

  return {
    missing: rows.filter(row => row.status === 'missing').map(row => row.name),
    ok: rows.every(row => row.ok),
    rows,
  };
}

function validateWaitOptions({ pollSeconds, timeoutSeconds }) {
  if (!Number.isFinite(pollSeconds) || pollSeconds <= 0) {
    throw new Error('--poll-seconds must be a positive number.');
  }
  if (!Number.isFinite(timeoutSeconds) || timeoutSeconds <= 0) {
    throw new Error('--timeout-seconds must be a positive number.');
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function hasRequiredJobFailure(requiredJobSummary) {
  return requiredJobSummary.rows.some(row => row.status === 'completed' && row.conclusion !== 'success');
}

function isRunReady(run) {
  return run?.status === 'completed' && run?.conclusion === 'success';
}

export async function waitForRequiredCiJobs({
  repo,
  branch,
  headSha,
  runId,
  fetchImpl = globalThis.fetch,
  token,
  pollSeconds = 20,
  timeoutSeconds = 1800,
  sleepImpl = sleep,
}) {
  validateWaitOptions({ pollSeconds, timeoutSeconds });
  const startedAt = Date.now();

  for (;;) {
    try {
      const run = await fetchRunForHead({ repo, branch, headSha, runId, fetchImpl, token });
      const jobs = await fetchRunJobs({ repo, runId: run.id, fetchImpl, token });
      const requiredJobSummary = summarizeRequiredCiJobs(jobs);

      if (hasRequiredJobFailure(requiredJobSummary) || run.status === 'completed') {
        return { jobs, requiredJobSummary, run };
      }
    } catch (error) {
      const elapsedMs = Date.now() - startedAt;
      if (error instanceof RunNotFoundError) {
        if (elapsedMs >= timeoutSeconds * 1000) {
          throw new Error(`Timed out waiting for a GitHub Actions run for ${headSha} on ${branch} after ${timeoutSeconds}s.`);
        }

        await sleepImpl(pollSeconds * 1000);
        continue;
      }

      if (isTransientGitHubApiError(error)) {
        if (elapsedMs >= timeoutSeconds * 1000) {
          throw new Error(`Timed out waiting for GitHub Actions after ${timeoutSeconds}s. Last GitHub API error: ${errorMessage(error)}.`);
        }

        await sleepImpl(pollSeconds * 1000);
        continue;
      }

      throw error;
    }

    const elapsedMs = Date.now() - startedAt;
    if (elapsedMs >= timeoutSeconds * 1000) {
      throw new Error(`Timed out waiting for GitHub Actions run for ${headSha} after ${timeoutSeconds}s.`);
    }

    await sleepImpl(pollSeconds * 1000);
  }
}

function markdownLink(label, url) {
  return url ? `[${label}](${url})` : label;
}

function formatEvidenceFiles(evidenceFiles) {
  if (!evidenceFiles.length) return '- No optional evidence files listed.';
  return evidenceFiles.map(file => `- ${file}`).join('\n');
}

function formatEvidenceVerification(evidenceSummary) {
  if (!evidenceSummary) return 'not checked';
  if (evidenceSummary.ok) return 'pass';
  return `fail: ${evidenceSummary.error || 'unknown error'}`;
}

function resolveEvidencePath(filePath) {
  return path.isAbsolute(filePath) ? filePath : path.resolve(ROOT_DIR, filePath);
}

function readEvidenceJson(filePath) {
  const fullPath = resolveEvidencePath(filePath);
  const raw = readFileSync(fullPath, 'utf8').replace(/^\uFEFF/, '');
  return JSON.parse(raw);
}

export function inferEvidenceType(data) {
  if (data?.mode === 'feather-fall-adventure-browser-smoke') return 'feather-fall';
  if (data?.base_url && Array.isArray(data?.room_sizes) && Object.prototype.hasOwnProperty.call(data, 'cleanup_ok')) {
    return 'multiplayer-load';
  }
  if (Array.isArray(data?.healthChecks) && Array.isArray(data?.logChecks) && Object.prototype.hasOwnProperty.call(data, 'healthReady')) {
    return 'postdeploy-healthcheck';
  }
  if (data?.mode === 'stage7-local-http-smoke') return 'local-http-smoke';
  if (data?.mode === 'stage7-public-browser-smoke') return 'public-browser-smoke';
  return 'unknown';
}

function collectEvidenceTypes(evidenceFiles) {
  return normalizeRequiredEvidenceTypes(evidenceFiles.map(filePath => inferEvidenceType(readEvidenceJson(filePath))));
}

function missingEvidenceTypes(foundTypes, requiredTypes) {
  const found = new Set(foundTypes);
  return requiredTypes.filter(type => !found.has(type));
}

export function buildCiBlockers({ requiredJobSummary = null, run = null } = {}) {
  if (!requiredJobSummary) {
    return [
      {
        conclusion: 'not checked',
        id: null,
        kind: 'ci',
        logsUrl: '',
        name: 'CI check',
        reason: 'not checked',
        status: 'not checked',
        url: '',
      },
    ];
  }

  const blockers = [];

  if (!isRunReady(run)) {
    const status = run?.status || 'missing';
    const conclusion = normalizeCiConclusion(run?.conclusion, status);
    blockers.push({
      conclusion,
      id: run?.id || null,
      kind: 'workflow',
      logsUrl: '',
      name: run ? `${run.name || 'workflow'} #${run.id}` : 'workflow run',
      reason: run ? `${status}/${conclusion}` : 'missing',
      status,
      url: run?.html_url || '',
    });
  }

  requiredJobSummary.rows
    .filter(row => !row.ok)
    .forEach(row => {
      blockers.push({
        conclusion: row.conclusion,
        id: row.id,
        kind: 'job',
        logsUrl: row.logsUrl,
        name: row.name,
        reason: row.reason,
        status: row.status,
        url: row.url,
      });
    });

  return blockers;
}

function formatJobRows(summary) {
  if (!summary) return '_CI was not checked._';
  return [
    '| Job | Status | Conclusion | Result |',
    '| --- | --- | --- | --- |',
    ...summary.rows.map(row => {
      const label = markdownLink(row.name, row.url);
      return `| ${label} | ${row.status} | ${row.conclusion} | ${row.ok ? 'pass' : `fail: ${row.reason}`} |`;
    }),
  ].join('\n');
}

function formatCiBlockers(blockers) {
  if (!blockers?.length) return '- None.';
  return blockers.map(blocker => {
    const label = markdownLink(blocker.name, blocker.url);
    const logs = blocker.logsUrl ? ` (logs: ${markdownLink('download', blocker.logsUrl)})` : '';
    return `- ${label}: ${blocker.reason}${logs}`;
  }).join('\n');
}

function safeFileStem(value) {
  return String(value || 'ci-job')
    .replace(/[^a-z0-9._-]+/gi, '-')
    .replace(/^-+|-+$/g, '')
    .slice(0, 80) || 'ci-job';
}

export async function downloadCiBlockerLogs(blockers, {
  fetchImpl = globalThis.fetch,
  outputDir = '',
  token,
} = {}) {
  if (!outputDir) return [];
  const jobBlockers = (blockers || []).filter(blocker => blocker.kind === 'job' && blocker.logsUrl);
  if (!jobBlockers.length) return [];

  const fullDir = path.resolve(outputDir);
  await mkdir(fullDir, { recursive: true });

  const results = [];
  for (const blocker of jobBlockers) {
    const fileName = `${safeFileStem(blocker.name)}-${blocker.id || 'unknown'}.log`;
    const filePath = path.join(fullDir, fileName);
    try {
      const text = await githubText(blocker.logsUrl, { fetchImpl, token });
      await writeFile(filePath, text, 'utf8');
      results.push({
        error: '',
        id: blocker.id,
        name: blocker.name,
        ok: true,
        path: filePath,
        url: blocker.logsUrl,
      });
    } catch (error) {
      results.push({
        error: error.message || String(error),
        id: blocker.id,
        name: blocker.name,
        ok: false,
        path: filePath,
        url: blocker.logsUrl,
      });
    }
  }

  return results;
}

function formatDownloadedLogs(downloadedLogs) {
  if (!downloadedLogs?.length) return '- None.';
  return downloadedLogs.map(result => {
    if (result.ok) {
      return `- ${result.name}: saved to ${result.path}`;
    }
    return `- ${result.name}: failed to download (${result.error || 'unknown error'})`;
  }).join('\n');
}

export function buildDecisionBlockers({
  ciBlockers = [],
  evidenceSummary = null,
  gitStatus = '',
} = {}) {
  const blockers = [];
  const status = gitStatus.trim();
  if (status) {
    blockers.push({
      category: 'working-tree',
      detail: status,
      name: 'working tree',
      reason: 'dirty',
    });
  }

  ciBlockers.forEach(blocker => {
    blockers.push({
      category: 'ci',
      detail: blocker.reason,
      logsUrl: blocker.logsUrl || '',
      name: blocker.name,
      reason: blocker.reason,
      url: blocker.url || '',
    });
  });

  if (evidenceSummary && evidenceSummary.ok !== true) {
    blockers.push({
      category: 'evidence',
      detail: evidenceSummary.error || 'unknown error',
      name: 'evidence verification',
      reason: 'failed',
    });
  }

  return blockers;
}

function formatDecisionBlockers(blockers) {
  if (!blockers?.length) return '- None.';
  return blockers.map(blocker => {
    if (blocker.category === 'ci') {
      const label = markdownLink(blocker.name, blocker.url);
      const logs = blocker.logsUrl ? `; logs: ${markdownLink('download', blocker.logsUrl)}` : '';
      return `- CI ${label}: ${blocker.reason}${logs}`;
    }
    if (blocker.category === 'working-tree') {
      return `- Working tree: ${blocker.reason} (${blocker.detail})`;
    }
    if (blocker.category === 'evidence') {
      return `- Evidence verification: ${blocker.detail}`;
    }
    return `- ${blocker.name}: ${blocker.reason}`;
  }).join('\n');
}

export function buildReleaseCandidatePayload({
  branch,
  downloadedLogs = [],
  evidenceFiles = [],
  evidenceSummary = null,
  generatedAt = new Date().toISOString(),
  gitStatus = '',
  headSha,
  repo,
  requiredJobSummary = null,
  run = null,
}) {
  const treeClean = gitStatus.trim().length === 0;
  const requiredJobsReady = requiredJobSummary?.ok === true;
  const runReady = isRunReady(run);
  const ciReady = requiredJobsReady && runReady;
  const ciBlockers = buildCiBlockers({ requiredJobSummary, run });
  const evidenceReady = evidenceSummary ? evidenceSummary.ok === true : true;
  const decisionBlockers = buildDecisionBlockers({
    ciBlockers,
    evidenceSummary,
    gitStatus,
  });
  const requiredJobs = requiredJobSummary
    ? requiredJobSummary.rows.map(row => ({
      conclusion: row.conclusion,
      id: row.id,
      logsUrl: row.logsUrl,
      name: row.name,
      ok: row.ok,
      reason: row.reason,
      status: row.status,
      url: row.url,
    }))
    : [];

  return {
    branch: branch || '',
    ci: {
      blockers: ciBlockers,
      checked: Boolean(requiredJobSummary),
      downloadedLogs,
      ready: ciReady,
      requiredJobsReady,
      requiredJobs,
      runReady,
      run: run
        ? {
          conclusion: run.conclusion || '',
          headSha: run.head_sha || '',
          id: run.id,
          name: run.name || '',
          status: run.status || '',
          url: run.html_url || '',
        }
        : null,
    },
    evidenceFiles,
    evidenceVerification: evidenceSummary
      ? {
        checked: true,
        error: evidenceSummary.error || '',
        foundTypes: evidenceSummary.foundTypes || [],
        ok: evidenceSummary.ok,
        output: evidenceSummary.output || '',
        requiredTypes: evidenceSummary.requiredTypes || [],
      }
      : {
        checked: false,
        error: '',
        foundTypes: [],
        ok: true,
        output: '',
        requiredTypes: [],
      },
    generatedAt,
    headSha: headSha || '',
    decisionBlockers,
    ready: treeClean && ciReady && evidenceReady,
    repo: repo || '',
    workingTree: {
      clean: treeClean,
      status: gitStatus,
    },
  };
}

export function buildReleaseCandidateJson(options) {
  return `${JSON.stringify(buildReleaseCandidatePayload(options), null, 2)}\n`;
}

export function buildReleaseCandidateSummary(options) {
  const {
    branch,
    downloadedLogs = [],
    evidenceFiles = [],
    evidenceSummary = null,
    generatedAt = new Date().toISOString(),
    gitStatus = '',
    headSha,
    repo,
    requiredJobSummary = null,
    run = null,
  } = options;
  const payload = buildReleaseCandidatePayload({
    branch,
    downloadedLogs,
    evidenceFiles,
    evidenceSummary,
    generatedAt,
    gitStatus,
    headSha,
    repo,
    requiredJobSummary,
    run,
  });
  const runLabel = run
    ? markdownLink(`${run.name || 'workflow'} #${run.id}`, run.html_url)
    : 'not checked';
  const runState = run ? `${run.status || 'unknown'}/${run.conclusion || 'unknown'}` : 'not checked';

  return [
    '# Stage 7 Release Candidate Summary',
    '',
    `Generated: ${payload.generatedAt}`,
    `Repository: ${payload.repo || 'unknown'}`,
    `Branch: ${payload.branch || 'unknown'}`,
    `Commit: ${payload.headSha || 'unknown'}`,
    `Working tree: ${payload.workingTree.clean ? 'clean' : 'dirty'}`,
    `CI run: ${runLabel} (${runState})`,
    '',
    '## Required CI Jobs',
    '',
    formatJobRows(requiredJobSummary),
    '',
    '## CI Blockers',
    '',
    formatCiBlockers(payload.ci.blockers),
    '',
    '## CI Log Downloads',
    '',
    formatDownloadedLogs(downloadedLogs),
    '',
    '## Evidence Files',
    '',
    formatEvidenceFiles(evidenceFiles),
    '',
    `Evidence verification: ${formatEvidenceVerification(evidenceSummary)}`,
    '',
    '## Decision Blockers',
    '',
    formatDecisionBlockers(payload.decisionBlockers),
    '',
    '## Decision',
    '',
    `Ready for deployment handoff: ${payload.ready ? 'yes' : 'no'}`,
    '',
  ].join('\n');
}

export function verifyEvidenceFiles(evidenceFiles, {
  noFileCheck = false,
  requireEvidence = false,
  requiredEvidenceTypes = [],
} = {}) {
  const requiredTypes = normalizeRequiredEvidenceTypes(requiredEvidenceTypes);
  if (!evidenceFiles.length) {
    if (requiredTypes.length) {
      return {
        error: `Missing required Stage 7 evidence type(s): ${requiredTypes.join(', ')}`,
        foundTypes: [],
        ok: false,
        output: '',
        requiredTypes,
      };
    }
    if (requireEvidence) {
      return {
        error: 'At least one Stage 7 evidence file is required.',
        foundTypes: [],
        ok: false,
        output: '',
        requiredTypes,
      };
    }
    return {
      error: '',
      foundTypes: [],
      ok: true,
      output: 'No optional evidence files listed.',
      requiredTypes,
    };
  }

  const args = [path.join(SCRIPT_DIR, 'verify_stage7_evidence.mjs')];
  if (noFileCheck) args.push('--no-file-check');
  args.push(...evidenceFiles);

  try {
    const output = execFileSync(process.execPath, args, {
      cwd: ROOT_DIR,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
    }).trim();
    const foundTypes = collectEvidenceTypes(evidenceFiles);
    const missingTypes = missingEvidenceTypes(foundTypes, requiredTypes);
    if (missingTypes.length) {
      return {
        error: `Missing required Stage 7 evidence type(s): ${missingTypes.join(', ')}`,
        foundTypes,
        ok: false,
        output,
        requiredTypes,
      };
    }
    return {
      error: '',
      foundTypes,
      ok: true,
      output,
      requiredTypes,
    };
  } catch (error) {
    return {
      error: (error.stderr || error.stdout || error.message || String(error)).trim(),
      foundTypes: [],
      ok: false,
      output: (error.stdout || '').trim(),
      requiredTypes,
    };
  }
}

async function writeOutput(filePath, text) {
  const fullPath = path.resolve(filePath);
  await mkdir(path.dirname(fullPath), { recursive: true });
  await writeFile(fullPath, text, 'utf8');
  return fullPath;
}

export async function runCli(argv = process.argv.slice(2), {
  fetchImpl = globalThis.fetch,
  sleepImpl = sleep,
  token = process.env.GITHUB_TOKEN,
} = {}) {
  const args = parseArgs(argv);
  if (args.help) {
    console.log(usage());
    return 0;
  }
  if (args.format !== 'markdown' && args.format !== 'json') {
    throw new Error('--format must be markdown or json.');
  }

  const local = getLocalReleaseContext();
  const repo = args.repo || local.repo;
  const branch = args.branch || local.branch || 'main';
  const headSha = args.headSha || local.headSha;

  if (!args.noCi && !repo) {
    throw new Error('GitHub repo is required. Pass --repo owner/name or configure origin.');
  }
  if (!args.noCi && !headSha) {
    throw new Error('Head SHA is required. Pass --head <sha> or run from a git checkout.');
  }

  let run = null;
  let requiredJobSummary = null;
  if (!args.noCi) {
    if (args.wait) {
      const result = await waitForRequiredCiJobs({
        repo,
        branch,
        headSha,
        runId: args.runId,
        fetchImpl,
        pollSeconds: args.pollSeconds,
        sleepImpl,
        timeoutSeconds: args.timeoutSeconds,
        token,
      });
      run = result.run;
      requiredJobSummary = result.requiredJobSummary;
    } else {
      validateWaitOptions({ pollSeconds: args.pollSeconds, timeoutSeconds: args.timeoutSeconds });
      run = await fetchRunForHead({ repo, branch, headSha, runId: args.runId, fetchImpl, token });
      const jobs = await fetchRunJobs({ repo, runId: run.id, fetchImpl, token });
      requiredJobSummary = summarizeRequiredCiJobs(jobs);
    }
  }

  const downloadedLogs = args.blockerLogDir
    ? await downloadCiBlockerLogs(buildCiBlockers({ requiredJobSummary, run }), {
      fetchImpl,
      outputDir: args.blockerLogDir,
      token,
    })
    : [];

  const summaryOptions = {
    branch,
    downloadedLogs,
    evidenceFiles: args.evidenceFiles,
    evidenceSummary: args.evidenceVerified || args.evidenceRequired || args.requiredEvidenceTypes.length
      ? verifyEvidenceFiles(args.evidenceFiles, {
        noFileCheck: args.evidenceNoFileCheck,
        requireEvidence: args.evidenceRequired,
        requiredEvidenceTypes: args.requiredEvidenceTypes,
      })
      : null,
    gitStatus: local.status,
    headSha,
    repo,
    requiredJobSummary,
    run,
  };
  const releasePayload = buildReleaseCandidatePayload(summaryOptions);
  const summary = args.format === 'json'
    ? `${JSON.stringify(releasePayload, null, 2)}\n`
    : buildReleaseCandidateSummary(summaryOptions);

  if (args.output) {
    const outputPath = await writeOutput(args.output, summary);
    console.log(`Wrote ${outputPath}`);
  } else {
    console.log(summary);
  }

  return releasePayload.ready ? 0 : 1;
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
