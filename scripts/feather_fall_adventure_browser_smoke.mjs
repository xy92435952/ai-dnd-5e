import { spawn, spawnSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import { mkdir, mkdtemp, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(scriptDir, '..');
const backendCwd = path.join(root, 'backend');
const frontendCwd = path.join(root, 'frontend');
const backendOrigin = process.env.BACKEND_ORIGIN || 'http://127.0.0.1:8002';
const frontendOrigin = process.env.FRONTEND_ORIGIN || 'http://127.0.0.1:3000';
const pythonPath = resolvePythonPath();
const decision = normalizeDecision(process.env.FEATHER_FALL_SMOKE_DECISION || parseDecisionArg() || 'accept');
const reactionType = decision === 'decline' ? 'decline' : 'feather_fall';
const decisionButtonText = decision === 'decline' ? 'Decline' : 'Cast Feather Fall';
const slug = process.env.FEATHER_FALL_SMOKE_SLUG || `stage7_feather_fall_browser_${decision}`;
const artifactTag = normalizeArtifactTag(process.env.FEATHER_FALL_SMOKE_ARTIFACT_TAG || parseArgValue('--artifact-tag') || todayTag());
const promptScreenshotPath = screenshotPath('prompt');
const resolvedScreenshotPath = screenshotPath('resolved');
const manifestPath = artifactPath('manifest', 'json');

function sleep(ms) {
  return new Promise(resolve => setTimeout(resolve, ms));
}

function assert(condition, message) {
  if (!condition) throw new Error(message);
}

function parseDecisionArg(args = process.argv.slice(2)) {
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === '--decision') return args[index + 1] || '';
    if (arg.startsWith('--decision=')) return arg.slice('--decision='.length);
    if (['accept', 'cast', 'feather_fall', 'feather-fall', 'decline', 'pass'].includes(arg)) {
      return arg;
    }
  }
  return '';
}

function parseArgValue(name, args = process.argv.slice(2)) {
  for (let index = 0; index < args.length; index += 1) {
    const arg = args[index];
    if (arg === name) return args[index + 1] || '';
    if (arg.startsWith(`${name}=`)) return arg.slice(name.length + 1);
  }
  return '';
}

function normalizeDecision(value) {
  const normalized = String(value || '').trim().toLowerCase().replace(/-/g, '_');
  if (['accept', 'cast', 'feather_fall'].includes(normalized)) return 'accept';
  if (['decline', 'pass'].includes(normalized)) return 'decline';
  throw new Error(`Unsupported Feather Fall smoke decision "${value}". Use accept or decline.`);
}

function todayTag() {
  const now = new Date();
  return [
    String(now.getFullYear()),
    String(now.getMonth() + 1).padStart(2, '0'),
    String(now.getDate()).padStart(2, '0'),
  ].join('');
}

function normalizeArtifactTag(value) {
  const tag = String(value || '').trim();
  if (!/^[A-Za-z0-9_.-]+$/.test(tag)) {
    throw new Error(`Unsupported artifact tag "${value}". Use only letters, numbers, dot, underscore, or dash.`);
  }
  return tag;
}

function commandExists(command) {
  const checker = process.platform === 'win32' ? 'where' : 'command';
  const args = process.platform === 'win32' ? [command] : ['-v', command];
  const result = spawnSync(checker, args, { stdio: 'ignore', shell: process.platform !== 'win32' });
  return result.status === 0;
}

function resolvePythonPath() {
  const explicit = process.env.PYTHON_EXE;
  if (explicit) return explicit;

  const pathCandidates = [
    path.join(root, '.codex-test-artifacts', 'backend-venv', 'Scripts', 'python.exe'),
    path.join(root, 'backend', '.venv-codex', 'Scripts', 'python.exe'),
    path.join(root, 'backend', '.venv-codex', 'bin', 'python'),
  ];
  const foundPath = pathCandidates.find(candidate => existsSync(candidate));
  if (foundPath) return foundPath;

  const commandCandidates = process.platform === 'win32' ? ['python.exe', 'python'] : ['python3', 'python'];
  const foundCommand = commandCandidates.find(commandExists);
  if (foundCommand) return foundCommand;

  throw new Error(
    `No Python executable found. Set PYTHON_EXE or create one of: ${pathCandidates.join(', ')}`,
  );
}

function screenshotPath(kind) {
  return artifactPath(kind, 'png');
}

function artifactPath(kind, extension) {
  if (decision === 'accept') {
    const suffix = kind === 'prompt' || kind === 'resolved' ? kind : `${kind}`;
    return path.join(root, 'artifacts', `browser-feather-fall-adventure-${suffix}-${artifactTag}.${extension}`);
  }
  return path.join(root, 'artifacts', `browser-feather-fall-adventure-${decision}-${kind}-${artifactTag}.${extension}`);
}

function sqliteUrl(dbPath) {
  return `sqlite+aiosqlite:///${dbPath.replace(/\\/g, '/')}`;
}

function browserPath() {
  const candidates = [
    process.env.FEATHER_FALL_SMOKE_BROWSER_PATH,
    process.env.CHROME_PATH,
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

function pipeLogs(proc, label) {
  proc.stdout?.on('data', chunk => process.stdout.write(`[${label}] ${chunk}`));
  proc.stderr?.on('data', chunk => process.stderr.write(`[${label}] ${chunk}`));
}

function randomPort() {
  return 47000 + Math.floor(Math.random() * 8000);
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

async function urlReady(url) {
  try {
    const response = await fetch(url);
    return response.ok;
  } catch {
    return false;
  }
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

async function waitForUrl(label, url, proc = null) {
  return waitFor(label, async () => {
    if (proc && proc.exitCode !== null) {
      throw new Error(`${label} exited early with code ${proc.exitCode}`);
    }
    return (await urlReady(url)) ? true : null;
  }, 45000, 500);
}

async function stopProcess(proc) {
  if (!proc) return;
  const closeStdio = () => {
    proc.removeAllListeners();
    proc.stdout?.removeAllListeners();
    proc.stderr?.removeAllListeners();
    proc.stdout?.destroy();
    proc.stderr?.destroy();
    proc.stdin?.destroy();
    proc.unref?.();
  };
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
  if (proc.exitCode === null && process.platform !== 'win32') {
    proc.kill('SIGKILL');
    await waitForClose(2000);
  }
  closeStdio();
}

function runSeed(env) {
  const seeded = spawnSync(
    pythonPath,
    ['seed_smoke_scenario.py', '--slug', slug, '--variant', 'feather-fall'],
    {
      cwd: backendCwd,
      env,
      encoding: 'utf8',
    },
  );
  if (seeded.status !== 0) {
    throw new Error(`seed_smoke_scenario failed:\nstdout:\n${seeded.stdout}\nstderr:\n${seeded.stderr}`);
  }
  try {
    return JSON.parse(seeded.stdout);
  } catch (error) {
    throw new Error(`Could not parse seed output: ${error.message}\n${seeded.stdout}`);
  }
}

async function login(seed) {
  return httpJson(`${backendOrigin}/auth/login`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      username: seed.username,
      password: seed.password,
    }),
  });
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
              try { ws.close(1000, 'smoke complete'); } catch { resolveClose(); }
            }),
            sleep(timeoutMs),
          ]);
        },
        events,
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
              if (events.length > 80) events.shift();
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
          if (events.length > 80) events.shift();
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

async function readUiState(cdp) {
  return evalPage(cdp, `(() => {
    const textFromIds = (value) => (value || '')
      .split(/\\s+/)
      .map((id) => {
        const node = document.getElementById(id);
        return node?.innerText || node?.textContent || '';
      })
      .join(' ')
      .replace(/\\s+/g, ' ')
      .trim();
    const dialog = Array.from(document.querySelectorAll('[role="dialog"].exploration-reaction-prompt'))
      .find((candidate) => textFromIds(candidate.getAttribute('aria-labelledby')).includes('Feather Fall')) || null;
    const dialogName = dialog ? textFromIds(dialog.getAttribute('aria-labelledby')) : '';
    const dialogDescription = dialog ? textFromIds(dialog.getAttribute('aria-describedby')) : '';
    const buttons = Array.from(document.querySelectorAll('button')).map((button) => ({
      text: (button.innerText || '').replace(/\\s+/g, ' ').trim(),
      disabled: button.disabled,
      className: button.className || '',
    }));
    return {
      path: window.location.pathname,
      text: document.body?.innerText || '',
      dialogVisible: Boolean(dialog),
      dialogName,
      dialogDescription,
      dialogText: dialog ? (dialog.innerText || '').replace(/\\s+/g, ' ').trim() : '',
      buttons,
      castButtonVisible: buttons.some(button => button.text.includes('Cast Feather Fall')),
      declineButtonVisible: buttons.some(button => button.text.includes('Decline')),
    };
  })()`);
}

async function clickPromptButton(cdp, buttonText) {
  return evalPage(cdp, `(() => {
    const expected = ${JSON.stringify(buttonText)};
    const button = Array.from(document.querySelectorAll('button'))
      .find((candidate) => (candidate.innerText || '').includes(expected));
    if (!button) return { ok: false, text: document.body?.innerText || '' };
    button.click();
    return { ok: true, text: (button.innerText || '').replace(/\\s+/g, ' ').trim() };
  })()`);
}

async function assertResolvedSession(seed, token, beforeSession) {
  const after = await httpJson(`${backendOrigin}/game/sessions/${seed.session_id}`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  assert(!after.game_state?.pending_exploration_reaction, 'pending_exploration_reaction survived refresh');
  const beforeHp = Number(beforeSession.player?.hp_current ?? beforeSession.player?.hp_max ?? 0);
  const pending = beforeSession.game_state?.pending_exploration_reaction || {};
  const fallDamage = Number(pending.damage_before ?? pending.damage_prevented ?? 0);
  const expectedHp = decision === 'decline' ? Math.max(0, beforeHp - fallDamage) : beforeHp;
  assert(after.player?.hp_current === expectedHp, `player HP mismatch for ${decision}: ${after.player?.hp_current} vs ${expectedHp}`);
  const companion = (after.companions || []).find(item => item.id === seed.companion_ids[0]);
  assert(companion, `missing seeded Feather Fall caster ${seed.companion_ids[0]}`);
  const beforeCompanion = (beforeSession.companions || []).find(item => item.id === seed.companion_ids[0]);
  const expectedSlots = decision === 'decline' ? beforeCompanion?.spell_slots?.['1st'] : 0;
  assert(companion.spell_slots?.['1st'] === expectedSlots, `Feather Fall slot mismatch for ${decision}: ${JSON.stringify(companion.spell_slots)}`);
  const logText = JSON.stringify(after.logs || []);
  if (decision === 'decline') {
    assert(
      logText.includes('lets the Feather Fall window pass') && logText.includes(`deals ${fallDamage} damage`),
      'session logs did not include declined Feather Fall narration',
    );
  } else {
    assert(logText.includes('Feather Fall') && logText.includes(`preventing ${fallDamage} fall damage`), 'session logs did not include resolved Feather Fall narration');
  }
  return after;
}

function buildResolvedSummary(seed, beforeSession, afterSession) {
  const beforeHp = Number(beforeSession.player?.hp_current ?? beforeSession.player?.hp_max ?? 0);
  const pending = beforeSession.game_state?.pending_exploration_reaction || {};
  const fallDamage = Number(pending.damage_before ?? pending.damage_prevented ?? 0);
  const expectedHp = decision === 'decline' ? Math.max(0, beforeHp - fallDamage) : beforeHp;
  const afterCompanion = (afterSession.companions || []).find(item => item.id === seed.companion_ids[0]);
  const beforeCompanion = (beforeSession.companions || []).find(item => item.id === seed.companion_ids[0]);
  const expectedCasterFirstSlots = decision === 'decline' ? beforeCompanion?.spell_slots?.['1st'] : 0;
  const actualCasterFirstSlots = afterCompanion?.spell_slots?.['1st'];

  return {
    pending_cleared: !afterSession.game_state?.pending_exploration_reaction,
    fall_damage: fallDamage,
    before_hp: beforeHp,
    expected_hp: expectedHp,
    actual_hp: afterSession.player?.hp_current,
    hp_max: afterSession.player?.hp_max,
    expected_caster_1st_slots: expectedCasterFirstSlots,
    actual_caster_1st_slots: actualCasterFirstSlots,
  };
}

async function main() {
  const tempDir = await mkdtemp(path.join(tmpdir(), 'codex-dnd-feather-fall-smoke-'));
  const profileDir = await mkdtemp(path.join(tmpdir(), 'codex-dnd-feather-fall-chrome-'));
  const dbPath = path.join(tempDir, 'feather_fall_smoke.db');
  const tempEnv = {
    ...process.env,
    DATABASE_URL: sqliteUrl(dbPath),
    LANGGRAPH_DB_PATH: path.join(tempDir, 'langgraph_memory.db'),
    CHROMADB_PATH: path.join(tempDir, 'chromadb_data'),
    UPLOAD_DIR: path.join(tempDir, 'uploads'),
  };
  let backend = null;
  let frontend = null;
  let cdp = null;
  let chrome = null;
  let lastUiState = null;
  const chromeDebug = { exit: null, stdout: '', stderr: '' };

  try {
    if (await urlReady(`${backendOrigin}/health`)) {
      throw new Error(
        `${backendOrigin} is already serving a backend. Stop it before running this temp-DB smoke, `
        + 'or run the HTTP-only seed regression instead.',
      );
    }

    backend = spawn(pythonPath, ['-m', 'uvicorn', 'main:app', '--host', '127.0.0.1', '--port', '8002'], {
      cwd: backendCwd,
      env: tempEnv,
      stdio: ['ignore', 'pipe', 'pipe'],
      windowsHide: true,
    });
    pipeLogs(backend, 'backend');
    await waitForUrl('backend', `${backendOrigin}/health`, backend);

    const seed = runSeed(tempEnv);
    const auth = await login(seed);
    const before = await httpJson(`${backendOrigin}/game/sessions/${seed.session_id}`, {
      headers: { Authorization: `Bearer ${auth.token}` },
    });
    assert(before.combat_active === false, 'seeded Feather Fall session should restore in Adventure, not Combat');
    assert(before.game_state?.pending_exploration_reaction, 'seed did not expose pending_exploration_reaction over HTTP');

    if (!(await urlReady(frontendOrigin))) {
      const frontendCommand = process.platform === 'win32' ? 'cmd.exe' : 'npm';
      const frontendArgs = process.platform === 'win32'
        ? ['/d', '/s', '/c', 'npm.cmd run dev -- --host 127.0.0.1 --port 3000']
        : ['run', 'dev', '--', '--host', '127.0.0.1', '--port', '3000'];
      frontend = spawn(frontendCommand, frontendArgs, {
        cwd: frontendCwd,
        stdio: ['ignore', 'pipe', 'pipe'],
        windowsHide: true,
      });
      pipeLogs(frontend, 'frontend');
    }
    await waitForUrl('frontend', frontendOrigin, frontend);

    const debugPort = randomPort();
    chrome = spawn(browserPath(), [
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
      `${frontendOrigin}/login`,
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

    cdp = await connectBrowserPageCdp(debugPort, `${frontendOrigin}/login`, () => chromeDebug)
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

    await navigate(cdp, `${frontendOrigin}/login`);
    await evalPage(cdp, `(() => {
      localStorage.setItem('token', ${JSON.stringify(auth.token)});
      localStorage.setItem('user', ${JSON.stringify(JSON.stringify({
        user_id: auth.user_id,
        username: auth.username,
        display_name: auth.display_name || auth.username,
      }))});
      window.dispatchEvent(new Event('user-changed'));
      return true;
    })()`);

    await navigate(cdp, `${frontendOrigin}/adventure/${seed.session_id}?featherFallSmoke=1`);
    const promptState = await waitFor('Feather Fall exploration prompt UI', async () => {
      const state = await readUiState(cdp);
      lastUiState = state;
      return state.dialogVisible
        && state.dialogName.includes('Feather Fall')
        && state.dialogText.includes('Mara Quickstep')
        && state.dialogText.includes('Smoke Sentinel')
        && state.dialogText.includes('Gatehouse drop shaft')
        && state.dialogDescription.includes('Prevents 6 fall damage')
        && state.castButtonVisible
        && state.declineButtonVisible
        ? state
        : null;
    }, 45000, 250);
    await screenshot(cdp, promptScreenshotPath);

    const clicked = await clickPromptButton(cdp, decisionButtonText);
    assert(clicked.ok, `Could not click ${decisionButtonText}: ${JSON.stringify(clicked)}`);

    const resolvedUi = await waitFor('Feather Fall prompt clears after decision', async () => {
      const state = await readUiState(cdp);
      lastUiState = state;
      return !state.dialogVisible
        && state.text.includes('Feather Fall')
        ? state
        : null;
    }, 30000, 250);
    await screenshot(cdp, resolvedScreenshotPath);

    const after = await assertResolvedSession(seed, auth.token, before);
    const result = {
      ok: true,
      mode: 'feather-fall-adventure-browser-smoke',
      created_at: new Date().toISOString(),
      decision,
      reaction_type: reactionType,
      artifact_tag: artifactTag,
      seed: {
        slug: seed.slug,
        session_id: seed.session_id,
        character_id: seed.character_id,
        companion_id: seed.companion_ids[0],
      },
      prompt: {
        dialogName: promptState.dialogName,
        dialogDescription: promptState.dialogDescription,
        dialogText: promptState.dialogText,
        buttons: promptState.buttons,
      },
      resolved: {
        path: resolvedUi.path,
        hp_current: after.player.hp_current,
        hp_max: after.player.hp_max,
        caster_slots: (after.companions || []).find(item => item.id === seed.companion_ids[0])?.spell_slots,
        pending_cleared: !after.game_state?.pending_exploration_reaction,
      },
      assertions: buildResolvedSummary(seed, before, after),
      screenshots: {
        prompt: promptScreenshotPath,
        resolved: resolvedScreenshotPath,
      },
      manifest: manifestPath,
    };
    await writeJsonArtifact(manifestPath, result);
    console.log(JSON.stringify(result, null, 2));
  } catch (error) {
    throw new Error(`${error.message}\nLast UI state:\n${JSON.stringify(lastUiState, null, 2)}\nRecent browser events:\n${JSON.stringify(cdp?.events?.slice(-20) || [], null, 2)}`);
  } finally {
    await cdp?.close?.().catch(() => {});
    await stopProcess(chrome);
    await stopProcess(frontend);
    await stopProcess(backend);
    await rm(profileDir, { recursive: true, force: true }).catch(() => {});
    await rm(tempDir, { recursive: true, force: true }).catch(() => {});
  }
}

main().catch(error => {
  console.error(error.stack || error.message || String(error));
  process.exitCode = 1;
});
