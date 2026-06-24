#!/usr/bin/env node
import { spawn, spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(scriptDir, '..');
const DEFAULT_STAGE7_5_COMBAT_CHOICE_TEXT = 'Secure the gate and start the Stage 7.5 training fight.';
const DEFAULT_STAGE7_5_CLAIM_LOOT_ID = 'loot_gear_gate_token_0';

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

function parseBooleanOption(value, optionName) {
  const normalized = String(value || '').trim().toLowerCase();
  if (['1', 'true', 'yes', 'on'].includes(normalized)) return true;
  if (['0', 'false', 'no', 'off'].includes(normalized)) return false;
  throw new Error(`${optionName} must be a boolean value.`);
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
    if (!/^https?:$/.test(parsed.protocol)) throw new Error('unsupported protocol');
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
    artifactTag: env.STAGE7_5_ARTIFACT_TAG || todayTag(),
    browserPath: env.STAGE7_5_BROWSER_PATH || env.CHROME_PATH || '',
    claimLootId: env.STAGE7_5_CLAIM_LOOT_ID || DEFAULT_STAGE7_5_CLAIM_LOOT_ID,
    combatChoiceText: env.STAGE7_5_COMBAT_CHOICE_TEXT || DEFAULT_STAGE7_5_COMBAT_CHOICE_TEXT,
    combatSessionId: env.STAGE7_5_COMBAT_SESSION_ID || '',
    explorationSessionId: env.STAGE7_5_EXPLORATION_SESSION_ID || '',
    frontendOrigin: env.STAGE7_5_FRONTEND_ORIGIN || '',
    help: false,
    mutating: env.STAGE7_5_MUTATING
      ? parseBooleanOption(env.STAGE7_5_MUTATING, 'STAGE7_5_MUTATING')
      : false,
    output: env.STAGE7_5_OUTPUT || '',
    password: env.STAGE7_5_PASSWORD || '',
    timeoutMs: env.STAGE7_5_TIMEOUT_MS
      ? parsePositiveMs(env.STAGE7_5_TIMEOUT_MS, 'STAGE7_5_TIMEOUT_MS')
      : 45_000,
    username: env.STAGE7_5_USERNAME || '',
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    if (arg === '--help' || arg === '-h') {
      args.help = true;
      continue;
    }
    if (arg === '--mutating') {
      args.mutating = true;
      continue;
    }
    if (arg === '--no-mutating') {
      args.mutating = false;
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
    if (arg === '--exploration-session-id') {
      args.explorationSessionId = requiredOptionValue(argv, index, arg);
      index += 1;
      continue;
    }
    if (arg.startsWith('--exploration-session-id=')) {
      args.explorationSessionId = requiredInlineOptionValue(arg.slice('--exploration-session-id='.length), '--exploration-session-id');
      continue;
    }
    if (arg === '--combat-session-id') {
      args.combatSessionId = requiredOptionValue(argv, index, arg);
      index += 1;
      continue;
    }
    if (arg.startsWith('--combat-session-id=')) {
      args.combatSessionId = requiredInlineOptionValue(arg.slice('--combat-session-id='.length), '--combat-session-id');
      continue;
    }
    if (arg === '--combat-choice-text') {
      args.combatChoiceText = requiredOptionValue(argv, index, arg);
      index += 1;
      continue;
    }
    if (arg.startsWith('--combat-choice-text=')) {
      args.combatChoiceText = requiredInlineOptionValue(arg.slice('--combat-choice-text='.length), '--combat-choice-text');
      continue;
    }
    if (arg === '--claim-loot-id') {
      args.claimLootId = requiredOptionValue(argv, index, arg);
      index += 1;
      continue;
    }
    if (arg.startsWith('--claim-loot-id=')) {
      args.claimLootId = requiredInlineOptionValue(arg.slice('--claim-loot-id='.length), '--claim-loot-id');
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
  args.combatChoiceText = String(args.combatChoiceText || '').trim();
  args.claimLootId = String(args.claimLootId || '').trim();
  if (args.mutating && !args.combatSessionId) {
    args.combatSessionId = args.explorationSessionId;
  }
  return args;
}

export function usage() {
  return [
    'Usage:',
    '  node scripts/stage7_5_launch_experience_smoke.mjs --frontend-origin <origin> --username <user> --password <pass> --exploration-session-id <id> --combat-session-id <id> [--artifact-tag <tag>] [--output <json-file>]',
    '  node scripts/stage7_5_launch_experience_smoke.mjs --mutating --frontend-origin <origin> --username <user> --password <pass> --exploration-session-id <stage7_5-session-id> [--combat-choice-text <text>] [--claim-loot-id <loot-id>]',
    '',
    'Runs Stage 7.5 launch-experience QA against a public deployment.',
    'This smoke avoids story/combat mutations: it opens Adventure tools, verifies Combat readiness, and captures screenshots without claiming loot, attacking, or ending turns.',
    'With --mutating, it uses a resettable Stage 7.5 seed session to click the fixed exploration choice, resolve one deterministic attack/damage/end-turn sequence, and claim the Gate Token to party stash.',
    'Note: opening Journal may trigger the app\'s normal journal-generation request when the session has no generated journal text yet.',
    '',
    'Environment variables are also supported:',
    '  STAGE7_5_FRONTEND_ORIGIN, STAGE7_5_USERNAME, STAGE7_5_PASSWORD, STAGE7_5_EXPLORATION_SESSION_ID, STAGE7_5_COMBAT_SESSION_ID',
    '  STAGE7_5_MUTATING, STAGE7_5_COMBAT_CHOICE_TEXT, STAGE7_5_CLAIM_LOOT_ID',
  ].join('\n');
}

export function validateRequiredArgs(args) {
  const missing = [];
  if (!args.frontendOrigin) missing.push('--frontend-origin');
  if (!args.username) missing.push('--username');
  if (!args.password) missing.push('--password');
  if (!args.explorationSessionId) missing.push('--exploration-session-id');
  if (!args.combatSessionId && !args.mutating) missing.push('--combat-session-id');
  if (args.mutating && !args.combatChoiceText) missing.push('--combat-choice-text');
  if (args.mutating && !args.claimLootId) missing.push('--claim-loot-id');
  if (missing.length) {
    throw new Error(`Missing required Stage 7.5 smoke option(s): ${missing.join(', ')}.`);
  }
}

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function randomPort() {
  return 49000 + Math.floor(Math.random() * 6000);
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
      while (closeWaiters.length > 0) closeWaiters.shift()?.();
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
              try { ws.close(1000, 'stage7.5 smoke complete'); } catch { resolveClose(); }
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
    adventureDialoguePanel: Boolean(document.querySelector('.adventure-dialogue-panel')),
    adventureResponseBox: Boolean(document.querySelector('.dialogue-response-box')),
    adventureRecoveryButtons: document.querySelectorAll('.recovery-affordance').length,
    adventureFreeSpeak: Boolean(document.querySelector('#dialogue-free-speak-input') && document.querySelector('.free-speak-send')),
    adventureTopButtons: document.querySelectorAll('.adventure-topbar-button').length,
    adventureToolButtons: document.querySelectorAll('.adventure-tool-button').length,
    journalOpen: Boolean(document.querySelector('.journal-modal-head') || document.querySelector('[aria-label="冒险卷宗"]')),
    mapOpen: Boolean(document.querySelector('.location-map-head') || document.querySelector('[aria-label="Location map"]')),
    lootOpen: Boolean(document.querySelector('.loot-modal-head') || document.querySelector('[aria-label="Session loot"]')),
    combatLoaded: Boolean(document.querySelector('.combat-page-shell')),
    combatSkillButtons: document.querySelectorAll('.skill-bar [role="button"]').length,
    combatUnits: document.querySelectorAll('.iso-unit').length,
    combatEnemies: document.querySelectorAll('.iso-unit.enemy').length,
    combatEndTurnPresent: Boolean(document.querySelector('.end-turn-mega')),
    combatEndTurnDisabled: Boolean(document.querySelector('.end-turn-mega')?.disabled),
    combatLogPresent: Boolean(document.querySelector('.combat-log-panel')),
    combatLogItems: document.querySelectorAll('.combat-log [role="listitem"], .combat-log .log-entry').length,
    reactionPromptPresent: Boolean(document.querySelector('.reaction-prompt-layer, .legendary-action-prompt, .lair-action-prompt')),
    text: (document.body?.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 1200),
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

async function clickFirst(cdp, selectors) {
  const list = Array.isArray(selectors) ? selectors : [selectors];
  return evalPage(cdp, `(() => {
    const selectors = ${JSON.stringify(list)};
    for (const selector of selectors) {
      const element = document.querySelector(selector);
      if (element && !element.disabled) {
        element.click();
        return { ok: true, selector };
      }
    }
    return { ok: false, selectors };
  })()`);
}

async function clickChoiceByText(cdp, text) {
  return evalPage(cdp, `(() => {
    const expected = ${JSON.stringify(text)}.replace(/\\s+/g, ' ').trim();
    const buttons = Array.from(document.querySelectorAll('.choice-list button.choice, button.choice'));
    for (const button of buttons) {
      const label = (button.innerText || button.textContent || '').replace(/\\s+/g, ' ').trim();
      if (label.includes(expected) && !button.disabled) {
        button.click();
        return { ok: true, label };
      }
    }
    return {
      ok: false,
      expected,
      labels: buttons.map(button => (button.innerText || button.textContent || '').replace(/\\s+/g, ' ').trim()).slice(0, 8),
    };
  })()`);
}

async function closeTopOverlay(cdp) {
  return evalPage(cdp, `(() => {
    const panel = document.querySelector('.adventure-overlay-panel');
    if (!panel) return { ok: true, reason: 'no overlay' };
    const closeButton = panel.querySelector('button[aria-label*="Close"], button[aria-label*="关闭"], button[aria-label="关闭日志"], button[aria-label="关闭卷宗"]');
    if (closeButton) {
      closeButton.click();
      return { ok: true, reason: 'clicked close' };
    }
    return { ok: false, reason: 'close button missing' };
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

async function postApiJson(cdp, urlPath, payload = {}, timeoutMs = 30000) {
  return evalPage(cdp, `(() => fetch(${JSON.stringify(urlPath)}, {
    method: 'POST',
    headers: {
      accept: 'application/json',
      'content-type': 'application/json',
      authorization: localStorage.getItem('token') ? 'Bearer ' + localStorage.getItem('token') : '',
    },
    body: JSON.stringify(${JSON.stringify(payload)}),
  }).then(async (response) => {
    const text = await response.text();
    let body = null;
    try { body = text ? JSON.parse(text) : null; } catch { body = text; }
    return { ok: response.ok, status: response.status, body };
  }))()`, timeoutMs);
}

function combatTurnToken(combatBody = {}) {
  const turnOrder = Array.isArray(combatBody.turn_order) ? combatBody.turn_order : [];
  const turnIndex = Number(combatBody.current_turn_index || 0);
  const current = turnOrder[turnIndex] || {};
  const actorId = current.character_id || current.id || '';
  return `${combatBody.round_number || 1}:${turnIndex}:${actorId}`;
}

function combatCurrentActorId(combatBody = {}) {
  const turnOrder = Array.isArray(combatBody.turn_order) ? combatBody.turn_order : [];
  const turnIndex = Number(combatBody.current_turn_index || 0);
  const current = turnOrder[turnIndex] || {};
  return current.character_id || current.id || '';
}

function combatEntity(combatBody = {}, entityId = '') {
  return (combatBody.entities && combatBody.entities[entityId]) || null;
}

function firstLiveEnemy(combatBody = {}) {
  const entries = Object.entries(combatBody.entities || {})
    .filter(([, entity]) => entity?.is_enemy && Number(entity.hp_current || 0) > 0)
    .map(([id, entity]) => ({ id: entity.id || id, ...entity }));
  entries.sort((a, b) => Number(a.hp_current || 0) - Number(b.hp_current || 0));
  return entries[0] || null;
}

async function runMutatingCombatRound({
  cdp,
  sessionId,
  playerId,
  claimLootId,
  timeoutMs,
}) {
  const beforeCombatApi = await fetchApiJson(cdp, `/api/game/combat/${sessionId}`, timeoutMs);
  assert(beforeCombatApi.ok, `mutating combat API failed with HTTP ${beforeCombatApi.status}`);
  const beforeCombat = beforeCombatApi.body || {};
  const currentActorId = combatCurrentActorId(beforeCombat);
  assert(currentActorId === playerId, `mutating combat expected player turn ${playerId}, got ${currentActorId || 'none'}`);
  const target = firstLiveEnemy(beforeCombat);
  assert(target?.id, 'mutating combat could not find a live enemy target');
  const beforeTargetHp = Number(target.hp_current || 0);
  const attackTurnToken = combatTurnToken(beforeCombat);

  const attackApi = await postApiJson(
    cdp,
    `/api/game/combat/${sessionId}/attack-roll`,
    {
      entity_id: playerId,
      target_id: target.id,
      action_type: 'ranged',
      d20_value: 19,
      expected_turn_token: attackTurnToken,
    },
    timeoutMs,
  );
  assert(attackApi.ok, `mutating attack-roll failed with HTTP ${attackApi.status}: ${JSON.stringify(attackApi.body)}`);
  assert(attackApi.body?.hit === true, 'mutating attack-roll did not hit with fixed d20=19');
  assert(attackApi.body?.pending_attack_id, 'mutating attack-roll did not return pending_attack_id');

  const damageApi = await postApiJson(
    cdp,
    `/api/game/combat/${sessionId}/damage-roll`,
    {
      pending_attack_id: attackApi.body.pending_attack_id,
      damage_values: [4],
    },
    timeoutMs,
  );
  assert(damageApi.ok, `mutating damage-roll failed with HTTP ${damageApi.status}: ${JSON.stringify(damageApi.body)}`);

  const afterDamageCombatApi = await fetchApiJson(cdp, `/api/game/combat/${sessionId}`, timeoutMs);
  assert(afterDamageCombatApi.ok, `post-damage combat API failed with HTTP ${afterDamageCombatApi.status}`);
  const afterDamageTarget = combatEntity(afterDamageCombatApi.body || {}, target.id);
  const afterDamageTargetHp = Number(afterDamageTarget?.hp_current || 0);
  assert(
    afterDamageTargetHp < beforeTargetHp || afterDamageTarget?.life_state === 'dead',
    `mutating damage did not reduce target HP (${beforeTargetHp} -> ${afterDamageTargetHp})`,
  );

  const endTurnToken = combatTurnToken(afterDamageCombatApi.body || {});
  const endTurnApi = await postApiJson(
    cdp,
    `/api/game/combat/${sessionId}/end-turn`,
    { expected_turn_token: endTurnToken },
    timeoutMs,
  );
  assert(endTurnApi.ok, `mutating end-turn failed with HTTP ${endTurnApi.status}: ${JSON.stringify(endTurnApi.body)}`);

  const afterEndTurnCombatApi = await fetchApiJson(cdp, `/api/game/combat/${sessionId}`, timeoutMs);
  assert(afterEndTurnCombatApi.ok, `post-end-turn combat API failed with HTTP ${afterEndTurnCombatApi.status}`);
  const afterEndTurnToken = combatTurnToken(afterEndTurnCombatApi.body || {});
  assert(afterEndTurnToken !== endTurnToken, 'mutating end-turn did not advance the turn token');

  const lootClaimApi = await postApiJson(
    cdp,
    `/api/game/sessions/${sessionId}/loot/claim`,
    {
      character_id: playerId,
      loot_id: claimLootId,
      claim_mode: 'party_stash',
    },
    timeoutMs,
  );
  assert(lootClaimApi.ok, `mutating loot claim failed with HTTP ${lootClaimApi.status}: ${JSON.stringify(lootClaimApi.body)}`);

  const afterLootApi = await fetchApiJson(cdp, `/api/game/sessions/${sessionId}/loot`, timeoutMs);
  assert(afterLootApi.ok, `post-claim loot API failed with HTTP ${afterLootApi.status}`);
  const claimedLoot = (afterLootApi.body?.items || []).find(item => String(item.id) === String(claimLootId));
  assert(claimedLoot?.status === 'claimed', 'mutating loot claim did not persist claimed status');

  const afterSessionApi = await fetchApiJson(cdp, `/api/game/sessions/${sessionId}`, timeoutMs);
  assert(afterSessionApi.ok, `post-mutating session API failed with HTTP ${afterSessionApi.status}`);

  return {
    enabled: true,
    attack_roll_ok: attackApi.ok === true,
    damage_roll_ok: damageApi.ok === true,
    end_turn_ok: endTurnApi.ok === true,
    turn_advanced: afterEndTurnToken !== endTurnToken,
    loot_claim_ok: lootClaimApi.ok === true && claimedLoot?.status === 'claimed',
    target_id: target.id,
    target_name: target.name || target.id,
    before_target_hp: beforeTargetHp,
    after_damage_target_hp: afterDamageTargetHp,
    target_hp_reduced: afterDamageTargetHp < beforeTargetHp || afterDamageTarget?.life_state === 'dead',
    attack_total: attackApi.body?.attack_total,
    target_ac: attackApi.body?.target_ac,
    pending_attack_id: attackApi.body?.pending_attack_id,
    attack_turn_token: attackTurnToken,
    end_turn_token: endTurnToken,
    after_end_turn_token: afterEndTurnToken,
    loot_id: claimLootId,
    loot_claim_mode: lootClaimApi.body?.claimed?.claim_mode || 'party_stash',
    session_logs_count: Array.isArray(afterSessionApi.body?.logs) ? afterSessionApi.body.logs.length : 0,
  };
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

function buildChecks({
  combatApi = null,
  combatSessionApi = null,
  combatSkillBarApi = null,
  combatState = null,
  explorationLootApi = null,
  explorationSessionApi = null,
  explorationState = null,
  journalState = null,
  loginState = null,
  lootState = null,
  mapState = null,
  mutating = null,
} = {}) {
  const explorationBody = explorationSessionApi?.body || {};
  const explorationGameState = explorationBody.game_state || {};
  const combatSessionBody = combatSessionApi?.body || {};
  const combatBody = combatApi?.body || {};
  const combatSkillBarCount = Array.isArray(combatSkillBarApi?.body?.bar) ? combatSkillBarApi.body.bar.length : 0;
  const lootItems = Array.isArray(explorationLootApi?.body?.items) ? explorationLootApi.body.items.length : 0;
  const mutatingEnabled = mutating?.enabled === true;

  return {
    login_path: loginState?.path || '',
    login_token_present: loginState?.tokenPresent === true,
    exploration_session_api_ok: explorationSessionApi?.ok === true,
    exploration_session_combat_inactive: explorationBody.combat_active === false,
    exploration_player_present: Boolean(explorationBody.player?.id),
    exploration_current_scene_present: Boolean(explorationBody.current_scene || explorationGameState.current_scene),
    exploration_location_graph_present: Boolean(explorationGameState.location_graph),
    adventure_path: explorationState?.path || '',
    adventure_loaded: explorationState?.adventureLoaded === true,
    adventure_dialogue_panel_present: explorationState?.adventureDialoguePanel === true,
    adventure_response_box_present: explorationState?.adventureResponseBox === true,
    adventure_recovery_buttons_count: Number(explorationState?.adventureRecoveryButtons || 0),
    adventure_free_speak_present: explorationState?.adventureFreeSpeak === true,
    adventure_top_buttons_count: Number(explorationState?.adventureTopButtons || 0),
    adventure_tool_buttons_count: Number(explorationState?.adventureToolButtons || 0),
    journal_opened: journalState?.journalOpen === true,
    map_opened: mapState?.mapOpen === true,
    loot_opened: lootState?.lootOpen === true,
    exploration_loot_api_ok: explorationLootApi?.ok === true,
    exploration_loot_items_count: lootItems,
    combat_path: combatState?.path || '',
    combat_loaded: combatState?.combatLoaded === true,
    combat_session_api_ok: combatSessionApi?.ok === true,
    combat_player_present: Boolean(combatSessionBody.player?.id),
    combat_api_ok: combatApi?.ok === true,
    combat_session_active: combatSessionBody.combat_active === true
      || combatBody.combat_active === true
      || combatBody.active === true
      || Boolean(combatBody.entities),
    combat_round: Number(combatBody.round_number || combatBody.round || 0),
    combat_turn_order_count: Array.isArray(combatBody.turn_order) ? combatBody.turn_order.length : 0,
    combat_entities_count: combatBody.entities && typeof combatBody.entities === 'object'
      ? Object.keys(combatBody.entities).length
      : 0,
    combat_units_dom_count: Number(combatState?.combatUnits || 0),
    combat_enemy_dom_count: Number(combatState?.combatEnemies || 0),
    combat_skill_bar_api_ok: combatSkillBarApi?.ok === true,
    combat_skill_bar_count: combatSkillBarCount,
    combat_skill_bar_dom_count: Number(combatState?.combatSkillButtons || 0),
    combat_end_turn_present: combatState?.combatEndTurnPresent === true,
    combat_end_turn_disabled: combatState?.combatEndTurnDisabled === true,
    combat_log_present: combatState?.combatLogPresent === true,
    combat_log_items_count: Number(combatState?.combatLogItems || 0),
    combat_reaction_prompt_present: combatState?.reactionPromptPresent === true,
    mutating_enabled: mutatingEnabled,
    mutating_exploration_choice_clicked: mutatingEnabled ? mutating.exploration_choice_clicked === true : false,
    mutating_combat_handoff_ok: mutatingEnabled ? mutating.combat_handoff_ok === true : false,
    mutating_attack_roll_ok: mutatingEnabled ? mutating.attack_roll_ok === true : false,
    mutating_damage_roll_ok: mutatingEnabled ? mutating.damage_roll_ok === true : false,
    mutating_target_hp_reduced: mutatingEnabled ? mutating.target_hp_reduced === true : false,
    mutating_end_turn_ok: mutatingEnabled ? mutating.end_turn_ok === true : false,
    mutating_turn_advanced: mutatingEnabled ? mutating.turn_advanced === true : false,
    mutating_loot_claim_ok: mutatingEnabled ? mutating.loot_claim_ok === true : false,
    mutating_session_logs_count: mutatingEnabled ? Number(mutating.session_logs_count || 0) : 0,
  };
}

export function buildLaunchExperiencePayload({
  browserErrors = [],
  checks = {},
  createdAt = new Date().toISOString(),
  combatSessionId = '',
  explorationSessionId = '',
  frontendOrigin = '',
  mutating = null,
  screenshots = {},
  username = '',
} = {}) {
  const assertions = {
    login_ok: checks.login_token_present === true && checks.login_path !== '/login',
    exploration_adventure_ready: checks.exploration_session_api_ok === true
      && checks.exploration_session_combat_inactive === true
      && checks.exploration_player_present === true
      && checks.exploration_current_scene_present === true
      && checks.adventure_loaded === true
      && checks.adventure_dialogue_panel_present === true
      && checks.adventure_response_box_present === true
      && checks.adventure_recovery_buttons_count >= 3
      && checks.adventure_free_speak_present === true,
    exploration_tools_ready: checks.journal_opened === true
      && checks.map_opened === true
      && checks.loot_opened === true
      && checks.exploration_loot_api_ok === true,
    combat_ready: checks.combat_loaded === true
      && checks.combat_session_api_ok === true
      && checks.combat_player_present === true
      && checks.combat_api_ok === true
      && checks.combat_session_active === true
      && checks.combat_entities_count >= 2
      && checks.combat_units_dom_count >= 2,
    combat_controls_ready: checks.combat_skill_bar_api_ok === true
      && checks.combat_skill_bar_count > 0
      && checks.combat_skill_bar_dom_count > 0
      && checks.combat_end_turn_present === true
      && checks.combat_log_present === true,
    mutating_round_trip: checks.mutating_enabled !== true
      || (
        checks.mutating_exploration_choice_clicked === true
        && checks.mutating_combat_handoff_ok === true
        && checks.mutating_attack_roll_ok === true
        && checks.mutating_damage_roll_ok === true
        && checks.mutating_target_hp_reduced === true
        && checks.mutating_end_turn_ok === true
        && checks.mutating_turn_advanced === true
        && checks.mutating_loot_claim_ok === true
        && checks.mutating_session_logs_count > 0
      ),
    no_browser_errors: browserErrors.length === 0,
  };
  const ok = Object.values(assertions).every(Boolean);
  return {
    ok,
    mode: 'stage7.5-launch-experience-smoke',
    created_at: createdAt,
    frontend_origin: frontendOrigin,
    username,
    exploration_session_id: explorationSessionId,
    combat_session_id: combatSessionId,
    checks,
    assertions,
    browser: {
      errors: browserErrors,
    },
    mutating,
    screenshots,
    notes: mutating?.enabled
      ? [
          'Stage 7.5 mutating QA requires a freshly reset stage7-5 smoke seed.',
          'The mutating run clicks the fixed exploration choice, resolves one deterministic combat turn slice, and claims Gate Token to party stash.',
          'Opening Journal may trigger the app\'s normal journal-generation request when generated journal text is empty.',
        ]
      : [
          'Stage 7.5 public UI QA avoids advancing story, claiming loot, attacking, or ending turns.',
          'Opening Journal may trigger the app\'s normal journal-generation request when generated journal text is empty.',
          'Full mutating round-trip QA still requires a resettable smoke session or an explicit mutating run.',
        ],
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
  return path.join(root, 'artifacts', `stage7_5-launch-experience-${kind}-${artifactTag}.${extension}`);
}

export async function runCli(argv = process.argv.slice(2)) {
  const args = parseArgs(argv);
  if (args.help) {
    console.log(usage());
    return 0;
  }
  validateRequiredArgs(args);

  const outputPath = args.output || defaultArtifactPath('result', args.artifactTag, 'json');
  const explorationScreenshot = defaultArtifactPath('exploration', args.artifactTag, 'png');
  const journalScreenshot = defaultArtifactPath('journal', args.artifactTag, 'png');
  const mapScreenshot = defaultArtifactPath('map', args.artifactTag, 'png');
  const lootScreenshot = defaultArtifactPath('loot', args.artifactTag, 'png');
  const combatScreenshot = defaultArtifactPath('combat', args.artifactTag, 'png');
  const mutatingCombatScreenshot = defaultArtifactPath('combat-mutating', args.artifactTag, 'png');
  const debugPort = randomPort();
  const chromeDebug = { exit: null, stdout: '', stderr: '' };
  let chrome = null;
  let cdp = null;
  let payload = null;
  let profileDir = '';
  let loginState = null;
  let explorationState = null;
  let journalState = null;
  let mapState = null;
  let lootState = null;
  let combatState = null;
  let explorationSessionApi = null;
  let explorationLootApi = null;
  let combatSessionApi = null;
  let combatApi = null;
  let combatSkillBarApi = null;
  let mutatingResult = args.mutating ? { enabled: true } : null;
  let lastPageState = null;

  try {
    await mkdir(path.join(root, 'artifacts'), { recursive: true });
    profileDir = await mkdtemp(path.join(tmpdir(), 'codex-dnd-stage7-5-chrome-'));
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
    await waitFor('Stage 7.5 login form', async () => {
      const state = await readPageState(cdp);
      lastPageState = state;
      return state.loginFormVisible ? state : null;
    }, args.timeoutMs, 250);
    const submitted = await submitLogin(cdp, args.username, args.password);
    assert(submitted.ok, submitted.reason || 'login submit failed');
    loginState = await waitFor('Stage 7.5 login token', async () => {
      const state = await readPageState(cdp);
      lastPageState = state;
      return state.tokenPresent && state.path !== '/login' ? state : null;
    }, args.timeoutMs, 250);

    await navigate(cdp, `${args.frontendOrigin}/adventure/${args.explorationSessionId}?stage7_5Smoke=1`);
    explorationState = await waitFor('Stage 7.5 Adventure page', async () => {
      const state = await readPageState(cdp);
      lastPageState = state;
      return state.adventureLoaded ? state : null;
    }, args.timeoutMs, 250);
    explorationSessionApi = await fetchApiJson(cdp, `/api/game/sessions/${args.explorationSessionId}`, args.timeoutMs);
    assert(explorationSessionApi.ok, `exploration session API failed with HTTP ${explorationSessionApi.status}`);
    assert(explorationSessionApi.body?.combat_active === false, 'exploration smoke session must be combat_active=false');
    assert(explorationSessionApi.body?.player?.id, 'exploration session API did not include player.id');
    await screenshot(cdp, explorationScreenshot);

    const journalClicked = await clickFirst(cdp, [
      'button[aria-label="Open journal"]',
      '.adventure-tool-button[aria-label^="Journal"]',
    ]);
    assert(journalClicked.ok, 'journal button missing');
    journalState = await waitFor('Stage 7.5 Journal modal', async () => {
      const state = await readPageState(cdp);
      lastPageState = state;
      return state.journalOpen ? state : null;
    }, args.timeoutMs, 250);
    await screenshot(cdp, journalScreenshot);
    await closeTopOverlay(cdp);

    const mapClicked = await clickFirst(cdp, [
      '.adventure-tool-button[aria-label^="Map"]',
    ]);
    assert(mapClicked.ok, 'map button missing or disabled');
    mapState = await waitFor('Stage 7.5 Map modal', async () => {
      const state = await readPageState(cdp);
      lastPageState = state;
      return state.mapOpen ? state : null;
    }, args.timeoutMs, 250);
    await screenshot(cdp, mapScreenshot);
    await closeTopOverlay(cdp);

    const lootClicked = await clickFirst(cdp, [
      '.adventure-tool-button[aria-label^="Loot"]',
    ]);
    assert(lootClicked.ok, 'loot button missing');
    lootState = await waitFor('Stage 7.5 Loot modal', async () => {
      const state = await readPageState(cdp);
      lastPageState = state;
      return state.lootOpen ? state : null;
    }, args.timeoutMs, 250);
    explorationLootApi = await fetchApiJson(cdp, `/api/game/sessions/${args.explorationSessionId}/loot`, args.timeoutMs);
    assert(explorationLootApi.ok, `exploration loot API failed with HTTP ${explorationLootApi.status}`);
    await screenshot(cdp, lootScreenshot);
    await closeTopOverlay(cdp);

    if (args.mutating) {
      const choiceClicked = await clickChoiceByText(cdp, args.combatChoiceText);
      assert(choiceClicked.ok, `Stage 7.5 combat choice missing: ${JSON.stringify(choiceClicked)}`);
      mutatingResult = {
        ...mutatingResult,
        exploration_choice_clicked: true,
        combat_choice_text: args.combatChoiceText,
        combat_choice_label: choiceClicked.label,
      };
      await waitFor('Stage 7.5 mutating Adventure-to-Combat handoff', async () => {
        const state = await readPageState(cdp);
        lastPageState = state;
        return state.path === `/combat/${args.combatSessionId}` && state.combatLoaded ? state : null;
      }, args.timeoutMs, 250);
      mutatingResult.combat_handoff_ok = true;
    } else {
      await navigate(cdp, `${args.frontendOrigin}/adventure/${args.combatSessionId}?stage7_5Smoke=1`);
      await waitFor('Stage 7.5 Adventure-to-Combat handoff', async () => {
        const state = await readPageState(cdp);
        lastPageState = state;
        return state.path === `/combat/${args.combatSessionId}` && state.combatLoaded ? state : null;
      }, args.timeoutMs, 250);
    }

    await navigate(cdp, `${args.frontendOrigin}/combat/${args.combatSessionId}?stage7_5Smoke=1`);
    combatState = await waitFor('Stage 7.5 Combat page', async () => {
      const state = await readPageState(cdp);
      lastPageState = state;
      return state.combatLoaded ? state : null;
    }, args.timeoutMs, 250);
    combatSessionApi = await fetchApiJson(cdp, `/api/game/sessions/${args.combatSessionId}`, args.timeoutMs);
    assert(combatSessionApi.ok, `combat session API failed with HTTP ${combatSessionApi.status}`);
    assert(combatSessionApi.body?.combat_active === true, 'combat smoke session must be combat_active=true');
    assert(combatSessionApi.body?.player?.id, 'combat session API did not include player.id');
    combatApi = await fetchApiJson(cdp, `/api/game/combat/${args.combatSessionId}`, args.timeoutMs);
    assert(combatApi.ok, `combat API failed with HTTP ${combatApi.status}`);
    const playerId = combatSessionApi.body?.player?.id
      || combatApi.body?.player_id
      || Object.entries(combatApi.body?.entities || {}).find(([, entity]) => entity?.is_player)?.[0]
      || '';
    assert(playerId, 'combat smoke could not resolve player entity id');
    combatSkillBarApi = await fetchApiJson(
      cdp,
      `/api/game/combat/${args.combatSessionId}/skill-bar?entity_id=${encodeURIComponent(playerId)}`,
      args.timeoutMs,
    );
    assert(combatSkillBarApi.ok, `combat skill-bar API failed with HTTP ${combatSkillBarApi.status}`);
    await screenshot(cdp, combatScreenshot);

    if (args.mutating) {
      mutatingResult = {
        ...mutatingResult,
        ...(await runMutatingCombatRound({
          cdp,
          sessionId: args.combatSessionId,
          playerId,
          claimLootId: args.claimLootId,
          timeoutMs: args.timeoutMs,
        })),
      };
      await navigate(cdp, `${args.frontendOrigin}/combat/${args.combatSessionId}?stage7_5Smoke=1&mutating=1`);
      combatState = await waitFor('Stage 7.5 post-mutating Combat page', async () => {
        const state = await readPageState(cdp);
        lastPageState = state;
        return state.combatLoaded ? state : null;
      }, args.timeoutMs, 250);
      combatSessionApi = await fetchApiJson(cdp, `/api/game/sessions/${args.combatSessionId}`, args.timeoutMs);
      combatApi = await fetchApiJson(cdp, `/api/game/combat/${args.combatSessionId}`, args.timeoutMs);
      combatSkillBarApi = await fetchApiJson(
        cdp,
        `/api/game/combat/${args.combatSessionId}/skill-bar?entity_id=${encodeURIComponent(playerId)}`,
        args.timeoutMs,
      );
      await screenshot(cdp, mutatingCombatScreenshot);
    }

    payload = buildLaunchExperiencePayload({
      browserErrors: collectBlockingBrowserEvents(cdp.events),
      checks: buildChecks({
        combatApi,
        combatSessionApi,
        combatSkillBarApi,
        combatState,
        explorationLootApi,
        explorationSessionApi,
        explorationState,
        journalState,
        loginState,
        lootState,
        mapState,
        mutating: mutatingResult,
      }),
      combatSessionId: args.combatSessionId,
      explorationSessionId: args.explorationSessionId,
      frontendOrigin: args.frontendOrigin,
      mutating: mutatingResult,
      screenshots: {
        exploration: explorationScreenshot,
        journal: journalScreenshot,
        map: mapScreenshot,
        loot: lootScreenshot,
        combat: combatScreenshot,
        ...(args.mutating ? { combat_mutating: mutatingCombatScreenshot } : {}),
      },
      username: args.username,
    });
  } catch (error) {
    let failureState = lastPageState;
    if (cdp) {
      failureState = await readPageState(cdp).catch(() => failureState);
      await screenshot(cdp, defaultArtifactPath('failure', args.artifactTag, 'png')).catch(() => {});
    }
    const checks = buildChecks({
      combatApi,
      combatSessionApi,
      combatSkillBarApi,
      combatState,
      explorationLootApi,
      explorationSessionApi,
      explorationState,
      journalState,
      loginState,
      lootState,
      mapState,
      mutating: mutatingResult,
    });
    if (failureState) {
      checks.failure_path = failureState.path;
      checks.failure_token_present = failureState.tokenPresent === true;
      checks.failure_login_form_visible = failureState.loginFormVisible === true;
      checks.failure_text = failureState.text || '';
    }
    payload = buildLaunchExperiencePayload({
      browserErrors: [
        ...collectBlockingBrowserEvents(cdp?.events || []),
        { method: 'Smoke.failure', message: error.message || String(error) },
      ],
      checks,
      combatSessionId: args.combatSessionId,
      explorationSessionId: args.explorationSessionId,
      frontendOrigin: args.frontendOrigin,
      mutating: mutatingResult,
      screenshots: {
        exploration: explorationScreenshot,
        journal: journalScreenshot,
        map: mapScreenshot,
        loot: lootScreenshot,
        combat: combatScreenshot,
        ...(args.mutating ? { combat_mutating: mutatingCombatScreenshot } : {}),
        failure: defaultArtifactPath('failure', args.artifactTag, 'png'),
      },
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

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  runCli()
    .then(code => {
      process.exitCode = code;
    })
    .catch(error => {
      console.error(error.message || error);
      process.exitCode = 1;
    });
}
