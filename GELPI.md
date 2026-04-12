# gelpi Specification

A minimal rendering engine built on ModernGL. Immutable scene graph, explicit mutation. Implemented as a single file: `gelpi.py`.

## Dependencies

- `moderngl` — OpenGL context and GPU resource management.
- `pyglm` — matrix math (GLM-style vec/mat types for OpenGL transforms).

## Design Principles

- **Immutable by default.** Scene graph is rebuilt each frame as a pure function of application state. Same inputs, same output, always.
- **Explicit mutation.** Two mutable reference types: `Buffer` and `Texture`. All mutation is visible in the type.
- **Engine doesn't own the window.** Applications create their own window and pass the GL context. Engine only renders.
- **One UBO contract.** Engine communicates with shaders through a single uniform buffer object at binding point 0.

## Components

### `render(ctx, camera, environment, node)`

The sole entry point. Traverses the node tree, computes world transforms, and draws.

### `Node` (frozen)

The scene graph building block. A frozen dataclass with no parent pointer. Tree is top-down only.

Fields:
- `transform` — translation, rotation, scale. Defaults to identity.
- `drawable` — optional `Drawable` reference.
- `children` — tuple of child `Node`s.

A `Node` without a drawable serves as a transform group.

### `Transform` (frozen)

Local transform applied to a node. Composed as T × R × S (scale first, then rotate, then translate).

Fields:
- `translation` — vec3. Defaults to (0, 0, 0).
- `rotation` — vec3, euler angles in radians (rx, ry, rz). Defaults to (0, 0, 0).
- `scale` — vec3. Defaults to (1, 1, 1).

### `drawable(ctx, geometry, material, instancing=None)` constructor

Creates a `Drawable`, eagerly building the VAO from the geometry, material's shader, and optional instancing configuration.

### `Drawable` (frozen)

Pairs a `Geometry` with a `Material` for rendering, with optional GPU instancing. The VAO is stored internally, created by the `drawable()` constructor.

Fields:
- `geometry` — `Geometry` reference.
- `material` — `Material` reference.
- `instancing` — optional `Instancing` reference.

### `Instancing` (frozen)

Describes per-instance data for GPU instancing. The instance count is derived at draw time from `buffer.size_bytes // stride`, where stride is computed from the layout.

Fields:
- `buffer` — `Buffer` reference containing per-instance data.
- `layout` — tuple of `(attribute_name, format)` pairs (e.g., `(("in_offset", "3f"), ("in_color", "3f"))`).

### `Camera`

Produces view and projection matrices. Convention: Z-up, forward along +Y at yaw=0/pitch=0. Positive yaw rotates clockwise from above (turns right). Positive pitch looks up.

Fields:
- `position` — vec3.
- `orientation` — (yaw, pitch, roll) euler angles in radians.
- `fov` — field of view in degrees.
- `aspect` — aspect ratio.
- `near`, `far` — clipping planes.

### `Environment` (frozen)

Global rendering state passed to `render()`. Uploaded to the engine UBO once per frame.

Fields:
- `clear_color` — vec4 background color.
- `time` — float, application time.
- `ambient` — vec3 ambient light color.
- `viewport` — (x, y, width, height) integer tuple.
- `light` — optional `DirectLight(direction, color, intensity)`.
- `cull_face` — boolean, enable backface culling. Default false.

### `Material` (frozen)

Groups a shader with its surface properties. Engine binds the material before drawing.

Fields:
- `shader` — `ctx.program()` result.
- `texture` — optional `Texture` reference.
- `uniforms` — dict of app-specific uniform name-value pairs.

Engine sets engine-owned uniforms (UBO). Application-specific uniforms from `Material.uniforms` are set as regular shader uniforms.

### `material(ctx, color, texture, lit, vertex_color)` constructor

Convenience function that returns a `Material` with a pre-built shader.

Parameters:
- `color` — vec3 or vec4. Default white.
- `texture` — optional `Texture` reference. If set, texture is sampled and multiplied with color.
- `lit` — boolean. If true, applies ambient + directional lighting. Default true.
- `vertex_color` — boolean. If true, multiplies base color by per-vertex `in_color` attribute. Default false.

### `particle_material(ctx, color, texture, vertex_color, size, screen_space)` constructor

Convenience function that returns a `Material` with a billboard particle vertex shader and the shared fragment shader.

Parameters:
- `color` — vec3 or vec4. Default white.
- `texture` — optional `Texture` reference.
- `vertex_color` — boolean. Default true (per-particle color is the common case).
- `size` — float. Quad size in world units, or pixel size when `screen_space` is true. Default 1.0.
- `screen_space` — boolean. If true, quads are sized in pixels instead of world units. Default false.

### `quad_geometry(ctx)` constructor

Returns a unit quad `Geometry` from -0.5 to 0.5 in the XY plane, with position (3f), normal (3f), and UV (2f). Suitable for use with both `material()` and `particle_material()`.

#### Custom Shaders

For advanced use cases, applications use `ctx.program()` directly and pass the result to `Material`.

Shaders opt into engine data by declaring the UBO:

```glsl
layout(std140, binding = 0) uniform Gelpi {
    mat4 model;
    mat4 view;
    mat4 projection;
    mat4 mvp;
    vec2 viewport;
    vec3 camera_pos;
    float time;
    vec3 ambient;
    int has_light;
    vec3 light_direction;
    vec3 light_color;
    float light_intensity;
};
```

Shaders that don't need engine data simply don't declare the block.

### `Geometry` (frozen)

Describes how to interpret buffer data for rendering. References buffers but does not own vertex data.

Fields:
- `layout` — tuple of `(attribute_name, format)` pairs (e.g., `(("in_position", "3f"), ("in_normal", "3f"), ("in_uv", "2f"), ("in_color", "3f"))`).
- `primitive` — `TRIANGLES`, `LINES`, `LINE_STRIP`, `POINTS`, etc.
- `vertex_buffer` — `Buffer` reference.
- `index_buffer` — optional `Buffer` reference for indexed rendering.

### `Buffer` (mutable reference)

Mutable GPU buffer. One of two mutable types in the engine. Accepts raw `bytes` (use `pack()` to convert numeric lists).

Constructor:
- `Buffer(ctx, data, dynamic=False)` — `data` is `bytes`. `dynamic=True` hints frequent updates.

Properties:
- `size_bytes` — readable size of valid data. Returns the full underlying buffer size by default. Set to limit the valid region (e.g., for partially-filled instance buffers).

Methods:
- `update(data)` — full replacement.
- `update(data, offset)` — partial update. Offset in bytes.
- `read()` — read back the raw buffer contents.

### `pack(data)` (module-level utility)

Packs a non-empty list of `int` or `float` values into little-endian `bytes` (`int32` or `float32`, auto-detected from the first element).

### `Texture` (mutable reference)

Mutable GPU texture. One of two mutable types in the engine. Accepts any iterable of byte values (0–255) for RGBA pixel data.

Constructor:
- `Texture(ctx, size, data=None)` — create from pixel data or empty.

Methods:
- `update(data)` — replace texture contents.
- `read()` — read back the raw texture contents.

## Rendering Pipeline

Each frame, `render()` performs:

1. **Set render state.** Apply viewport from `environment.viewport`, enable depth testing, apply backface culling from `environment.cull_face`.
2. **Compute world transforms.** Walk the node tree, multiply parent × child transforms.
3. **Draw.** For each drawable node:
   - Bind material (shader, texture, app uniforms).
   - Update UBO with transforms, camera, environment.
   - Draw geometry.

## UBO Contract

The engine owns a single UBO at binding point 0. It is updated per draw call with the full payload: transforms, camera, environment, and time. Shaders declare the block to receive this data.

Material-specific uniforms are set as regular uniforms on the shader, separate from the UBO.

## Type Summary

Type          Mutable  Description
-----------------------------------------------
Node          No       Transform + drawable + children
Drawable      No       Geometry + material + optional instancing
Instancing    No       Instance buffer + layout
Camera        No       View/projection
Environment   No       Clear color + ambient + light + time + viewport
DirectLight   No       Direction + color + intensity
Material      No       Shader + texture + uniforms
Geometry      No       Buffer refs + format + primitive type
Buffer        Yes      GPU buffer, updatable
Texture       Yes      GPU texture, updatable

## Smoke Test

A single test `smoke_gelpi.py` with three renders at 100x100 resolution using a headless context. Verify behavior through stdout prints and visual inspection of saved PNGs.

### Test Harness

Create a standalone GL context using `moderngl.create_standalone_context()`. No window is needed. Create a framebuffer with a single RGBA color attachment at 100x100 resolution and an associated depth renderbuffer. Bind the framebuffer before each render call.

After each `render()` call, read the color attachment's contents using its `read()` method, which returns raw RGBA bytes. Convert to a PIL `Image` using `Image.frombytes("RGBA", (100, 100), raw)`, flip vertically (OpenGL's origin is bottom-left), and save as PNG to a temp directory.

The test script should print diagnostics to stdout and save three PNGs: `render1.png`, `render2.png`, `render3.png` to `/tmp/gelpi/`. Pillow is required by the test harness for PNG export.

### Render 1: Baseline

Setup:
- Single triangle node as root. Vertices (0, 0, 1), (1, 0, -1), (-1, 0, -1), normals all (0, -1, 0), UVs (0.5, 1), (1, 0), (0, 0). Red material, no texture. Node transform: translate (1, 0, 0).
- Camera at (1, -2, 0) looking along +Y. FOV 90.
- `Environment` with dark blue clear color (0.1, 0.1, 0.3), ambient (0.3, 0.3, 0.3), viewport (0, 0, 100, 100), no directional light.

Expectations:
- UBO byte contents printed to stdout.
- World transform printed to stdout and equal to translation (1, 0, 0).
- Background is dark blue.
- A red triangle is visible, centered on screen, pointing up.
- Triangle is a dim, uniform dark red with no shading gradient (ambient only, no directional light).
- No other geometry visible.

### Render 2: Transform + lighting + lines

Changes:
- Root is now a transform group (no geometry) with two children.
- First child: the triangle node. Transform: translate (1, 0, 0), then rotate 45 degrees around Y, then scale 0.5.
- Second child: line geometry with 4 vertices (-1, 0, 1), (1, 0, 1), (-1, 0, -1), (1, 0, -1), each with white per-vertex color. Green material. Node transform: translate (-1, 0, 0), then scale 0.5. Index buffer forms 3 segments in a Z-shape, reusing two vertices.
- Add a `DirectLight` with direction (1, 1, -1), white color (1, 1, 1), intensity 1.0.
- Move camera to (0, -2, 0), still looking along +Y.

Expectations:
- Composed world transform printed to stdout.
- World transform differs from render 1 (reflects 45-degree rotation and 0.5 scale in addition to translation).
- Triangle is visibly rotated, pointing upper-right.
- Triangle is roughly half the size of render 1, in the right half of the viewport.
- Triangle is vertically centered.
- Triangle is a noticeably brighter uniform red compared to render 1 (directional light contributes evenly since all normals are identical).
- Three green line segments are visible in the left half of the viewport, forming a Z-shape.
- Lines are vertically centered.
- Lines and triangle do not overlap.

### Render 3: Mutation + texture

Changes:
- Move camera to (0, 3, 1), looking along -Y (behind the objects).
- Partially update the triangle's vertex buffer: move the top vertex position from (0, 0, 1) to (1, 0, 1).
- Partially update the triangle's vertex buffer: change the bottom-left vertex normal from (0, -1, 0) to (1, 0, 0).
- Fully replace the lines' vertex buffer with vertices (-1, 0, 1), (0, 0, 0), (1, 0, 1), (0, 0, -1) with per-vertex colors red, green, blue, yellow respectively to form a Y-shape.
- Fully replace the lines' index buffer to form a Y-shape instead of a Z-shape.
- Rebuild the line drawable with a white base material with `lit=False`, so vertex colors show through.
- Replace the triangle's `Material` with one that uses a 4x4 black-and-white checkerboard `Texture`.

Expectations:
- Buffer contents before mutation printed to stdout (original vertex positions).
- Buffer contents after mutation printed to stdout (modified vertex positions).
- Before and after buffer contents differ.
- Triangle occupies the left-bottom part of the viewport.
- Y-shaped lines occupy the right-bottom part of the viewport.
- Triangle shape has changed — wider and flatter than render 2, resembling a downward-pointing chevron (top vertex was shifted right by buffer mutation).
- Triangle surface shows a black-and-white checkerboard pattern.
- Checkerboard shows a smooth shading gradient — the bottom vertex with the mutated normal (1, 0, 0) is as dim as render 1 (ambient only), while the other two vertices remain bright. The gradient is clearly visible across the checkerboard pattern.
- Line segments form a Y-shape instead of the Z-shape from render 2.
- Green lines are still visible and distinct from the triangle.

### Coverage

Feature                               Step
---------------------------------------------
Node with drawable                    1,2,3
Transform group (no drawable)         2,3
Parent-child transform composition    2,3
Geometry — TRIANGLES                  1,2,3
Geometry — LINES                      2,3
Index buffer                          2,3
Material — flat color                 1,2
Material — textured                   3
Camera                                1,2,3
Camera position change                2,3
Environment — ambient only            1
Environment — ambient + light         2,3
UBO contract                          1,2,3
Buffer partial mutation               3
Buffer full mutation                  3
Texture                               3
Vertex color attribute                2,3

## Notes

- Pack according to std140 rules — do not guess at padding. After implementing, verify the packed byte count matches the driver's expected UBO size:

   ```python
   block = prog._members["Gelpi"]  # UniformBlock
   assert len(packed_bytes) == block.size
   ```

- All matrices use **column-vector convention** via PyGLM: `mvp = proj * view * world`, `world = parent * child`. PyGLM's `mat4.to_bytes()` serialises row-major, which matches GLSL's column-major layout directly — no transpose needed.
