#!/usr/bin/env node
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

import { STAGE8_PUBLIC_EVIDENCE_ASSERTIONS } from './stage8_public_evidence_smoke.mjs';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(scriptDir, '..');

export const STAGE8_REQUIRED_CI_JOBS = ['backend', 'frontend', 'frontend-prod-build'];

export const STAGE8_DEPLOYMENT_WS_PROXY_FILES = [
  {
    file: 'deploy.sh',
    proxyPass: 'http://127.0.0.1:8000/ws/',
  },
  {
    file: 'update_server.sh',
    proxyPass: 'http://127.0.0.1:8000/ws/',
  },
  {
    file: 'frontend/nginx.conf',
    proxyPass: 'http://backend:8000/ws/',
  },
];

export const STAGE8_SUITES = [
  {
    id: 'account-module-character',
    requiredPaths: [
      'backend/tests/integration/test_health_and_routes.py',
      'backend/tests/integration/test_inventory_endpoints.py',
      'backend/tests/integration/test_character_progression_endpoints.py',
      'backend/tests/integration/test_character_leveling_progression_endpoints.py',
      'backend/tests/unit/test_character_creation_service.py',
      'frontend/src/pages/__tests__/Home.responsive.test.jsx',
      'frontend/src/pages/__tests__/CharacterCreate.smoke.test.jsx',
      'frontend/src/pages/__tests__/CharacterSheet.inventory.test.jsx',
    ],
    evidenceRequirements: [
      {
        id: 'deployed-login',
        label: 'deployed login/register sanity',
      },
      {
        id: 'fresh-character-create',
        label: 'fresh character-create path',
        verifierAssertion: STAGE8_PUBLIC_EVIDENCE_ASSERTIONS['fresh-character-create'],
        verifierType: 'stage8-public-evidence-smoke',
      },
    ],
  },
  {
    id: 'adventure',
    requiredPaths: [
      'backend/tests/integration/test_game_flow.py',
      'backend/tests/integration/test_full_game_flow.py',
      'backend/tests/integration/test_state_restoration.py',
      'backend/tests/integration/test_smoke_seed_feather_fall.py',
      'frontend/src/pages/__tests__/Adventure.smoke.test.jsx',
      'frontend/src/components/adventure/__tests__/DialogueChoices.test.jsx',
      'frontend/src/components/adventure/__tests__/JournalModal.test.jsx',
      'frontend/src/components/adventure/__tests__/LocationMapModal.test.jsx',
      'frontend/src/components/adventure/__tests__/LootModal.test.jsx',
    ],
    evidenceRequirements: [
      {
        id: 'exploration-tools',
        label: 'public Adventure screenshot plus Journal/Map/Loot from one session',
      },
      {
        id: 'skill-check-path',
        label: 'skill-check click path or documented replacement',
      },
    ],
  },
  {
    id: 'combat',
    requiredPaths: [
      'backend/tests/integration/test_combat_endpoints.py',
      'backend/tests/integration/test_combat_rules_endpoints.py',
      'backend/tests/integration/test_stage7_5_smoke_seed.py',
      'backend/tests/unit/test_combat_attack_prepare_service.py',
      'backend/tests/unit/test_combat_spell_effects.py',
      'backend/tests/unit/test_combat_reaction_service.py',
      'backend/tests/unit/test_combat_condition_duration_service.py',
      'frontend/src/pages/__tests__/Combat.smoke.test.jsx',
      'frontend/src/components/combat/__tests__/CombatHudSkillBar.test.jsx',
      'frontend/src/components/combat/__tests__/CombatHudCombatLog.test.jsx',
      'frontend/src/components/combat/__tests__/SpellModal.test.jsx',
      'frontend/src/components/combat/__tests__/ReactionPrompt.test.jsx',
    ],
    evidenceRequirements: [
      {
        id: 'stage7.5-mutating-smoke',
        label: 'Stage 7.5 mutating launch smoke artifact',
        verifierType: 'stage7.5-launch-smoke',
      },
      {
        id: 'combat-log-reload',
        label: 'persisted combat log after reload',
      },
    ],
  },
  {
    id: 'loot-economy',
    requiredPaths: [
      'backend/tests/integration/test_session_loot_endpoints.py',
      'backend/tests/integration/test_inventory_endpoints.py',
      'backend/tests/unit/test_context_builder_snapshots.py',
      'frontend/src/components/adventure/__tests__/LootModal.test.jsx',
      'frontend/src/pages/__tests__/CharacterSheet.inventory.test.jsx',
    ],
    evidenceRequirements: [
      {
        id: 'party-stash-claim',
        label: 'party-stash claim',
      },
      {
        id: 'gold-or-shop-economy',
        label: 'gold split or shop buy/sell smoke',
        verifierAssertion: STAGE8_PUBLIC_EVIDENCE_ASSERTIONS['gold-or-shop-economy'],
        verifierType: 'stage8-public-evidence-smoke',
      },
    ],
  },
  {
    id: 'multiplayer',
    requiredPaths: [
      'backend/tests/integration/test_multiplayer_flow.py',
      'backend/tests/integration/test_multiplayer_happy_path.py',
      'backend/tests/integration/test_multiplayer_ws_realtime.py',
      'backend/tests/unit/test_room_multiplayer_state.py',
      'backend/tests/unit/test_ws_cleanup_service.py',
      'frontend/src/pages/__tests__/RoomLobby.smoke.test.jsx',
      'frontend/src/components/room/__tests__/RoomMultiplayerStatusPanel.test.jsx',
      'frontend/src/components/adventure/__tests__/MultiplayerSpeakBar.test.jsx',
      'frontend/src/components/combat/__tests__/MultiplayerTurnBar.test.jsx',
    ],
    evidenceRequirements: [
      {
        id: 'two-browser-room-join',
        label: 'two-browser room join',
        verifierAssertion: STAGE8_PUBLIC_EVIDENCE_ASSERTIONS['two-browser-room-join'],
        verifierType: 'stage8-public-evidence-smoke',
      },
      {
        id: 'speak-turn-handoff',
        label: 'speak-turn handoff',
        verifierAssertion: STAGE8_PUBLIC_EVIDENCE_ASSERTIONS['speak-turn-handoff'],
        verifierType: 'stage8-public-evidence-smoke',
      },
      {
        id: 'combat-sync-or-blocker',
        label: 'combat refresh/sync or documented blocker',
        verifierAssertion: STAGE8_PUBLIC_EVIDENCE_ASSERTIONS['combat-sync-or-blocker'],
        verifierType: 'stage8-public-evidence-smoke',
      },
    ],
  },
  {
    id: 'production-parity',
    requiredPaths: [
      'scripts/check.sh',
      'scripts/stage7_reaction_backend_gate.sh',
      'scripts/verify_stage7_evidence.mjs',
      'scripts/stage7_5_launch_experience_smoke.mjs',
      'scripts/stage8_comprehensive_gate.mjs',
      'scripts/stage8_public_evidence_smoke.mjs',
      'deploy.sh',
      'update_server.sh',
      'frontend/nginx.conf',
      'backend/tests/unit/test_smoke_scenario_seed.py',
      'frontend/src/__tests__/stage7EvidenceVerifier.test.js',
      'frontend/src/__tests__/stage7_5LaunchExperienceSmoke.test.js',
      'frontend/src/__tests__/stage8ComprehensiveGate.test.js',
    ],
    evidenceRequirements: [
      {
        id: 'github-actions-green',
        label: 'latest required GitHub Actions jobs are green',
      },
      {
        id: 'postdeploy-healthcheck',
        label: 'public /api/health post-deploy healthcheck',
        verifierType: 'postdeploy-healthcheck',
      },
      {
        id: 'postgres-seed-reset',
        label: 'PostgreSQL seed/reset result',
      },
    ],
  },
];

const PASS_VALUES = new Set(['pass', 'passed', 'ok', 'success', 'verified']);
const BLOCKED_VALUES = new Set(['blocked', 'blocker']);

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
    allowBlockers: false,
    evidenceManifest: '',
    evidenceNoFileCheck: false,
    format: 'markdown',
    help: false,
    requireStage75Evidence: false,
    requireSuiteEvidence: false,
    stage75Evidence: [],
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
    if (arg === '--require-stage7-5-evidence') {
      args.requireStage75Evidence = true;
      continue;
    }
    if (arg === '--stage7-5-evidence') {
      args.stage75Evidence.push(requiredOptionValue(argv, index, arg));
      index += 1;
      continue;
    }
    if (arg.startsWith('--stage7-5-evidence=')) {
      args.stage75Evidence.push(requiredInlineOptionValue(arg.slice('--stage7-5-evidence='.length), '--stage7-5-evidence'));
      continue;
    }
    if (arg === '--evidence-manifest' || arg === '--manifest') {
      args.evidenceManifest = requiredOptionValue(argv, index, arg);
      index += 1;
      continue;
    }
    if (arg.startsWith('--evidence-manifest=')) {
      args.evidenceManifest = requiredInlineOptionValue(arg.slice('--evidence-manifest='.length), '--evidence-manifest');
      continue;
    }
    if (arg.startsWith('--manifest=')) {
      args.evidenceManifest = requiredInlineOptionValue(arg.slice('--manifest='.length), '--manifest');
      continue;
    }
    if (arg === '--require-suite-evidence') {
      args.requireSuiteEvidence = true;
      continue;
    }
    if (arg === '--allow-blockers') {
      args.allowBlockers = true;
      continue;
    }
    if (arg === '--evidence-no-file-check') {
      args.evidenceNoFileCheck = true;
      continue;
    }
    throw new Error(`Unknown option: ${arg}`);
  }

  if (!['json', 'markdown'].includes(args.format)) {
    throw new Error('--format must be markdown or json.');
  }
  return args;
}

export function usage() {
  return [
    'Usage:',
    '  node scripts/stage8_comprehensive_gate.mjs [--json|--format markdown|json] [--require-stage7-5-evidence] [--stage7-5-evidence <json-file>...] [--require-suite-evidence] [--evidence-manifest <json-file>] [--allow-blockers] [--evidence-no-file-check]',
    '',
    'Checks Stage 8 regression matrix integrity and optional public/release evidence.',
    '',
    'Use --require-suite-evidence with a Stage 8 evidence manifest to require every suite evidence item.',
    'Use --allow-blockers only when a documented blocker may satisfy a suite item for audit purposes.',
  ].join('\n');
}

function resolvePath(relativePath) {
  return path.resolve(root, relativePath);
}

function resolveInputPath(filePath) {
  return path.isAbsolute(filePath) ? filePath : path.resolve(root, filePath);
}

function loadJson(filePath) {
  const fullPath = resolveInputPath(filePath);
  return {
    data: JSON.parse(readFileSync(fullPath, 'utf8').replace(/^\uFEFF/, '')),
    fullPath,
  };
}

export function checkMatrixFiles(suites = STAGE8_SUITES) {
  return suites.map(suite => {
    const missing = suite.requiredPaths.filter(filePath => !existsSync(resolvePath(filePath)));
    return {
      id: suite.id,
      ok: missing.length === 0,
      required_count: suite.requiredPaths.length,
      missing,
    };
  });
}

export function checkDeploymentWebSocketProxyFiles(files = STAGE8_DEPLOYMENT_WS_PROXY_FILES) {
  return files.map(({ file, proxyPass }) => {
    const fullPath = resolvePath(file);
    if (!existsSync(fullPath)) {
      return {
        file,
        ok: false,
        checks: {
          exists: false,
          location: false,
          proxy_pass: false,
          upgrade_header: false,
          connection_upgrade: false,
          long_read_timeout: false,
        },
      };
    }

    const source = readFileSync(fullPath, 'utf8').replace(/^\uFEFF/, '');
    const checks = {
      exists: true,
      location: /location\s+\/api\/ws\//.test(source),
      proxy_pass: source.includes(`proxy_pass ${proxyPass};`),
      upgrade_header: /proxy_set_header\s+Upgrade\s+\\?\$http_upgrade;/.test(source),
      connection_upgrade: /proxy_set_header\s+Connection\s+"upgrade";/.test(source),
      long_read_timeout: /proxy_read_timeout\s+3600s;/.test(source),
    };
    return {
      file,
      ok: Object.values(checks).every(Boolean),
      checks,
    };
  });
}

function verifyStage7Evidence(files, {
  noFileCheck = false,
  type = 'auto',
} = {}) {
  if (files.length === 0) {
    return {
      ok: false,
      files: [],
      error: 'No evidence files provided.',
    };
  }
  const args = [path.resolve(root, 'scripts/verify_stage7_evidence.mjs')];
  if (noFileCheck) args.push('--no-file-check');
  if (type && type !== 'auto') {
    args.push('--type', type);
  }
  args.push(...files);
  try {
    const output = execFileSync(process.execPath, args, {
      cwd: root,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
    }).trim();
    return {
      ok: true,
      files,
      output,
      error: '',
    };
  } catch (error) {
    return {
      ok: false,
      files,
      output: (error.stdout || '').toString().trim(),
      error: error.stderr?.toString()?.trim() || error.message || String(error),
    };
  }
}

function verifyStage75Evidence(files, noFileCheck = false) {
  if (files.length === 0) {
    return {
      ok: false,
      files: [],
      output: '',
      error: 'No Stage 7.5 evidence files provided.',
    };
  }
  return verifyStage7Evidence(files, {
    noFileCheck,
    type: 'stage7.5-launch-smoke',
  });
}

function verifyStage8PublicEvidence(files, assertion) {
  if (files.length === 0) {
    return {
      ok: false,
      files: [],
      output: '',
      error: 'No Stage 8 public evidence files provided.',
    };
  }
  const missingAssertion = String(assertion || '').trim();
  if (!missingAssertion) {
    return {
      ok: false,
      files,
      output: '',
      error: 'Stage 8 public evidence verifier needs a verifierAssertion.',
    };
  }

  const errors = [];
  const outputs = [];
  for (const file of files) {
    try {
      const { data } = loadJson(file);
      if (data?.mode !== 'stage8-public-evidence-smoke') {
        errors.push(`${file}: mode must be stage8-public-evidence-smoke`);
        continue;
      }
      if (data?.error) {
        errors.push(`${file}: artifact includes error: ${data.error}`);
        continue;
      }
      if (data?.assertions?.[missingAssertion] !== true) {
        errors.push(`${file}: assertions.${missingAssertion} must be true`);
        continue;
      }
      outputs.push(`${file}: assertions.${missingAssertion}=true`);
    } catch (error) {
      errors.push(`${file}: ${error.message || String(error)}`);
    }
  }
  return {
    ok: errors.length === 0,
    files,
    output: outputs.join('\n'),
    error: errors.join('\n'),
  };
}

function verifyEvidenceByType(files, {
  noFileCheck = false,
  assertion = '',
  type = 'auto',
} = {}) {
  if (type === 'stage8-public-evidence-smoke') {
    return verifyStage8PublicEvidence(files, assertion);
  }
  return verifyStage7Evidence(files, {
    noFileCheck,
    type,
  });
}

function normalizeResult(value) {
  return String(value || '').trim().toLowerCase();
}

function listValue(value) {
  if (Array.isArray(value)) return value.map(item => String(item || '').trim()).filter(Boolean);
  if (!value) return [];
  return [String(value).trim()].filter(Boolean);
}

function nonEmptyObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value) && Object.keys(value).length > 0;
}

function hasSupportingDetail(item) {
  if (!item || typeof item !== 'object') return false;
  return Boolean(
    item.file
    || item.artifact
    || item.path
    || listValue(item.files).length
    || item.url
    || item.screenshot
    || listValue(item.screenshots).length
    || nonEmptyObject(item.screenshots)
    || item.command
    || (typeof item.notes === 'string' && item.notes.trim())
    || nonEmptyObject(item.checks),
  );
}

function normalizeManifestSuites(manifest) {
  const suites = manifest?.suites;
  if (Array.isArray(suites)) {
    return new Map(suites.map(suite => [suite?.id, suite]).filter(([id]) => id));
  }
  if (suites && typeof suites === 'object') {
    return new Map(Object.entries(suites).map(([id, suite]) => [id, { id, ...suite }]));
  }
  return new Map();
}

function evidenceItems(suiteRecord) {
  return Array.isArray(suiteRecord?.evidence) ? suiteRecord.evidence : [];
}

function blockerItems(suiteRecord) {
  return Array.isArray(suiteRecord?.blockers) ? suiteRecord.blockers : [];
}

function evidenceItemId(item) {
  return String(item?.id || item?.requirement_id || item?.evidence_id || '').trim();
}

function blockerCoversRequirement(blocker, requirementId) {
  const covers = [
    ...listValue(blocker?.covers),
    ...listValue(blocker?.covers_requirement),
    ...listValue(blocker?.requirement_ids),
    ...listValue(blocker?.requirement_id),
    ...listValue(blocker?.evidence_id),
    ...listValue(blocker?.id),
  ];
  return covers.includes(requirementId);
}

function blockerDocumentation(blocker) {
  return {
    nextAction: String(blocker?.next_action || blocker?.nextAction || blocker?.next || '').trim(),
    reason: String(blocker?.reason || blocker?.detail || blocker?.notes || '').trim(),
  };
}

function documentedBlocker(blocker, requirementId, allowBlockers) {
  const docs = blockerDocumentation(blocker);
  const covers = blockerCoversRequirement(blocker, requirementId);
  const documented = covers && Boolean(docs.reason && docs.nextAction);
  return {
    accepted: allowBlockers && documented,
    documented,
    next_action: docs.nextAction,
    reason: docs.reason,
  };
}

function findRequirementEvidence(suiteRecord, requirementId) {
  return evidenceItems(suiteRecord).find(item => evidenceItemId(item) === requirementId);
}

function findRequirementBlocker(suiteRecord, requirementId) {
  return blockerItems(suiteRecord).find(blocker => blockerCoversRequirement(blocker, requirementId));
}

function evidenceFile(item) {
  return String(item?.file || item?.artifact || item?.path || '').trim();
}

function assertRequiredCiJobs(item) {
  const checks = item?.checks || {};
  if (checks.required_jobs_ok === true) return '';
  const jobs = [
    ...listValue(checks.jobs),
    ...listValue(item?.jobs),
  ];
  const missing = STAGE8_REQUIRED_CI_JOBS.filter(job => !jobs.includes(job));
  if (missing.length === 0) return '';
  return `github-actions-green needs checks.required_jobs_ok=true or jobs containing: ${STAGE8_REQUIRED_CI_JOBS.join(', ')}`;
}

function assertPostgresSeedReset(item) {
  const checks = item?.checks || {};
  if (checks.seed_reset_ok === true || checks.postgres_seed_reset_ok === true) return '';
  return 'postgres-seed-reset needs checks.seed_reset_ok=true or checks.postgres_seed_reset_ok=true';
}

function assertArtifactHealthUrl(item, filePath) {
  const expectedUrl = String(item?.required_url || item?.health_url || item?.checks?.required_health_url || '').trim();
  if (!expectedUrl) return '';
  try {
    const { data } = loadJson(filePath);
    const urls = Array.isArray(data?.healthChecks)
      ? data.healthChecks.map(check => String(check?.url || '').trim()).filter(Boolean)
      : [];
    return urls.includes(expectedUrl)
      ? ''
      : `postdeploy-healthcheck artifact must include health URL: ${expectedUrl}`;
  } catch (error) {
    return error.message || String(error);
  }
}

function evaluatePassingEvidence(item, requirement, {
  evidenceNoFileCheck = false,
} = {}) {
  if (!hasSupportingDetail(item)) {
    return {
      ok: false,
      status: 'fail',
      error: `${requirement.id} needs supporting detail such as notes, command, URL, checks, or artifact file.`,
    };
  }

  if (requirement.id === 'github-actions-green') {
    const ciError = assertRequiredCiJobs(item);
    if (ciError) {
      return {
        ok: false,
        status: 'fail',
        error: ciError,
      };
    }
  }

  if (requirement.id === 'postgres-seed-reset') {
    const seedError = assertPostgresSeedReset(item);
    if (seedError) {
      return {
        ok: false,
        status: 'fail',
        error: seedError,
      };
    }
  }

  const file = evidenceFile(item);
  if (requirement.verifierType) {
    if (!file) {
      return {
        ok: false,
        status: 'fail',
        error: `${requirement.id} requires a JSON artifact file verified as ${requirement.verifierType}.`,
      };
    }
    const verified = verifyEvidenceByType([file], {
      assertion: requirement.verifierAssertion,
      noFileCheck: evidenceNoFileCheck,
      type: requirement.verifierType,
    });
    if (!verified.ok) {
      return {
        ok: false,
        status: 'fail',
        error: verified.error,
      };
    }
    const healthUrlError = requirement.verifierType === 'postdeploy-healthcheck'
      ? assertArtifactHealthUrl(item, file)
      : '';
    if (healthUrlError) {
      return {
        ok: false,
        status: 'fail',
        error: healthUrlError,
      };
    }
    return {
      ok: true,
      status: 'pass',
      artifact: {
        file,
        verifier_type: requirement.verifierType,
      },
      error: '',
    };
  }

  if (file && item.verifier_type) {
    const verified = verifyEvidenceByType([file], {
      assertion: item.verifier_assertion || item.verifierAssertion || requirement.verifierAssertion,
      noFileCheck: evidenceNoFileCheck,
      type: item.verifier_type,
    });
    if (!verified.ok) {
      return {
        ok: false,
        status: 'fail',
        error: verified.error,
      };
    }
  }

  return {
    ok: true,
    status: 'pass',
    error: '',
  };
}

function evaluateRequirement({
  allowBlockers,
  evidenceNoFileCheck,
  requirement,
  suiteRecord,
}) {
  const item = findRequirementEvidence(suiteRecord, requirement.id);
  if (item) {
    const result = normalizeResult(item.result || item.status);
    if (PASS_VALUES.has(result)) {
      return {
        id: requirement.id,
        label: requirement.label,
        ...evaluatePassingEvidence(item, requirement, { evidenceNoFileCheck }),
      };
    }
    if (BLOCKED_VALUES.has(result)) {
      const blocker = documentedBlocker({
        id: requirement.id,
        ...(item.blocker || item),
      }, requirement.id, allowBlockers);
      return {
        id: requirement.id,
        label: requirement.label,
        ok: blocker.accepted,
        status: 'blocked',
        blocker: {
          accepted: blocker.accepted,
          documented: blocker.documented,
          next_action: blocker.next_action,
          reason: blocker.reason,
        },
        error: blocker.documented
          ? (allowBlockers ? '' : `${requirement.id} is blocked; rerun with --allow-blockers to accept documented blockers for audit.`)
          : `${requirement.id} blocker needs reason and next_action.`,
      };
    }
    return {
      id: requirement.id,
      label: requirement.label,
      ok: false,
      status: result || 'missing-result',
      error: `${requirement.id} result must be pass or blocked.`,
    };
  }

  const blocker = findRequirementBlocker(suiteRecord, requirement.id);
  if (blocker) {
    const blockerResult = documentedBlocker(blocker, requirement.id, allowBlockers);
    return {
      id: requirement.id,
      label: requirement.label,
      ok: blockerResult.accepted,
      status: 'blocked',
      blocker: {
        accepted: blockerResult.accepted,
        documented: blockerResult.documented,
        next_action: blockerResult.next_action,
        reason: blockerResult.reason,
      },
      error: blockerResult.documented
        ? (allowBlockers ? '' : `${requirement.id} is blocked; rerun with --allow-blockers to accept documented blockers for audit.`)
        : `${requirement.id} blocker needs reason and next_action.`,
    };
  }

  return {
    id: requirement.id,
    label: requirement.label,
    ok: false,
    status: 'missing',
    error: `${requirement.id} evidence is missing.`,
  };
}

export function evaluateStage8EvidenceManifest(manifest, {
  allowBlockers = false,
  evidenceNoFileCheck = false,
} = {}) {
  const suiteMap = normalizeManifestSuites(manifest);
  const extraSuites = [...suiteMap.keys()].filter(id => !STAGE8_SUITES.some(suite => suite.id === id));
  const suites = STAGE8_SUITES.map(suite => {
    const suiteRecord = suiteMap.get(suite.id);
    if (!suiteRecord) {
      const requirements = suite.evidenceRequirements.map(requirement => ({
        id: requirement.id,
        label: requirement.label,
        ok: false,
        status: 'missing',
        error: `${requirement.id} evidence is missing.`,
      }));
      return {
        id: suite.id,
        ok: false,
        present: false,
        requirements,
      };
    }
    const requirements = suite.evidenceRequirements.map(requirement => evaluateRequirement({
      allowBlockers,
      evidenceNoFileCheck,
      requirement,
      suiteRecord,
    }));
    return {
      id: suite.id,
      ok: requirements.every(requirement => requirement.ok),
      present: true,
      requirements,
    };
  });

  const blockers = suites.flatMap(suite => suite.requirements
    .filter(requirement => requirement.status === 'blocked')
    .map(requirement => ({
      accepted: requirement.blocker?.accepted === true,
      documented: requirement.blocker?.documented === true,
      next_action: requirement.blocker?.next_action || '',
      reason: requirement.blocker?.reason || '',
      requirement_id: requirement.id,
      suite_id: suite.id,
    })));
  const missing = suites.flatMap(suite => suite.requirements
    .filter(requirement => !requirement.ok)
    .map(requirement => ({
      error: requirement.error,
      requirement_id: requirement.id,
      status: requirement.status,
      suite_id: suite.id,
    })));

  return {
    ok: suites.every(suite => suite.ok),
    allow_blockers: allowBlockers,
    blockers,
    extra_suites: extraSuites,
    missing,
    suites,
  };
}

function loadAndEvaluateManifest(filePath, args) {
  if (!filePath) {
    return {
      ok: false,
      file: '',
      allow_blockers: args.allowBlockers,
      blockers: [],
      extra_suites: [],
      missing: STAGE8_SUITES.flatMap(suite => suite.evidenceRequirements.map(requirement => ({
        error: `${requirement.id} evidence is missing.`,
        requirement_id: requirement.id,
        status: 'missing',
        suite_id: suite.id,
      }))),
      suites: [],
      error: 'No Stage 8 evidence manifest provided.',
    };
  }
  try {
    const { data, fullPath } = loadJson(filePath);
    return {
      ...evaluateStage8EvidenceManifest(data, args),
      file: fullPath,
      error: '',
    };
  } catch (error) {
    return {
      ok: false,
      file: resolveInputPath(filePath),
      allow_blockers: args.allowBlockers,
      blockers: [],
      extra_suites: [],
      missing: [],
      suites: [],
      error: error.message || String(error),
    };
  }
}

export function buildStage8GatePayload(args) {
  const suites = checkMatrixFiles();
  const matrixOk = suites.every(suite => suite.ok);
  const deploymentWsProxy = checkDeploymentWebSocketProxyFiles();
  const deploymentWsProxyOk = deploymentWsProxy.every(file => file.ok);
  const stage75Evidence = args.requireStage75Evidence || args.stage75Evidence.length > 0
    ? verifyStage75Evidence(args.stage75Evidence, args.evidenceNoFileCheck)
    : {
        ok: null,
        files: [],
        output: '',
        error: '',
      };
  const stage75EvidenceOk = args.requireStage75Evidence ? stage75Evidence.ok === true : stage75Evidence.ok !== false;
  const suiteEvidence = args.requireSuiteEvidence || args.evidenceManifest
    ? loadAndEvaluateManifest(args.evidenceManifest, args)
    : {
        ok: null,
        file: '',
        allow_blockers: args.allowBlockers,
        blockers: [],
        extra_suites: [],
        missing: [],
        suites: [],
        error: '',
      };
  const suiteEvidenceOk = args.requireSuiteEvidence ? suiteEvidence.ok === true : suiteEvidence.ok !== false;
  return {
    ok: matrixOk && deploymentWsProxyOk && stage75EvidenceOk && suiteEvidenceOk,
    matrix_ok: matrixOk,
    deployment_ws_proxy_ok: deploymentWsProxyOk,
    stage7_5_evidence_ok: stage75Evidence.ok,
    suite_evidence_ok: suiteEvidence.ok,
    suites,
    deployment_ws_proxy: deploymentWsProxy,
    stage7_5_evidence: stage75Evidence,
    suite_evidence: suiteEvidence,
  };
}

function renderRequirement(requirement) {
  const suffix = requirement.error ? ` (${requirement.error})` : '';
  return `  - ${requirement.id}: ${requirement.ok ? requirement.status : `fail/${requirement.status}`}${suffix}`;
}

function renderMarkdown(payload) {
  const lines = [
    '# Stage 8 Comprehensive Gate',
    '',
    `Ready: ${payload.ok ? 'yes' : 'no'}`,
    `Matrix: ${payload.matrix_ok ? 'ok' : 'fail'}`,
    `Deployment WS proxy: ${payload.deployment_ws_proxy_ok ? 'ok' : 'fail'}`,
    `Stage 7.5 evidence: ${payload.stage7_5_evidence_ok === null ? 'not required' : payload.stage7_5_evidence_ok ? 'ok' : 'fail'}`,
    `Suite evidence: ${payload.suite_evidence_ok === null ? 'not required' : payload.suite_evidence_ok ? 'ok' : 'fail'}`,
    '',
    '## Local Matrix Suites',
  ];
  for (const suite of payload.suites) {
    lines.push(`- ${suite.id}: ${suite.ok ? 'ok' : `missing ${suite.missing.length}`} (${suite.required_count} required)`);
    for (const missing of suite.missing) {
      lines.push(`  - missing: ${missing}`);
    }
  }
  if (payload.suite_evidence_ok !== null) {
    lines.push('', '## Evidence Manifest Suites');
    if (payload.suite_evidence.error) {
      lines.push(`- manifest error: ${payload.suite_evidence.error}`);
    }
    for (const suite of payload.suite_evidence.suites) {
      lines.push(`- ${suite.id}: ${suite.ok ? 'ok' : 'fail'}`);
      for (const requirement of suite.requirements) {
        lines.push(renderRequirement(requirement));
      }
    }
    if (payload.suite_evidence.extra_suites.length) {
      lines.push(`- extra suites ignored: ${payload.suite_evidence.extra_suites.join(', ')}`);
    }
  }
  if (payload.stage7_5_evidence.error) {
    lines.push('', '## Stage 7.5 Evidence Error', payload.stage7_5_evidence.error);
  }
  return `${lines.join('\n')}\n`;
}

async function main() {
  const args = parseArgs();
  if (args.help) {
    console.log(usage());
    return 0;
  }
  const payload = buildStage8GatePayload(args);
  if (args.format === 'json') {
    console.log(JSON.stringify(payload, null, 2));
  } else {
    console.log(renderMarkdown(payload));
  }
  return payload.ok ? 0 : 1;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().then(
    code => {
      process.exitCode = code;
    },
    error => {
      console.error(error.stack || error.message || String(error));
      process.exitCode = 1;
    },
  );
}
