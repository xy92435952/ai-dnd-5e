#!/usr/bin/env node
import { spawn, spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(scriptDir, '..');

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

function parsePositiveMs(value, optionName) {
  const timeoutMs = Number(value);
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
    throw new Error(`${optionName} must be a positive number.`);
  }
  return timeoutMs;
}

function todayTag() {
  const now = new Date();
  return [
    String(now.getFullYear()),
    String(now.getMonth() + 1).padStart(2, '0'),
    String(now.getDate()).padStart(2, '0'),
  ].join('');
}

export function normalizeOrigin(value) {
  const origin = String(value || '').trim().replace(/\/+$/, '');
  if (!origin) return '';
  try {
    const parsed = new URL(origin);
    if (!/^https?:$/.test(parsed.protocol)) {
      throw new Error('unsupported protocol');
    }
    return parsed.origin;
  } catch {
    throw new Error(`--frontend-origin must be an http(s) origin, got "${value}".`);
  }
}

function normalizeArtifactTag(value) {
  const tag = String(value || '').trim();
  if (!/^[A-Za-z0-9_.-]+$/.test(tag)) {
    throw new Error(`Unsupported artifact tag "${value}". Use only letters, numbers, dot, underscore, or dash.`);
  }
  return tag;
}

export function parseArgs(argv = process.argv.slice(2), env = process.env) {
  const args = {
    artifactTag: env.STAGE7_PUBLIC_BROWSER_SMOKE_ARTIFACT_TAG || todayTag(),
    browserPath: env.STAGE7_PUBLIC_BROWSER_PATH || env.CHROME_PATH || '',
    frontendOrigin: env.STAGE7_PUBLIC_FRONTEND_ORIGIN || '',
    help: false,
    output: env.STAGE7_PUBLIC_BROWSER_SMOKE_OUTPUT || '',
    password: env.STAGE7_PUBLIC_PASSWORD || '',
    sessionId: env.STAGE7_PUBLIC_SESSION_ID || '',
    timeoutMs: env.STAGE7_PUBLIC_BROWSER_SMOKE_TIMEOUT_MS
      ? parsePositiveMs(env.STAGE7_PUBLIC_BROWSER_SMOKE_TIMEOUT_MS, 'STAGE7_PUBLIC_BROWSER_SMOKE_TIMEOUT_MS')
      : 45_000,
    username: env.STAGE7_PUBLIC_USERNAME || '',
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--help' || arg === '-h') {
      args.help = true;
      continue;
    }
    if (arg === '--frontend-origin') {
      args.frontendOrigin = requiredOptionValue(argv, index, arg);
      index += 1;
      continue;
    }
    if (arg.startsWith('--frontend-origin=')) {
      args.frontendOrigin = requiredInlineOptionValue(arg.slice('--frontend-origin='.length), '--frontend-origin');
      continue;
    }
    if (arg === '--username') {
      args.username = requiredOptionValue(argv, index, arg);
      index += 1;
      continue;
    }
    if (arg.startsWith('--username=')) {
      args.username = requiredInlineOptionValue(arg.slice('--username='.length), '--username');
      continue;
    }
    if (arg === '--password') {
      args.password = requiredOptionValue(argv, index, arg);
      index += 1;
      continue;
    }
    if (arg.startsWith('--password=')) {
      args.password = requiredInlineOptionValue(arg.slice('--password='.length), '--password');
      continue;
    }
    if (arg === '--session-id') {
      args.sessionId = requiredOptionValue(argv, index, arg);
      index += 1;
      continue;
    }
    if (arg.startsWith('--session-id=')) {
      args.sessionId = requiredInlineOptionValue(arg.slice('--session-id='.length), '--session-id');
      continue;
    }
    if (arg === '--artifact-tag') {
      args.artifactTag = requiredOptionValue(argv, index, arg);
      index += 1;
      continue;
    }
    if (arg.startsWith('--artifact-tag=')) {
      args.artifactTag = requiredInlineOptionValue(arg.slice('--artifact-tag='.length), '--artifact-tag');
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
      args.timeoutMs = parsePositiveMs(requiredOptionValue(argv, index, arg), arg);
      index += 1;
      continue;
    }
    if (arg.startsWith('--timeout-ms=')) {
      args.timeoutMs = parsePositiveMs(
        requiredInlineOptionValue(arg.slice('--timeout-ms='.length), '--timeout-ms'),
        '--timeout-ms',
      );
      continue;
    }
    if (arg === '--browser-path') {
      args.browserPath = requiredOptionValue(argv, index, arg);
      index += 1;
      continue;
    }
    if (arg.startsWith('--browser-path=')) {
      args.browserPath = requiredInlineOptionValue(arg.slice('--browser-path='.length), '--browser-path');
      continue;
    }
    if (arg.startsWith('--')) {
      throw new Error(`Unknown option: ${arg}`);
    }
    throw new Error(`Unknown argument: ${arg}`);
  }

  if (args.help) return args;
  args.frontendOrigin = normalizeOrigin(args.frontendOrigin);
  args.artifactTag = normalizeArtifactTag(args.artifactTag);
  return args;
}

export function usage() {
  return [
    'Usage:',
    '  node scripts/stage7_public_browser_smoke.mjs --frontend-origin <origin> --username <user> --password <pass> --session-id <id> [--artifact-tag <tag>] [--output <json-file>] [--timeout-ms <ms>]',
    '',
    'Runs the Stage 7 post-deploy public browser smoke against an existing deployment.',
    'The smoke logs in through the public UI, loads Adventure, loads Combat, and verifies same-origin /api session, combat, and skill-bar data.',
    '',
    'Environment variables are also supported:',
    '  STAGE7_PUBLIC_FRONTEND_ORIGIN, STAGE7_PUBLIC_USERNAME, STAGE7_PUBLIC_PASSWORD, STAGE7_PUBLIC_SESSION_ID',
  ].join('\n');
}

export function validateRequiredArgs(args) {
  const missing = [];
  if (!args.frontendOrigin) missing.push('--frontend-origin');
  if (!args.username) missing.push('--username');
  if (!args.password) missing.push('--password');
  if (!args.sessionId) missing.push('--session-id');
  if (missing.length) {
    throw new Error(`Missing required public browser smoke option(s): ${missing.join(', ')}.`);
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function randomPort() {
  return 48000 + Math.floor(Math.random() * 7000);
}

function commandExists(command) {
  const checker = process.platform === 'win32' ? 'where' : 'command';
  const args = process.platform === 'win32' ? [command] : ['-v', command];
  const result = spawnSync(checker, args, { stdio: 'ignore', shell: process.platform !== 'win32' });
  return result.status === 0;
}

function resolveBrowserPath(explicit = '') {
  const candidates = [
    explicit,
    'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
    'C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe',
    'C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe',
  ].filter(Boolean);
  const found = candidates.find(candidate => existsSync(candidate));
  if (found) return found;

  const commandCandidates = [
    'google-chrome',
    'google-chrome-stable',
    'chromium',
    'chromium-browser',
    'microsoft-edge',
    'microsoft-edge-stable',
    'msedge',
  ];
  const foundCommand = commandCandidates.find(commandExists);
  if (foundCommand) return foundCommand;

  throw new Error(
    `No Chrome/Chromium/Edge browser found. Checked paths: ${candidates.join(', ')}; `
    + `checked commands: ${commandCandidates.join(', ')}`,
  );
}

async function waitFor(description, fn, timeoutMs = 30000, intervalMs = 250) {
  const deadline = Date.now() + timeoutMs;
  let lastError = null;
  while (Date.now() < deadline) {
    try {
      const value = await fn();
      if (value) return value;
    } catch (error) {
      lastError = error;
    }
    await sleep(intervalMs);
  }
  throw new Error(`Timed out waiting for ${description}${lastError ? `: ${lastError.message}` : ''}`);
}

async function httpJson(url, options = {}) {
  const response = await fetch(url, options);
  const bodyText = await response.text();
  let body = null;
  try {
    body = bodyText ? JSON.parse(bodyText) : null;
  } catch {
    body = bodyText;
  }
  if (!response.ok) {
    throw new Error(`HTTP ${response.status} ${url}: ${typeof body === 'string' ? body : JSON.stringify(body)}`);
  }
  return body;
}

function connectCdp(wsUrl) {
  return new Promise((resolve, reject) => {
    const ws = new WebSocket(wsUrl);
    const pending = new Map();
    const events = [];
    let nextId = 1;
    let opened = false;
    const closeWaiters = [];
    const openTimeout = setTimeout(() => {
      if (!opened) reject(new Error('CDP websocket open timeout'));
    }, 10000);

    function settleClosed() {
      clearTimeout(openTimeout);
      for (const item of pending.values()) {
        clearTimeout(item.timer);
        item.reject(new Error(`CDP closed before ${item.method} completed`));
      }
      pending.clear();
      while (closeWaiters.length > 0) {
        closeWaiters.shift()?.();
      }
    }

    ws.addEventListener('open', () => {
      opened = true;
      clearTimeout(openTimeout);
      resolve({
        events,
        send(method, params = {}, timeoutMs = 15000, sessionId = null) {
          const id = nextId += 1;
          return new Promise((innerResolve, innerReject) => {
            const timer = setTimeout(() => {
              pending.delete(id);
              innerReject(new Error(`CDP timeout: ${method}`));
            }, timeoutMs);
            pending.set(id, { resolve: innerResolve, reject: innerReject, timer, method });
            const message = { id, method, params };
            if (sessionId) message.sessionId = sessionId;
            ws.send(JSON.stringify(message));
          });
        },
        close(timeoutMs = 2000) {
          settleClosed();
          if (ws.readyState === WebSocket.CLOSED) return Promise.resolve();
          return Promise.race([
            new Promise(resolveClose => {
              closeWaiters.push(resolveClose);
              try { ws.close(1000, 'public smoke complete'); } catch { resolveClose(); }
            }),
            sleep(timeoutMs),
          ]);
        },
      });
    });

    ws.addEventListener('message', event => {
      Promise.resolve(event.data)
        .then(data => {
          if (typeof data === 'string') return data;
          if (data instanceof ArrayBuffer) return Buffer.from(data).toString('utf8');
          if (ArrayBuffer.isView(data)) return Buffer.from(data.buffer, data.byteOffset, data.byteLength).toString('utf8');
          return String(data);
        })
        .then(raw => {
          const msg = JSON.parse(raw);
          if (!msg.id) {
            if (
              msg.method === 'Runtime.exceptionThrown'
              || msg.method === 'Runtime.consoleAPICalled'
              || msg.method === 'Log.entryAdded'
              || msg.method === 'Network.loadingFailed'
            ) {
              events.push(msg);
              if (events.length > 100) events.shift();
            }
            return;
          }
          const item = pending.get(msg.id);
          if (!item) return;
          pending.delete(msg.id);
          clearTimeout(item.timer);
          if (msg.error) {
            item.reject(new Error(`${item.method}: ${msg.error.message || JSON.stringify(msg.error)}`));
          } else {
            item.resolve(msg.result || {});
          }
        })
        .catch(error => {
          events.push({ method: 'CDP.messageParseFailed', error: error.message || String(error) });
          if (events.length > 100) events.shift();
        });
    });

    ws.addEventListener('error', event => {
      clearTimeout(openTimeout);
      reject(new Error(`CDP websocket error: ${event.message || 'unknown'}`));
    });

    ws.addEventListener('close', settleClosed);
  });
}

async function connectBrowserPageCdp(port, targetUrl, getChromeDebug = () => null) {
  const version = await waitFor('browser debugger', async () => {
    const chromeDebug = getChromeDebug();
    if (chromeDebug?.exit) {
      throw new Error(`Chrome exited before debugger connection: ${JSON.stringify(chromeDebug)}`);
    }
    try {
      const value = await httpJson(`http://127.0.0.1:${port}/json/version`);
      return value?.webSocketDebuggerUrl ? value : null;
    } catch {
      return null;
    }
  }, 30000, 200);
  const browserCdp = await connectCdp(version.webSocketDebuggerUrl);
  const targets = await browserCdp.send('Target.getTargets', {}, 30000).catch(() => ({ targetInfos: [] }));
  const targetInfo = (targets.targetInfos || []).find(target => (
    target.type === 'page'
    && typeof target.url === 'string'
    && target.url.startsWith(targetUrl)
  )) || (targets.targetInfos || []).find(target => target.type === 'page');
  const target = targetInfo || await browserCdp.send('Target.createTarget', { url: targetUrl }, 30000);
  const attached = await browserCdp.send('Target.attachToTarget', {
    targetId: target.targetId,
    flatten: true,
  }, 30000);
  return {
    events: browserCdp.events,
    close() {
      return browserCdp.close();
    },
    send(method, params = {}, timeoutMs = 15000) {
      return browserCdp.send(method, params, timeoutMs, attached.sessionId);
    },
  };
}

async function evalPage(cdp, expression, timeoutMs = 15000) {
  const result = await cdp.send('Runtime.evaluate', {
    expression,
    awaitPromise: true,
    returnByValue: true,
    userGesture: true,
  }, timeoutMs);
  if (result.exceptionDetails) {
    const detail = result.exceptionDetails.exception?.description
      || result.exceptionDetails.exception?.value
      || result.exceptionDetails.text
      || JSON.stringify(result.exceptionDetails);
    throw new Error(detail);
  }
  return result.result?.value;
}

async function navigate(cdp, url) {
  await cdp.send('Page.navigate', { url }, 15000);
  await sleep(1000);
}

async function screenshot(cdp, filePath) {
  await mkdir(path.dirname(filePath), { recursive: true });
  const capture = await cdp.send('Page.captureScreenshot', {
    format: 'png',
    fromSurface: true,
    captureBeyondViewport: false,
  }, 30000);
  await writeFile(filePath, Buffer.from(capture.data, 'base64'));
}

async function writeJsonArtifact(filePath, value) {
  await mkdir(path.dirname(filePath), { recursive: true });
  await writeFile(filePath, `${JSON.stringify(value, null, 2)}\n`, 'utf8');
}

async function readPageState(cdp) {
  return evalPage(cdp, `(() => ({
    path: window.location.pathname,
    tokenPresent: Boolean(localStorage.getItem('token')),
    loginFormVisible: Boolean(document.querySelector('form.login-form') && document.querySelector('input[autocomplete="username"]')),
    adventureLoaded: Boolean(document.querySelector('.adventure-page')),
    combatLoaded: Boolean(document.querySelector('.combat-page-shell')),
    skillButtonCount: document.querySelectorAll('.skill-bar [role="button"]').length,
    text: (document.body?.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 1000),
  }))()`);
}

async function submitLogin(cdp, username, password) {
  return evalPage(cdp, `(() => {
    const usernameInput = document.querySelector('input[autocomplete="username"]');
    const passwordInput = document.querySelector('input[autocomplete="current-password"], input[type="password"]');
    const form = document.querySelector('form.login-form') || usernameInput?.closest('form');
    if (!usernameInput || !passwordInput || !form) {
      return { ok: false, reason: 'login form controls missing' };
    }
    const setValue = (input, value) => {
      const setter = Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set;
      setter.call(input, value);
      input.dispatchEvent(new Event('input', { bubbles: true }));
      input.dispatchEvent(new Event('change', { bubbles: true }));
    };
    setValue(usernameInput, ${JSON.stringify(username)});
    setValue(passwordInput, ${JSON.stringify(password)});
    if (typeof form.requestSubmit === 'function') {
      form.requestSubmit();
    } else {
      form.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    }
    return { ok: true };
  })()`);
}

async function fetchApiJson(cdp, urlPath, timeoutMs = 30000) {
  return evalPage(cdp, `(() => fetch(${JSON.stringify(urlPath)}, {
    headers: {
      accept: 'application/json',
      authorization: localStorage.getItem('token') ? 'Bearer ' + localStorage.getItem('token') : '',
    },
  }).then(async (response) => {
    const text = await response.text();
    let body = null;
    try { body = text ? JSON.parse(text) : null; } catch { body = text; }
    return { ok: response.ok, status: response.status, body };
  }))()`, timeoutMs);
}

function browserEventSummary(event) {
  if (event.method === 'Runtime.exceptionThrown') {
    return event.params?.exceptionDetails?.exception?.description
      || event.params?.exceptionDetails?.text
      || 'runtime exception';
  }
  if (event.method === 'Runtime.consoleAPICalled') {
    return (event.params?.args || [])
      .map(arg => arg.value || arg.description || '')
      .filter(Boolean)
      .join(' ')
      || event.params?.type
      || 'console event';
  }
  if (event.method === 'Log.entryAdded') {
    return event.params?.entry?.text || event.params?.entry?.level || 'log entry';
  }
  if (event.method === 'Network.loadingFailed') {
    return event.params?.errorText || 'network load failed';
  }
  return event.error || event.method || 'browser event';
}

export function collectBlockingBrowserEvents(events = []) {
  return events.filter(event => {
    if (event.method === 'Runtime.exceptionThrown') return true;
    if (event.method === 'CDP.messageParseFailed') return true;
    if (event.method === 'Runtime.consoleAPICalled') return event.params?.type === 'error';
    if (event.method === 'Log.entryAdded') {
      const level = String(event.params?.entry?.level || '').toLowerCase();
      const text = String(event.params?.entry?.text || '');
      return level === 'error' && !/favicon\.ico/i.test(text);
    }
    if (event.method === 'Network.loadingFailed') {
      const errorText = String(event.params?.errorText || '');
      return errorText && !/ERR_ABORTED/i.test(errorText);
    }
    return false;
  }).map(event => ({
    method: event.method,
    message: browserEventSummary(event).slice(0, 500),
  }));
}

export function buildPublicBrowserPayload({
  browserErrors = [],
  checks = {},
  createdAt = new Date().toISOString(),
  frontendOrigin = '',
  screenshots = {},
  sessionId = '',
  username = '',
} = {}) {
  const assertions = {
    login_ok: checks.login_token_present === true && checks.login_path !== '/login',
    adventure_loaded: checks.adventure_loaded === true && checks.session_api_ok === true,
    combat_loaded: checks.combat_loaded === true && checks.combat_api_ok === true,
    combat_session_active: checks.session_combat_active === true,
    skill_bar_loaded: Number(checks.skill_bar_count || 0) > 0 && Number(checks.skill_bar_dom_count || 0) > 0,
    no_browser_errors: browserErrors.length === 0,
  };
  const ok = Object.values(assertions).every(Boolean);
  return {
    ok,
    mode: 'stage7-public-browser-smoke',
    created_at: createdAt,
    frontend_origin: frontendOrigin,
    session_id: sessionId,
    username,
    checks,
    assertions,
    browser: {
      errors: browserErrors,
    },
    screenshots,
  };
}

async function stopProcess(proc) {
  if (!proc) return;
  const waitForClose = timeoutMs => {
    if (proc.exitCode !== null) return Promise.resolve();
    return Promise.race([
      new Promise(resolve => proc.once('close', resolve)),
      sleep(timeoutMs),
    ]);
  };
  if (proc.exitCode === null) {
    if (process.platform === 'win32') {
      spawnSync('taskkill', ['/PID', String(proc.pid), '/T', '/F'], { stdio: 'ignore' });
    } else {
      proc.kill('SIGTERM');
    }
  }
  await waitForClose(5000);
  proc.removeAllListeners();
  proc.stdout?.destroy();
  proc.stderr?.destroy();
  proc.stdin?.destroy();
  proc.unref?.();
}

function defaultArtifactPath(kind, artifactTag, extension) {
  return path.join(root, 'artifacts', `stage7-public-browser-smoke-${kind}-${artifactTag}.${extension}`);
}

export async function runCli(argv = process.argv.slice(2)) {
  const args = parseArgs(argv);
  if (args.help) {
    console.log(usage());
    return 0;
  }
  validateRequiredArgs(args);

  const outputPath = args.output || defaultArtifactPath('result', args.artifactTag, 'json');
  const adventureScreenshot = defaultArtifactPath('adventure', args.artifactTag, 'png');
  const combatScreenshot = defaultArtifactPath('combat', args.artifactTag, 'png');
  const debugPort = randomPort();
  const chromeDebug = { exit: null, stdout: '', stderr: '' };
  let chrome = null;
  let cdp = null;
  let payload = null;
  let profileDir = '';

  try {
    await mkdir(path.join(root, 'artifacts'), { recursive: true });
    profileDir = await mkdtemp(path.join(tmpdir(), 'codex-dnd-public-smoke-chrome-'));
    chrome = spawn(resolveBrowserPath(args.browserPath), [
      '--headless=new',
      `--remote-debugging-port=${debugPort}`,
      `--user-data-dir=${profileDir}`,
      '--remote-allow-origins=*',
      '--disable-gpu',
      '--disable-gpu-compositing',
      '--disable-gpu-rasterization',
      '--disable-accelerated-2d-canvas',
      '--disable-accelerated-video-decode',
      '--disable-gpu-sandbox',
      '--disable-features=UseSkiaRenderer,VizDisplayCompositor,CalculateNativeWinOcclusion,Vulkan,DawnGraphite',
      '--use-angle=swiftshader',
      '--use-gl=swiftshader',
      '--no-sandbox',
      '--disable-extensions',
      '--no-first-run',
      '--no-default-browser-check',
      '--window-size=1440,1000',
      `${args.frontendOrigin}/login`,
    ], { stdio: ['ignore', 'pipe', 'pipe'], windowsHide: true });
    chrome.stdout?.on('data', chunk => {
      chromeDebug.stdout = `${chromeDebug.stdout}${chunk.toString()}`.slice(-4000);
    });
    chrome.stderr?.on('data', chunk => {
      chromeDebug.stderr = `${chromeDebug.stderr}${chunk.toString()}`.slice(-4000);
    });
    chrome.once('exit', (code, signal) => {
      chromeDebug.exit = { code, signal };
    });

    cdp = await connectBrowserPageCdp(debugPort, `${args.frontendOrigin}/login`, () => chromeDebug)
      .catch(error => {
        throw new Error(`${error.message}\nChrome debug:\n${JSON.stringify(chromeDebug, null, 2)}`);
      });
    await cdp.send('Page.enable');
    await cdp.send('Runtime.enable');
    await cdp.send('Log.enable');
    await cdp.send('Network.enable');
    await cdp.send('Emulation.setDeviceMetricsOverride', {
      width: 1440,
      height: 1000,
      deviceScaleFactor: 1,
      mobile: false,
    });

    await navigate(cdp, `${args.frontendOrigin}/login`);
    await waitFor('public login form', async () => {
      const state = await readPageState(cdp);
      return state.loginFormVisible ? state : null;
    }, args.timeoutMs, 250);
    const submitted = await submitLogin(cdp, args.username, args.password);
    assert(submitted.ok, submitted.reason || 'login submit failed');

    const loginState = await waitFor('public login token', async () => {
      const state = await readPageState(cdp);
      return state.tokenPresent && state.path !== '/login' ? state : null;
    }, args.timeoutMs, 250);

    await navigate(cdp, `${args.frontendOrigin}/adventure/${args.sessionId}?stage7PublicSmoke=1`);
    const adventureState = await waitFor('public Adventure page', async () => {
      const state = await readPageState(cdp);
      return state.adventureLoaded ? state : null;
    }, args.timeoutMs, 250);
    const sessionApi = await fetchApiJson(cdp, `/api/game/sessions/${args.sessionId}`, args.timeoutMs);
    const sessionBody = sessionApi.body || {};
    assert(sessionApi.ok, `session API failed with HTTP ${sessionApi.status}`);
    assert(sessionBody.combat_active === true, 'public smoke session must be combat_active=true to verify Combat load');
    assert(sessionBody.player?.id, 'session API did not include player.id');
    await screenshot(cdp, adventureScreenshot);

    await navigate(cdp, `${args.frontendOrigin}/combat/${args.sessionId}?stage7PublicSmoke=1`);
    const combatState = await waitFor('public Combat page', async () => {
      const state = await readPageState(cdp);
      return state.combatLoaded ? state : null;
    }, args.timeoutMs, 250);
    const combatApi = await fetchApiJson(cdp, `/api/game/combat/${args.sessionId}`, args.timeoutMs);
    assert(combatApi.ok, `combat API failed with HTTP ${combatApi.status}`);
    const skillBarApi = await fetchApiJson(
      cdp,
      `/api/game/combat/${args.sessionId}/skill-bar?entity_id=${encodeURIComponent(sessionBody.player.id)}`,
      args.timeoutMs,
    );
    assert(skillBarApi.ok, `skill-bar API failed with HTTP ${skillBarApi.status}`);
    await screenshot(cdp, combatScreenshot);

    const skillBarCount = Array.isArray(skillBarApi.body?.bar) ? skillBarApi.body.bar.length : 0;
    payload = buildPublicBrowserPayload({
      browserErrors: collectBlockingBrowserEvents(cdp.events),
      checks: {
        login_path: loginState.path,
        login_token_present: loginState.tokenPresent,
        adventure_path: adventureState.path,
        adventure_loaded: adventureState.adventureLoaded,
        session_api_ok: sessionApi.ok,
        session_id_matches: sessionBody.id === args.sessionId || sessionBody.session_id === args.sessionId,
        session_combat_active: sessionBody.combat_active === true,
        current_scene_present: Boolean(sessionBody.current_scene || sessionBody.game_state?.current_scene),
        combat_path: combatState.path,
        combat_loaded: combatState.combatLoaded,
        combat_api_ok: combatApi.ok,
        combat_round: Number(combatApi.body?.round_number || combatApi.body?.round || 0),
        combat_turn_order_count: Array.isArray(combatApi.body?.turn_order) ? combatApi.body.turn_order.length : 0,
        combat_entities_count: combatApi.body?.entities && typeof combatApi.body.entities === 'object'
          ? Object.keys(combatApi.body.entities).length
          : 0,
        skill_bar_entity_id: skillBarApi.body?.entity_id || '',
        skill_bar_count: skillBarCount,
        skill_bar_dom_count: combatState.skillButtonCount,
      },
      frontendOrigin: args.frontendOrigin,
      screenshots: {
        adventure: adventureScreenshot,
        combat: combatScreenshot,
      },
      sessionId: args.sessionId,
      username: args.username,
    });
  } catch (error) {
    payload = buildPublicBrowserPayload({
      browserErrors: [
        ...collectBlockingBrowserEvents(cdp?.events || []),
        { method: 'Smoke.failure', message: error.message || String(error) },
      ],
      checks: {},
      frontendOrigin: args.frontendOrigin,
      screenshots: {
        adventure: adventureScreenshot,
        combat: combatScreenshot,
      },
      sessionId: args.sessionId,
      username: args.username,
    });
  } finally {
    if (cdp) await cdp.close().catch(() => {});
    await stopProcess(chrome).catch(() => {});
    if (profileDir) await rm(profileDir, { recursive: true, force: true }).catch(() => {});
  }

  await writeJsonArtifact(outputPath, payload);
  console.log(`Wrote ${path.resolve(outputPath)}`);
  return payload.ok ? 0 : 1;
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
