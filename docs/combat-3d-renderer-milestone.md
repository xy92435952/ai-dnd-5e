# Combat 3D Renderer Milestone

> Created: 2026-05-30
> Status: future milestone after the current P2 exploration/economy work
> Scope: combat page rendering, tactical map generation, asset pipeline, and 3D/2.5D research

## Why This Milestone Exists

The current combat page is a browser-native tactical board:

- `frontend/src/components/combat/IsoBattlefield.jsx` renders a CSS grid.
- `frontend/src/components/combat/IsoUnit.jsx` renders pixel-style units through `Sprite`.
- Combat rules, turns, reactions, ownership, HP, logs, and synchronization are already handled by the existing React/FastAPI architecture.

This is stable and testable, but it is still a simple 2D/2.5D presentation. A later visual direction can turn combat into a more CRPG-like tactical scene with 3D terrain, clearer rule overlays, animated tokens, spell effects, and stronger battlefield readability.

This milestone records that direction as an intentional future turn rather than an ad hoc visual experiment.

## Product Goal

Turn the combat page from a simple grid with pixel tokens into a tactical CRPG battle scene while preserving the current project principle:

> Backend rules remain authoritative. The renderer displays combat state; it does not own DnD math or multiplayer truth.

The 3D/2.5D renderer should improve:

- Battlefield readability.
- Movement and range understanding.
- Target selection confidence.
- Area-of-effect spell clarity.
- Reaction and damage feedback.
- Monster/terrain atmosphere.
- Long-term CRPG feel.

It should not make the rules less transparent or make multiplayer synchronization harder to trust.

## Recommended Position In The Roadmap

This milestone should sit after the current golden-path stabilization and before deeper tactical content expansion.

Recommended order:

1. Finish demo-quality golden path and remaining manual verification.
2. Run a Combat UI/UX information-architecture pass.
3. Start this Combat 3D Renderer milestone as a prototype track.
4. Continue Location Graph 2.0 and Encounter Template 2.0 with the renderer in mind.
5. Add rules-backed overlays for area targeting, cover, hazards, and line of sight.
6. Promote the 3D renderer only after it proves clearer than the existing board.

The milestone should not block core rule fixes, but it should shape how future combat-map data is modeled.

## Strategic Direction

Do not start by moving the whole combat page into Unity.

The recommended route is:

1. Extract a renderer-neutral combat scene view model.
2. Keep the current DOM/CSS battlefield as the stable renderer.
3. Add a parallel Web-native 3D prototype, preferably Three.js or React Three Fiber.
4. Start with 2.5D terrain and billboard/paper-mini units.
5. Add low-poly 3D miniatures, animation, and VFX only after the interaction model works.

Unity WebGL can remain a later research option, but it should not be the first implementation path because it would introduce a second frontend runtime, bridge protocols, a heavier asset pipeline, larger builds, and harder automated testing.

## Asset Strategy

### Prototype Asset Sources

Use low-risk, reusable assets first. Every asset must be recorded in an asset manifest with source, license, author, and download date.

Recommended prototype sources:

- [Kenney](https://kenney.nl/) - CC0-style game assets, props, icons, and particle/VFX packs.
- [Poly Haven](https://polyhaven.com/) - CC0 textures, HDRIs, and some models.
- [Quaternius](https://quaternius.com/) - low-poly fantasy, dungeon, monster, and RPG-style packs. Verify license per pack on download.
- [Mixamo](https://www.mixamo.com/) - humanoid animation source for idle, walk, attack, cast, hit, and death animations. Verify account availability and license terms before production use.
- [Sketchfab](https://sketchfab.com/) - useful for individual models, but every model's license must be reviewed.
- [OpenGameArt](https://opengameart.org/) - useful for prototype assets, but license types vary widely.

Recommended paid/style-consistent source:

- [Synty Studios](https://www.syntystudios.com/) or an equivalent low-poly fantasy pack source.

### License Rules

Default policy:

- Prefer CC0 or explicitly commercial-safe assets.
- Keep attribution-ready metadata even when attribution is not required.
- Avoid NC, SA, GPL, or unclear licenses in the main game client unless reviewed deliberately.
- Do not import official DnD art, official monster sculpts, official maps, or recognizable proprietary fantasy IP.
- Store original license files alongside downloaded packs when possible.

Suggested manifest shape:

```json
{
  "id": "mine_cart_01",
  "type": "prop",
  "source": "Kenney",
  "source_url": "https://kenney.nl/",
  "license": "CC0",
  "author": "Kenney",
  "downloaded_at": "2026-05-30",
  "format": "glb",
  "tags": ["mine", "cover", "prop"],
  "scale": 1,
  "notes": "Prototype-safe cover prop."
}
```

### Minimum Asset Library

First prototype should not chase a full bestiary. It should prove the rendering and interaction loop with a small but coherent library.

Minimum biomes:

- Mine.
- Dungeon.
- Forest.

Minimum terrain:

- Floor.
- Wall.
- Door.
- Stairs or ramp.
- Pit.
- Difficult terrain.
- Hazard surface.

Minimum props:

- Crate.
- Barrel.
- Pillar.
- Rock.
- Tree.
- Cart.
- Altar.
- Torch.

Minimum unit representations:

- Player billboard.
- Humanoid enemy.
- Beast enemy.
- Undead enemy.
- Large monster placeholder.

Minimum VFX:

- Hit.
- Critical hit.
- Heal.
- Fire.
- Poison.
- Shield.
- Lightning.
- Death.

## Realtime Map Strategy

Realtime maps should be generated as structured tactical data, not as bespoke art.

The core idea:

```text
Location graph + encounter template + tactical hints + seed
  -> battle map JSON
  -> 2D or 3D renderer instantiates tiles, props, hazards, units
  -> WebSocket sends deltas for runtime changes
```

The map state should remain deterministic and recoverable from a server snapshot. Clients should not invent authoritative geometry.

### Map Layers

Use three conceptual layers:

1. Exploration map.
   - Current location, known exits, hidden/locked routes, visited state.
   - Owned by the existing location graph direction.

2. Tactical battle map.
   - Grid, terrain, walls, doors, cover, hazards, spawn zones, objective zones.
   - Generated when combat starts or when an authored combat scene is loaded.

3. Visual skin.
   - The 2D/3D renderer maps semantic terrain and props to actual assets.
   - A `mine` biome and a `forest` biome can use the same rules schema with different assets.

### Proposed Battle Map Schema

```json
{
  "id": "mine_chamber_001",
  "seed": 928341,
  "biome": "mine",
  "width": 14,
  "height": 10,
  "cells": [
    {
      "x": 0,
      "y": 0,
      "terrain": "stone_floor",
      "elevation": 0,
      "blocks_movement": false,
      "blocks_los": false,
      "cover": "none",
      "hazard": null,
      "light": "dim"
    }
  ],
  "props": [
    {
      "id": "cart_1",
      "asset": "mine_cart",
      "x": 5,
      "y": 4,
      "cover": "half"
    }
  ],
  "spawn_zones": {
    "players": [{ "x": 1, "y": 4 }],
    "enemies": [{ "x": 11, "y": 4 }]
  },
  "objectives": [
    { "type": "reach", "label": "Sealed gate", "x": 13, "y": 4 }
  ],
  "revision": 1
}
```

### Runtime Map Deltas

Do not resend the whole map for each change. Send map patches:

```json
{
  "type": "map_delta",
  "revision": 2,
  "changes": [
    { "op": "open_door", "x": 6, "y": 2 },
    { "op": "add_hazard", "x": 8, "y": 5, "hazard": "fire", "duration": 3 },
    { "op": "remove_prop", "id": "barrel_2" }
  ]
}
```

Expected behavior:

- Backend stores the authoritative map and revision.
- WebSocket broadcasts deltas.
- Refresh/reconnect fetches a full combat snapshot.
- The renderer replays only visual changes, not rules authority.

## LLM Role

The LLM should not generate meshes or pixel-perfect battle maps.

The LLM can generate tactical intent:

```json
{
  "location_type": "abandoned_mine",
  "mood": "claustrophobic",
  "terrain_hints": ["narrow tunnel", "mine cart track", "weak wooden supports"],
  "hazards": ["collapsing ceiling", "poison gas pocket"],
  "cover": ["ore carts", "rock piles"],
  "encounter_objective": "reach the sealed gate before reinforcements arrive"
}
```

The generator translates those hints into rule-safe map data. This keeps imagination flexible without letting the model bypass tactical constraints.

## Renderer Architecture

Introduce a renderer-neutral combat scene adapter:

```text
combat state
  -> CombatSceneViewModel
    -> IsoBattlefield renderer
    -> ThreeBattlefield prototype renderer
```

The view model should contain:

- Map dimensions and visible cells.
- Terrain and prop semantics.
- Entity positions.
- Current actor.
- Selected target.
- Movement range.
- Threat cells.
- Area-of-effect cells.
- Cover and line-of-sight data when available.
- Clickable intents.
- Presentation-only VFX event queue.

The 3D renderer should consume the same view model as the existing 2D renderer. That lets the project keep the current battlefield as a fallback while experimenting with 3D.

## 3D Prototype Scope

The first prototype should be deliberately narrow:

- Render a tactical grid in 3D.
- Use an orthographic/isometric camera.
- Render floor, walls, and a few props.
- Render units as billboards or paper minis.
- Map clicks back to grid coordinates.
- Support target selection.
- Support movement cell overlays.
- Support basic AoE overlays.
- Keep existing React HUD, target card, log, spell modal, and reaction prompt.
- Do not move combat rules into the renderer.

Out of scope for first prototype:

- Full 3D animated characters.
- Full Unity migration.
- Fully procedural cinematic maps.
- Physics-based movement.
- Renderer-owned combat resolution.
- New combat rules.

## Future Visual Upgrades

After interaction is proven:

- Replace billboards with low-poly `glTF` miniatures.
- Add idle, move, attack, hit, cast, and death animations.
- Add spell VFX through particles, decals, and animated billboards.
- Add terrain height, stairs, pits, and cover indicators.
- Add line-of-sight and fog-of-war overlays.
- Add camera focus for attacks, reactions, critical hits, and deaths.
- Add asset streaming or preloading by biome.

## Risks

### Readability Risk

3D can make tactical rules harder to read if the camera, grid, and overlays are unclear. DnD combat needs reliable grid interpretation.

Mitigation:

- Use an orthographic tactical camera first.
- Keep visible grid lines.
- Keep 2D-style overlays for movement, range, threat, AoE, and cover.
- Preserve a 2D fallback renderer.

### Asset Pipeline Risk

Mixed asset sources can make the game look inconsistent.

Mitigation:

- Use one visual style, preferably low-poly tabletop miniatures or paper minis.
- Keep an asset manifest.
- Normalize scale, pivot, material names, and texture sizes.
- Avoid chasing realism.

### Performance Risk

WebGL scenes can become heavy on low-end machines.

Mitigation:

- Start with small maps.
- Use instancing for repeated tiles and props.
- Preload by biome.
- Use low-poly assets and compressed textures.
- Avoid excessive real-time lights and shadows in the prototype.

### Testing Risk

Canvas/WebGL is harder to test than DOM.

Mitigation:

- Test `CombatSceneViewModel` as ordinary data.
- Keep DOM HUD tests unchanged.
- Use browser smoke tests for nonblank canvas, click mapping, and key overlays.
- Keep the old battlefield renderer until the 3D path is proven.

### Synchronization Risk

The renderer could drift from backend truth.

Mitigation:

- Backend remains authoritative.
- Renderer consumes snapshots and deltas only.
- Animation queue is presentation-only.
- Reconnect always rebuilds scene from server snapshot.

## Acceptance Criteria For Prototype

The first milestone should be considered successful only if:

- Existing 2D combat still works.
- The 3D renderer can be enabled behind a feature flag.
- A seeded combat can render a 3D tactical map.
- Player and enemy tokens appear at correct grid coordinates.
- Clicking a unit selects the same target as the 2D renderer.
- Clicking a valid move cell sends the same move intent as the 2D renderer.
- Movement and AoE overlays are visually clear.
- Existing React HUD, logs, target card, spells, and reactions still work.
- Browser verification confirms the canvas is nonblank and interactive.
- Backend tests remain unaffected.
- Frontend tests/build/lint remain green.

## Suggested Work Plan

### Step 1: Scene View Model

- Add a `CombatSceneViewModel` utility.
- Make existing `IsoBattlefield` consume it or adapt toward it.
- Keep behavior unchanged.

### Step 2: Battle Map Schema

- Add `battle_map` shape to combat state or game state.
- Start with a compatibility layer that derives map data from current grid/walls/hazards.
- Do not require backend schema changes until the shape stabilizes.

### Step 3: Asset Manifest

- Create a prototype manifest for 3D assets.
- Start with CC0 or license-reviewed assets.
- Add biome tags and semantic tags.

### Step 4: ThreeBattlefield Prototype

- Add a parallel renderer behind a feature flag.
- Render tiles, walls, props, and billboard units.
- Add click-to-grid and click-to-unit mapping.

### Step 5: Overlay Parity

- Match selected target, movement, threat, and AoE overlays.
- Compare clarity against the current 2D board.

### Step 6: Map Generation

- Add a `battle_map_service` that builds deterministic maps from:
  - location graph node
  - encounter template
  - biome
  - seed
  - party/enemy spawn needs
  - terrain and hazard hints

### Step 7: VFX Event Queue

- Convert combat log/results into presentation events:
  - attack
  - miss
  - hit
  - crit
  - damage
  - heal
  - reaction
  - death

The queue should not change rules. It only animates already-confirmed backend results.

## Final Decision Record

The project should treat 3D combat as a renderer milestone, not as a game-engine rewrite.

Decision:

- Keep FastAPI/backend rules authoritative.
- Keep React UI and HUD ownership.
- Add a renderer-neutral combat scene model.
- Prototype Web-native 3D before considering Unity.
- Generate realtime maps as structured tactical data plus asset instancing.
- Use assets through a manifest and license-review process.
- Preserve 2D fallback until the 3D renderer is measurably better.
