"""Smoke test for gelpi.py — three renders at 100x100, headless."""

import os
import math
import shutil
import struct

import moderngl  # pylint: disable=import-error
from PIL import Image  # pylint: disable=import-error

import gelpi as gl

TEMP_DIR = "/tmp/gelpi"
shutil.rmtree(TEMP_DIR, ignore_errors=True)
os.makedirs(TEMP_DIR)

# --- Standalone context + framebuffer ---
ctx = moderngl.create_standalone_context(require=430)
color_att = ctx.texture((100, 100), 4)
depth_att = ctx.depth_renderbuffer((100, 100))
fbo = ctx.framebuffer(color_attachments=[color_att], depth_attachment=depth_att)


def save(name):
    """Save the current framebuffer to a PNG file."""
    raw = color_att.read()
    img = Image.frombytes("RGBA", (100, 100), raw)
    img = img.transpose(Image.FLIP_TOP_BOTTOM)
    img.save(f"{TEMP_DIR}/{name}")
    print(f"  Saved {TEMP_DIR}/{name}")


# ============================================================
# RENDER 1: Baseline
# ============================================================
print("=" * 60)
print("RENDER 1: Baseline")
print("=" * 60)

# Triangle: position(3f) + normal(3f) + uv(2f) = 8 floats/vertex
# Geometry in XZ plane (vertical), facing -Y toward camera.
tri_buf = gl.Buffer(ctx, [
     0.0, 0.0,  1.0,   0.0, -1.0, 0.0,   0.5, 1.0,   # top
     1.0, 0.0, -1.0,   0.0, -1.0, 0.0,   1.0, 0.0,   # bottom-right
    -1.0, 0.0, -1.0,   0.0, -1.0, 0.0,   0.0, 0.0,   # bottom-left
], dynamic=True)
tri_geom = gl.Geometry(
    layout=(("in_position", "3f"), ("in_normal", "3f"), ("in_uv", "2f")),
    primitive=gl.TRIANGLES,
    vertex_buffer=tri_buf,
)
tri_mat = gl.material(ctx, color=(1, 0, 0, 1))
tri_drawable = gl.drawable(ctx, tri_geom, tri_mat)
tri_node = gl.Node(
    transform=gl.Transform(translation=(1, 0, 0)),
    drawable=tri_drawable,
)

cam1 = gl.Camera(position=(1, -2, 0), fov=90, aspect=1.0)
env1 = gl.Environment(
    clear_color=(0.1, 0.1, 0.3, 1.0),
    ambient=(0.3, 0.3, 0.3),
    viewport=(0, 0, 100, 100),
)

# Verify UBO size
engine_block = tri_mat.shader["Gelpi"]  # pylint: disable=unsubscriptable-object
print(f"  Shader expects UBO size: {engine_block.size}")
assert engine_block.size == 336, f"UBO size mismatch: {engine_block.size}"

# World transform
world1 = gl._transform_matrix(tri_node.transform)  # pylint: disable=protected-access
print(f"  World transform:\n{world1}")

fbo.use()
gl.render(ctx, cam1, env1, tri_node)

# UBO bytes
ubo_data = ctx._ubo.read()  # pylint: disable=protected-access
print(f"  UBO bytes ({len(ubo_data)} bytes):")
for i in range(0, len(ubo_data), 32):
    print(f"    {i:3d}: {ubo_data[i:i+32].hex()}")

save("render1.png")
print()

# ============================================================
# RENDER 2: Transform + lighting + lines
# ============================================================
print("=" * 60)
print("RENDER 2: Transform + lighting + lines")
print("=" * 60)

tri_node2 = gl.Node(
    transform=gl.Transform(
        translation=(1, 0, 0),
        rotation=(0, math.pi / 4, 0),
        scale=(0.5, 0.5, 0.5),
    ),
    drawable=tri_drawable,
)

# Lines: position(3f) + color(3f), 4 vertices
line_buf = gl.Buffer(ctx, [
    -1.0, 0.0,  1.0,  1.0, 1.0, 1.0,
     1.0, 0.0,  1.0,  1.0, 1.0, 1.0,
    -1.0, 0.0, -1.0,  1.0, 1.0, 1.0,
     1.0, 0.0, -1.0,  1.0, 1.0, 1.0,
], dynamic=True)
line_ibo = gl.Buffer(ctx, [0, 1, 1, 2, 2, 3], dynamic=True)
line_geom = gl.Geometry(
    layout=(("in_position", "3f"), ("in_color", "3f")),
    primitive=gl.LINES,
    vertex_buffer=line_buf,
    index_buffer=line_ibo,
)
line_mat = gl.material(ctx, color=(0, 1, 0, 1), lit=False, vertex_color=True)
line_drawable = gl.drawable(ctx, line_geom, line_mat)
line_node = gl.Node(
    transform=gl.Transform(
        translation=(-1, 0, 0),
        scale=(0.5, 0.5, 0.5),
    ),
    drawable=line_drawable,
)

root2 = gl.Node(children=(tri_node2, line_node))

cam2 = gl.Camera(position=(0, -2, 0), fov=90, aspect=1.0)
env2 = gl.Environment(
    clear_color=(0.1, 0.1, 0.3, 1.0),
    ambient=(0.3, 0.3, 0.3),
    viewport=(0, 0, 100, 100),
    light=gl.DirectLight(direction=(1, 1, -1), color=(1, 1, 1), intensity=1.0),
)

# Composed world transform for triangle child (column-vector: parent * child)
world2 = (
    gl._transform_matrix(root2.transform)  # pylint: disable=protected-access
    * gl._transform_matrix(tri_node2.transform)  # pylint: disable=protected-access
)
print(f"  Composed world transform (triangle):\n{world2}")
print(f"  Differs from render 1: {world1 != world2}")

fbo.use()
gl.render(ctx, cam2, env2, root2)
save("render2.png")
print()

# ============================================================
# RENDER 3: Mutation + texture
# ============================================================
print("=" * 60)
print("RENDER 3: Mutation + texture")
print("=" * 60)

# Buffer contents before mutation
before_raw = tri_buf.read()
before_floats = struct.unpack(f"<{len(before_raw) // 4}f", before_raw)
before_positions = [before_floats[i:i+3] for i in range(0, len(before_floats), 8)]
print(f"  Triangle buffer BEFORE mutation (positions):\n{before_positions}")

# Partial update: top vertex position (0,0,1) -> (1,0,1)
tri_buf.update([1.0, 0.0, 1.0,  0.0, -1.0, 0.0,  0.5, 1.0], offset=0)
# Partial update: bottom-left normal (0,-1,0) -> (1,0,0)
tri_buf.update([-1.0, 0.0, -1.0,  1.0, 0.0, 0.0,  0.0, 0.0], offset=16)

after_raw = tri_buf.read()
after_floats = struct.unpack(f"<{len(after_raw) // 4}f", after_raw)
after_positions = [after_floats[i:i+3] for i in range(0, len(after_floats), 8)]
print(f"  Triangle buffer AFTER mutation (positions):\n{after_positions}")
print(f"  Buffers differ: {before_raw != after_raw}")

# Full replace line vertex buffer (Y-shape) with per-vertex colors
line_buf.update([
    -1.0, 0.0,  1.0,  1.0, 0.0, 0.0,  # red
     0.0, 0.0,  0.0,  0.0, 1.0, 0.0,  # green
     1.0, 0.0,  1.0,  0.0, 0.0, 1.0,  # blue
     0.0, 0.0, -1.0,  1.0, 1.0, 0.0,  # yellow
])

# Full replace line index buffer (Y-shape)
line_ibo.update([0, 1, 2, 1, 1, 3])

# 4x4 black-and-white checkerboard texture
checker = []
for y in range(4):
    for x in range(4):
        c = 255 if (x + y) % 2 == 0 else 0  # pylint: disable=invalid-name
        checker += [c, c, c, 255]
tex = gl.Texture(ctx, (4, 4), data=checker)

# New textured material
tex_mat = gl.material(ctx, color=(1, 1, 1, 1), texture=tex, lit=True)

# Rebuild triangle node with new material
# (geometry unchanged — same mutated buffer)
tri_node3 = gl.Node(
    transform=gl.Transform(
        translation=(1, 0, 0),
        rotation=(0, math.pi / 4, 0),
        scale=(0.5, 0.5, 0.5),
    ),
    drawable=gl.drawable(ctx, tri_geom, tex_mat),
)

# Rebuild line drawable with white material so vertex colors show through
line_mat3 = gl.material(ctx, color=(1, 1, 1, 1), lit=False, vertex_color=True)
line_drawable3 = gl.drawable(ctx, line_geom, line_mat3)
line_node3 = gl.Node(
    transform=gl.Transform(
        translation=(-1, 0, 0),
        scale=(0.5, 0.5, 0.5),
    ),
    drawable=line_drawable3,
)
root3 = gl.Node(children=(tri_node3, line_node3))

# Camera behind the scene, looking +Z
cam3 = gl.Camera(
    position=(0, 3, 1), orientation=(math.pi, 0, 0),
    fov=90, aspect=1.0,
)

fbo.use()
gl.render(ctx, cam3, env2, root3)
save("render3.png")
print()

print("Smoke test complete!")
