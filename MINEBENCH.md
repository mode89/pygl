# minebench Specification

Single-file Minecraft-like demo (`minebench.py`) using gelpi for rendering.

## World

- Right-hand coordinate system: X/Y horizontal, Z up.
- Infinite chunked world. Each chunk is `CHUNK_SIZE`x`CHUNK_SIZE`x`CHUNK_HEIGHT` (16x16x64).
- Terrain generated with 2D Perlin noise heightmap. Height range: ~10–30 blocks.
- Top layer: grass blocks (green). All blocks below: dirt blocks (brown).
- Blocks below z=0 and above the heightmap are air.
- No caves, no water, no trees.

## Chunks

Chunks are identified by `(cx, cy)` integer coordinates. The world is divided into a grid of chunks, each covering a 16x16 column of blocks up to height 64.

### Chunk States

The `state.chunks` dict maps `(cx, cy)` to one of:

- **Not in dict** — chunk not requested yet.
- **`Future`** — generation + meshing in flight on process pool.
- **`Chunk` with drawable** — done, renderable. Drawable is a `gl.Drawable`, or `"empty"` for chunks with no visible faces.

### Async Generation

- A `ProcessPoolExecutor` (16 workers) handles chunk generation off the main thread.
- `_generate_and_mesh(cx, cy, perm, seed)` runs in a worker process: generates heightmap + blocks, builds vertex list. Pure CPU, no OpenGL.
- Each chunk meshes independently — no neighbor awareness. Out-of-bounds lookups return air (exposed faces at chunk borders).
- New chunk submissions are sorted by distance from the player (nearest first).

### Chunk Lifecycle (`_update_chunks`)

Called once per frame (and once during `init`):

1. **Unload** — remove entries beyond `RENDER_DISTANCE + 1`. Cancel if `Future`.
2. **Collect** — for each done `Future`, upload vertices to GPU, store `Chunk` with drawable. Rate-limited by `max_meshes` per frame.
3. **Submit** — for each missing `(cx, cy)` within `RENDER_DISTANCE`, submit `_generate_and_mesh` to the process pool. Nearest chunks submitted first.

## Rendering

- Blue sky: clear color `(0.53, 0.81, 0.92, 1.0)`.
- Only exposed faces are emitted (skip faces adjacent to solid blocks within the same chunk).
- Each block type has a distinct base color via per-vertex color:
  - Grass top face: `(0.3, 0.8, 0.2)`. Grass side faces: `(0.3, 0.6, 0.1)`.
  - Dirt: `(0.55, 0.35, 0.15)`.
- Each block has a random brightness variation of ±0.08 applied uniformly across all its faces.
- Directional light from above-right `(0.5, -1.0, -0.3)` for shading.
- Backface culling enabled (only outward-facing block faces visible).
- Each chunk gets its own `Buffer` + `Geometry` + `Drawable`.
- `render_frame` skips `Future` entries and `"empty"` chunks.

## Block Selection

- A white wireframe cube highlights the block under the crosshair.
- `_raycast(state, origin, direction, max_dist=64.0)` — DDA voxel traversal. Takes an arbitrary origin and direction; returns `(bx, by, bz)` of the first solid block hit, or `None`.
- `_player_look_dir(player)` — computes the unit look direction from player yaw/pitch.
- The wireframe drawable is a unit cube (0–1 range) created once at init (`selected_block`). At render time it is positioned and slightly padded via `gl.Transform(translation, scale)` — no per-frame geometry allocation.
- `_get_block_at(state, wx, wy, wz)` — looks up the block type at integer world coordinates using chunk data. Returns `Block.AIR` for out-of-bounds or absent chunks.

## Camera & Controls

- First-person camera. Initial position: origin (0, 0), looking along +Y.
- Mouse controls yaw/pitch (captured/locked cursor via `mglw` exclusive mouse). Pitch clamped to ±89.999°.
- `W`/`A`/`S`/`D` — move forward/left/backward/right relative to facing direction (horizontal plane only).
- `SPACE` — jump (apply upward velocity, simple gravity pulls back down).
- `SHIFT` — run (hold while moving).
- Walking speed: 5 blocks/second. Running speed: 10 blocks/second.
- Mouse sensitivity: 0.002 rad/pixel.
- No collision with blocks (noclip), except gravity pulls player down to terrain surface.
- Eyes are 1.7 blocks above the terrain surface.
- Camera near=0.1, far=300.

## Physics

- Gravity: 20 blocks/s². Jump velocity: 8 blocks/s.
- Player stands on the highest solid block at their (x, y) position.
- When in air (after jumping or walking off edge), gravity applies until landing.
- `_get_ground_z` uses chunk heightmap if available, otherwise falls back to on-the-fly Perlin computation (for when chunks are still `Future` or absent).

## Architecture

Functional/declarative style. Immutable data throughout; side effects only at the boundaries (input handling, GPU uploads, rendering).

### Entry Points

- `init(ctx, seed=None) -> State` — creates permutation table, submits initial chunks to the process pool asynchronously, sets player Z from Perlin fallback. Returns initial state (chunks may still be in flight).
- `step(ctx, state, events, dt) -> State` — processes input events, updates movement and physics, calls `_update_chunks` to manage chunk lifecycle. Returns new state.
- `render_frame(ctx, state, viewport)` — derives `Camera`, `Environment`, and scene `Node` from state. Skips non-`Chunk` entries. Raycasts to find the aimed block and adds a wireframe highlight node if hit. Calls `gl.render()`.

### Pure Functions (no side effects)

- `generate_chunk_heightmap(cx, cy, perm)` — returns `array.array("i")` heightmap for one chunk.
- `generate_chunk_blocks(heightmap)` — returns `bytearray` block array from heightmap.
- `generate_chunk(cx, cy, perm)` — combines the above, returns `Chunk` with `drawable=None`.
- `build_chunk_mesh(chunk, seed)` — iterates solid blocks, emits vertices for exposed faces (chunk-local only). Returns flat vertex list.
- `_generate_and_mesh(cx, cy, perm, seed)` — worker function: generates chunk + builds mesh. Returns `(chunk, verts)`.
- `_player_look_dir(player)` — returns `(dx, dy, dz)` unit direction from yaw/pitch.
- `_raycast(state, origin, direction, max_dist)` — DDA voxel traversal, returns `(bx, by, bz)` or `None`.
- `_get_block_at(state, wx, wy, wz)` — block lookup at integer world coords.

### Enums

- `Block(IntEnum)` — `AIR = 0`, `GRASS = 1`, `DIRT = 2`. Used in block arrays and meshing logic.
- `Key(Enum)` — `W`, `A`, `S`, `D`, `SPACE`, `SHIFT`, `ESCAPE`. Backend-independent key identifiers used in events and the held-keys set.

### Data (frozen dataclasses)

- `State(player, keys, chunks, seed, perm, block_material, selected_block)` — complete simulation state. `chunks` is a `dict[(int,int), Chunk | Future]`. `keys` is a `frozenset[Key]`. `selected_block` is a wireframe cube `Drawable` for highlighting the aimed block.
- `Player(x, y, z, vz, yaw, pitch)` — player state. `vz` is vertical velocity.
- `Chunk(cx, cy, heightmap, blocks, drawable)` — chunk data + GPU handle.
- `KeyPress(key)`, `KeyRelease(key)`, `MouseMove(dx, dy)` — input events. `key` is a `Key` enum value.

### Boundary (side effects)

- `Window(mglw.WindowConfig)` — thin shell. Only mutable state: `self.state` and `self.pending` (list of input events). Callbacks append events to `self.pending`. `on_render` passes them to `step`, clears the list, calls `render_frame`.

## Perlin Noise

- Simple 2D Perlin noise function inline (no external dependency).
- Permutation table seeded from `Random(seed)`, stored as tuple in state for reproducibility and process-safety.
- Sample at scale 0.05 per block coordinate for rolling hills.
- Map noise output to height range ~[10, 30] via `round(n * 10 + 20)`.

## Vertex Format

```
layout: (("in_position", "3f"), ("in_normal", "3f"), ("in_color", "3f"))
```

One `material(ctx, lit=True)` shared across all chunks (`block_material`) — vertex colors provide block coloring, lighting via the directional light + ambient.

## Input Handling

Event-based. Callbacks append frozen event dataclasses to a pending list. `on_render` consumes and clears the list.

- `on_key_event` — translates backend key codes to `Key` enum values (e.g. `self.wnd.keys.W` maps to `Key.W`), then appends `KeyPress(key)` or `KeyRelease(key)`. Both left and right shift map to `Key.SHIFT`. Unknown keys are ignored.
- `on_mouse_position_event` — appends `MouseMove(dx, dy)`.
- `on_render` — calls `step(self.ctx, self.state, self.pending, frame_time)`, clears `self.pending`, calls `render_frame`.
- `ESC` — close window.

## Smoke Tests

Create `smoke_minebench.py` that implements smoke tests.

Use the following approach for headless testing:

- Create a standalone context via `moderngl.create_standalone_context()` with an offscreen framebuffer.
- Call `init(ctx, seed)` to get initial state.
- Use `drain_futures(state)` helper to wait for all in-flight chunks to complete before rendering or asserting.
- Feed synthetic event lists to `step()` to simulate player actions (walk forward, look around, jump).
- After all steps, drain futures, call `render_frame()` to render into the framebuffer, read pixels, save PNG under `/tmp/minebench/`.
- Set `RENDER_DISTANCE` to a small value (e.g. 2) before `init` to keep tests fast.

Since `step` is pure and deterministic, replaying the same event sequence always produces the same state. No mocking or window needed.

### Scenarios

1. **Initial render** — init + drain + render without any steps. Verify blue sky, terrain visible, camera at correct starting position.
2. **Walk forward** — several steps with W key held. Verify camera position changed, terrain still visible from new angle.
3. **Look around** — MouseMove events to rotate yaw/pitch. Verify different part of terrain visible compared to initial.
4. **Jump** — press SPACE, run steps in a loop. Capture before, at peak, and after landing. Verify Z position rises then returns to ground.
5. **Walk far (infinite world)** — walk many steps, verify new chunks load and old ones unload. No crash.
6. **Look straight down** — pitch down fully. Verify ground blocks visible directly below.
7. **Look at horizon** — verify sky/terrain boundary, distant blocks visible within far plane.
