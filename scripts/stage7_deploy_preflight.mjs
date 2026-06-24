#!/usr/bin/env node
import { execFileSync } from 'node:child_process';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { pathToFileURL } from 'node:url';

export const DEFAULT_DEPLOY_IGNORE_PATHS = [
  'backend/.env',
  'frontend/dist',
  'backend/.venv',
  'artifacts',
  '.codex-test-artifacts',
];

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

export function parseArgs(argv = process.argv.slice(2)) {
  const args = {
    allowDirty: false,
    format: 'markdown',
    help: false,
    output: '',
    paths: [],
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--help' || arg === '-h') {
      args.help = true;
      continue;
    }
    if (arg === '--allow-dirty') {
      args.allowDirty = true;
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
    if (arg === '--path') {
      args.paths.push(requiredOptionValue(argv, index, arg));
      index += 1;
      continue;
    }
    if (arg.startsWith('--path=')) {
      args.paths.push(requiredInlineOptionValue(arg.slice('--path='.length), '--path'));
      continue;
    }
    args.paths.push(arg);
  }

  args.paths = args.paths.filter(Boolean);
  return args;
}

export function usage() {
  return [
    'Usage:',
    '  node scripts/stage7_deploy_preflight.mjs [--format markdown|json] [--json] [--allow-dirty] [--output <file>] [--path <git-path>...]',
    '',
    'Checks the Stage 7 before-server-update preflight:',
    '  - working tree is clean unless --allow-dirty is set',
    `  - required local-only paths are ignored: ${DEFAULT_DEPLOY_IGNORE_PATHS.join(', ')}`,
  ].join('\n');
}

export function parseCheckIgnoreOutput(output) {
  const line = String(output || '').split(/\r?\n/).find(Boolean) || '';
  if (!line) return { source: '', pattern: '', matchedPath: '' };
  const tabIndex = line.lastIndexOf('\t');
  const left = tabIndex >= 0 ? line.slice(0, tabIndex) : line;
  const matchedPath = tabIndex >= 0 ? line.slice(tabIndex + 1) : '';
  const parts = left.split(':');
  return {
    source: parts.slice(0, 2).join(':'),
    pattern: parts.slice(2).join(':'),
    matchedPath,
  };
}

export function checkIgnoredPath(targetPath) {
  try {
    const output = execFileSync('git', ['check-ignore', '-v', '--', targetPath], {
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'ignore'],
    }).trim();
    return {
      ignored: true,
      path: targetPath,
      ...parseCheckIgnoreOutput(output),
    };
  } catch {
    return {
      ignored: false,
      matchedPath: '',
      path: targetPath,
      pattern: '',
      source: '',
    };
  }
}

export function buildPreflightPayload({
  allowDirty = false,
  generatedAt = new Date().toISOString(),
  gitStatus = '',
  ignoreResults = [],
} = {}) {
  const clean = gitStatus.trim().length === 0;
  const ignoredPathsReady = ignoreResults.every(result => result.ignored);
  const workingTreeReady = clean || allowDirty;

  return {
    generatedAt,
    ignoredPaths: ignoreResults,
    ignoredPathsReady,
    ready: workingTreeReady && ignoredPathsReady,
    workingTree: {
      allowDirty,
      clean,
      ready: workingTreeReady,
      status: gitStatus,
    },
  };
}

function formatStatusBlock(status) {
  if (!status.trim()) return '_clean_';
  return [
    '```text',
    status,
    '```',
  ].join('\n');
}

export function buildPreflightMarkdown(payload) {
  return [
    '# Stage 7 Deploy Preflight',
    '',
    `Generated: ${payload.generatedAt}`,
    `Ready for server update: ${payload.ready ? 'yes' : 'no'}`,
    `Working tree: ${payload.workingTree.clean ? 'clean' : 'dirty'}${payload.workingTree.allowDirty ? ' (allowed)' : ''}`,
    '',
    '## Ignored Paths',
    '',
    '| Path | Ignored | Rule |',
    '| --- | --- | --- |',
    ...payload.ignoredPaths.map(result => `| ${result.path} | ${result.ignored ? 'yes' : 'no'} | ${result.source ? `${result.source} ${result.pattern}` : '-'} |`),
    '',
    '## Git Status',
    '',
    formatStatusBlock(payload.workingTree.status),
    '',
  ].join('\n');
}

export function buildPreflightJson(payload) {
  return `${JSON.stringify(payload, null, 2)}\n`;
}

async function writeOutput(filePath, text) {
  const fullPath = path.resolve(filePath);
  await mkdir(path.dirname(fullPath), { recursive: true });
  await writeFile(fullPath, text, 'utf8');
  return fullPath;
}

export async function runCli(argv = process.argv.slice(2)) {
  const args = parseArgs(argv);
  if (args.help) {
    console.log(usage());
    return 0;
  }
  if (args.format !== 'markdown' && args.format !== 'json') {
    throw new Error('--format must be markdown or json.');
  }

  const paths = args.paths.length ? args.paths : DEFAULT_DEPLOY_IGNORE_PATHS;
  const payload = buildPreflightPayload({
    allowDirty: args.allowDirty,
    gitStatus: runGit(['status', '--short', '--untracked-files=all']),
    ignoreResults: paths.map(checkIgnoredPath),
  });
  const text = args.format === 'json'
    ? buildPreflightJson(payload)
    : buildPreflightMarkdown(payload);

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
