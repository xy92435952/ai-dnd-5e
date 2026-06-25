#!/usr/bin/env node
import { execFileSync } from 'node:child_process';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const root = path.resolve(scriptDir, '..');

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
  },
  {
    id: 'production-parity',
    requiredPaths: [
      'scripts/check.sh',
      'scripts/stage7_reaction_backend_gate.sh',
      'scripts/verify_stage7_evidence.mjs',
      'scripts/stage7_5_launch_experience_smoke.mjs',
      'scripts/stage8_comprehensive_gate.mjs',
      'backend/tests/unit/test_smoke_scenario_seed.py',
      'frontend/src/__tests__/stage7EvidenceVerifier.test.js',
      'frontend/src/__tests__/stage7_5LaunchExperienceSmoke.test.js',
      'frontend/src/__tests__/stage8ComprehensiveGate.test.js',
    ],
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

export function parseArgs(argv = process.argv.slice(2)) {
  const args = {
    format: 'markdown',
    help: false,
    requireStage75Evidence: false,
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
    '  node scripts/stage8_comprehensive_gate.mjs [--json|--format markdown|json] [--require-stage7-5-evidence] [--stage7-5-evidence <json-file>...]',
    '',
    'Checks Stage 8 comprehensive regression matrix integrity and optionally verifies Stage 7.5 public launch evidence.',
  ].join('\n');
}

function resolvePath(relativePath) {
  return path.resolve(root, relativePath);
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

function verifyStage75Evidence(files) {
  if (files.length === 0) {
    return {
      ok: false,
      files: [],
      error: 'No Stage 7.5 evidence files provided.',
    };
  }
  try {
    execFileSync(process.execPath, [
      path.resolve(root, 'scripts/verify_stage7_evidence.mjs'),
      '--type',
      'stage7.5-launch-smoke',
      ...files,
    ], {
      cwd: root,
      encoding: 'utf8',
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    return {
      ok: true,
      files,
      error: '',
    };
  } catch (error) {
    return {
      ok: false,
      files,
      error: error.stderr?.toString()?.trim() || error.message || String(error),
    };
  }
}

export function buildStage8GatePayload(args) {
  const suites = checkMatrixFiles();
  const matrixOk = suites.every(suite => suite.ok);
  const stage75Evidence = args.requireStage75Evidence || args.stage75Evidence.length > 0
    ? verifyStage75Evidence(args.stage75Evidence)
    : {
        ok: null,
        files: [],
        error: '',
      };
  const evidenceOk = args.requireStage75Evidence ? stage75Evidence.ok === true : stage75Evidence.ok !== false;
  return {
    ok: matrixOk && evidenceOk,
    matrix_ok: matrixOk,
    stage7_5_evidence_ok: stage75Evidence.ok,
    suites,
    stage7_5_evidence: stage75Evidence,
  };
}

function renderMarkdown(payload) {
  const lines = [
    '# Stage 8 Comprehensive Gate',
    '',
    `Ready: ${payload.ok ? 'yes' : 'no'}`,
    `Matrix: ${payload.matrix_ok ? 'ok' : 'fail'}`,
    `Stage 7.5 evidence: ${payload.stage7_5_evidence_ok === null ? 'not required' : payload.stage7_5_evidence_ok ? 'ok' : 'fail'}`,
    '',
    '## Suites',
  ];
  for (const suite of payload.suites) {
    lines.push(`- ${suite.id}: ${suite.ok ? 'ok' : `missing ${suite.missing.length}`} (${suite.required_count} required)`);
    for (const missing of suite.missing) {
      lines.push(`  - missing: ${missing}`);
    }
  }
  if (payload.stage7_5_evidence.error) {
    lines.push('', '## Evidence Error', payload.stage7_5_evidence.error);
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
