#!/usr/bin/env sh
set -eu

SCRIPT_DIR=${0%/*}
if [ "$SCRIPT_DIR" = "$0" ]; then
  SCRIPT_DIR=.
fi
ROOT_DIR="$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)"
BACKEND_PYTEST="$ROOT_DIR/backend/.venv-codex/bin/pytest"
BACKEND_PYTHON="$ROOT_DIR/.codex-test-artifacts/backend-venv/Scripts/python.exe"

TARGETS="
backend/tests/unit/test_combat_reaction_service.py::test_build_pending_attack_reaction_captures_attack_events
backend/tests/unit/test_combat_reaction_service.py::test_cutting_words_damage_reduces_first_qualifying_damage_roll
backend/tests/unit/test_combat_reaction_service.py::test_cutting_words_ability_check_subtracts_from_check_total
backend/tests/unit/test_combat_reaction_service.py::test_cutting_words_spends_bardic_resource_and_uses_subclass_die
backend/tests/unit/test_campaign_visibility_service.py::test_public_game_state_projects_pending_exploration_reaction_only_to_reactor
backend/tests/unit/test_ws_events.py::TestSampleEvents::test_reaction_prompt_projection_keeps_prompt_only_for_reactor
backend/tests/unit/test_ws_events.py::TestSampleEvents::test_exploration_reaction_prompt_carries_private_prompt
backend/tests/unit/test_game_exploration_service.py::test_send_exploration_reaction_prompt_targets_reactor_user
backend/tests/unit/test_game_exploration_service.py::test_broadcast_exploration_result_sends_private_prompt_to_reactor
backend/tests/unit/test_exploration_reaction_service.py::test_accepting_pending_feather_fall_spends_slot_and_prevents_saved_trap_damage
backend/tests/unit/test_exploration_reaction_service.py::test_declining_pending_feather_fall_applies_saved_trap_damage_without_spending_slot
backend/tests/integration/test_smoke_seed_feather_fall.py::test_seeded_feather_fall_variant_restores_prompt_and_resolves_via_http
backend/tests/integration/test_smoke_seed_feather_fall.py::test_seeded_feather_fall_variant_decline_applies_saved_damage
backend/tests/integration/test_multiplayer_ws_realtime.py::test_multiplayer_exploration_feather_fall_prompt_is_private_across_ws_and_refresh
backend/tests/integration/test_multiplayer_ws_realtime.py::test_multiplayer_guest_reaction_uses_guest_character_and_broadcasts_update
backend/tests/integration/test_multiplayer_ws_realtime.py::test_multiplayer_reaction_prompt_does_not_cross_room_boundaries
backend/tests/integration/test_multiplayer_ws_realtime.py::test_multiplayer_guest_cutting_words_damage_reduces_damage_and_broadcasts_state
backend/tests/integration/test_multiplayer_ws_realtime.py::test_multiplayer_counterspell_prompt_broadcasts_to_guest_reactor_and_cancels_spell
"

cd "$ROOT_DIR"

if [ -x "$BACKEND_PYTEST" ]; then
  # shellcheck disable=SC2086
  "$BACKEND_PYTEST" $TARGETS -q
elif [ -x "$BACKEND_PYTHON" ]; then
  # shellcheck disable=SC2086
  "$BACKEND_PYTHON" -m pytest $TARGETS -q
else
  # shellcheck disable=SC2086
  pytest $TARGETS -q
fi
