# minebench Specification

Single-file Minecraft-like demo (`minebench.py`) using gelpi for rendering.

## World

- Right-hand coordinate system: X/Y horizontal, Z up.
- 100×100×100 block grid.
- Terrain generated with Perlin noise heightmap. Height range: ~10–30 blocks.
- Top layer: grass blocks (green). All blocks below: dirt blocks (brown).
- Blocks below y=0 and above the heightmap are air.
- No caves, no water, no trees.

## Rendering

- Blue sky: clear color `(0.53, 0.81, 0.92, 1.0)`.
- Only exposed faces are emitted (skip faces between two solid blocks).
- Each block type has a distinct base color via per-vertex color:
  - Grass top face: `(0.3, 0.8, 0.2)`. Grass side faces: `(0.3, 0.6, 0.1)`.
  - Dirt: `(0.55, 0.35, 0.15)`.
- Each block has a random brightness variation of ±0.08 applied uniformly across all its faces.
- Directional light from above-right `(0.5, -1.0, -0.3)` for shading.
- Backface culling enabled (only outward-facing block faces visible).
- All geometry in a single `Buffer` + `Geometry` + `Drawable`, rebuilt once at startup.

## Camera & Controls

- First-person camera. Initial position: center of map, looking along +Y.
- Mouse controls yaw/pitch (captured/locked cursor via `mglw` exclusive mouse). Pitch clamped to ±89.999°.
- `W`/`A`/`S`/`D` — move forward/left/backward/right relative to facing direction (horizontal plane only).
- `SPACE` — jump (apply upward velocity, simple gravity pulls back down).
- `SHIFT` — run (hold while moving).
- Walking speed: ~5 blocks/second. Running speed: ~10 blocks/second.
- Mouse sensitivity: ~0.002 rad/pixel.
- No collision with blocks (noclip), except gravity pulls player down to terrain surface.
- Eyes are 1.7 blocks above the terrain surface.
- Camera near=0.1, far=300.

## Physics

- Gravity: 20 blocks/s². Jump velocity: 8 blocks/s.
- Player stands on the highest solid block at their (x, y) position.
- When in air (after jumping or walking off edge), gravity applies until landing.

## Architecture

Functional/declarative style. Immutable data throughout; side effects only at the boundaries (input handling, GPU uploads, rendering).

### Entry Points

- `init(ctx, seed=None) -> State` — generates world, builds mesh, uploads geometry to GPU. Returns initial immutable state. Seed controls terrain generation for reproducibility.
- `step(state, events, dt) -> State` — pure state transition. Processes input events in order, updates held-keys set, accumulates mouse deltas, applies movement and physics. Returns new state.
- `render_frame(ctx, state, viewport)` — derives `Camera`, `Environment`, and scene `Node` from state. Calls `gl.render()`.

### Pure Functions (no side effects)

- `generate_heightmap(seed) -> np.ndarray` — returns 100×100 int heightmap from Perlin noise.
- `generate_blocks(heightmap) -> np.ndarray` — returns 100×100×100 uint8 block type array from heightmap.
- `build_mesh(blocks) -> list[float]` — iterates all solid blocks, emits vertices for exposed faces with position + normal + color. Returns flat vertex list.

### Data (frozen dataclasses)

- `State(player, heightmap, keys, drawable)` — complete simulation state. Each frame produces a new State via `dataclasses.replace()`.
- `Player(x, y, z, vz, yaw, pitch)` — player state. `vz` is vertical velocity.
- `KeyPress(key)`, `KeyRelease(key)`, `MouseMove(dx, dy)` — input events.

### Boundary (side effects)

- `Window(mglw.WindowConfig)` — thin shell. Only mutable state: `self.state` and `self.pending` (list of input events). Callbacks append events to `self.pending`. `on_render` passes them to `step`, clears the list, calls `render_frame`.

## Perlin Noise

- Implement a simple 2D Perlin noise function inline (no external dependency).
- Sample at scale ~0.05 per block coordinate for rolling hills.
- Map noise output to height range [10, 30].

## Vertex Format

```
layout: (("in_position", "3f"), ("in_normal", "3f"), ("in_color", "3f"))
```

One `material(ctx, lit=True)` with white base color — vertex colors provide block coloring, lighting via the directional light + ambient.

## Input Handling

Event-based. Callbacks append frozen event dataclasses to a pending list. `on_render` consumes and clears the list.

- `on_key_event` — appends `KeyPress(key)` or `KeyRelease(key)`.
- `on_mouse_position_event` — appends `MouseMove(dx, dy)`.
- `on_render` — calls `step(self.state, self.pending, frame_time)`, clears `self.pending`, calls `render_frame`.
- `ESC` — close window.

## Smoke Tests

Use the following approach for headless testing:

- Create a standalone context via `moderngl.create_standalone_context()` with an offscreen framebuffer.
- Call `init(ctx)` to get initial state.
- Feed synthetic event lists to `step()` to simulate player actions (walk forward, look around, jump).
- After all steps, call `render_frame()` to render into the framebuffer, read pixels, save PNG.
- Read the saved image to perform visual inspection and confirm the expected outcome.
- When testing physics or animations, run `step()` multiple times in a loop to accumulate state. Capture extra screenshots (before, in the middle, and after) for analysis.

Since `step` is pure and deterministic, replaying the same event sequence always produces the same state. No mocking or window needed.

### Scenarios

1. **Initial render** — init + render without any steps. Verify blue sky, terrain visible, camera at correct starting position.
2. **Walk forward** — several steps with W key held. Verify camera position changed, terrain still visible from new angle.
3. **Look around** — MouseMove events to rotate yaw/pitch. Verify different part of terrain visible compared to initial.
4. **Jump** — press SPACE, run steps in a loop. Capture before, at peak, and after landing. Verify Z position rises then returns to ground.
5. **Walk to edge** — walk to world boundary. Verify no crash, terrain still renders.
6. **Look straight down** — pitch down fully. Verify ground blocks visible directly below.
7. **Look at horizon** — verify sky/terrain boundary, distant blocks visible within far plane.
