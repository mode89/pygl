"""Smoke tests for minebench.py — headless rendering scenarios."""

import math
import os
from concurrent.futures import Future
import shutil

import moderngl  # pylint: disable=import-error
from PIL import Image  # pylint: disable=import-error

import minebench

TEMP_DIR = "/tmp/minebench"
shutil.rmtree(TEMP_DIR, ignore_errors=True)
os.makedirs(TEMP_DIR)

# --- Standalone context + framebuffer ---
ctx = moderngl.create_standalone_context(require=430)
W, H = 400, 300
color_att = ctx.texture((W, H), 4)
depth_att = ctx.depth_renderbuffer((W, H))
fbo = ctx.framebuffer(color_attachments=[color_att], depth_attachment=depth_att)


def drain_futures(state):
    """Keep updating chunks until all futures are resolved."""
    while any(isinstance(v, Future) for v in state.chunks.values()):
        state = minebench._update_chunks(state, ctx, max_meshes=100)
    return state


def save(name):
    raw = color_att.read()
    img = Image.frombytes("RGBA", (W, H), raw)
    img = img.transpose(Image.FLIP_TOP_BOTTOM)
    path = f"{TEMP_DIR}/{name}"
    img.save(path)
    print(f"  Saved {path}")


def render(state):
    fbo.use()
    minebench.render_frame(ctx, state, (0, 0, W, H))


Key = minebench.Key

# ============================================================
# Scenario 1: Initial render
# ============================================================
print("=" * 60)
print("SCENARIO 1: Initial render")
print("=" * 60)

minebench.RENDER_DISTANCE = 2
state = minebench.init(ctx, seed=42)
state = drain_futures(state)
p = state.player
print(f"  Player: ({p.x:.1f}, {p.y:.1f}, {p.z:.1f})")
print(f"  Yaw: {p.yaw:.3f}, Pitch: {p.pitch:.3f}")
ground = minebench._get_ground_z(state, 0, 0)
print(f"  Ground at origin: {ground}")

render(state)
save("mb_01_initial.png")
print()

# ============================================================
# Scenario 2: Walk forward
# ============================================================
print("=" * 60)
print("SCENARIO 2: Walk forward")
print("=" * 60)

state2 = state
events = [minebench.KeyPress(Key.W)]
for i in range(60):
    state2 = minebench.step(ctx, state2, events if i == 0 else [], 1.0 / 30.0)
state2 = drain_futures(state2)

p2 = state2.player
print(f"  Player after walk: ({p2.x:.1f}, {p2.y:.1f}, {p2.z:.1f})")
print(f"  Moved forward: {p2.y - p.y:.1f} blocks")

render(state2)
save("mb_02_walk.png")
print()

# ============================================================
# Scenario 3: Look around
# ============================================================
print("=" * 60)
print("SCENARIO 3: Look around")
print("=" * 60)

state3 = state
events3 = [minebench.MouseMove(300, 0)]  # yaw right
state3 = minebench.step(ctx, state3, events3, 1.0 / 30.0)
state3 = drain_futures(state3)

p3 = state3.player
print(f"  Yaw after mouse: {p3.yaw:.3f} rad ({math.degrees(p3.yaw):.1f} deg)")

render(state3)
save("mb_03_look.png")
print()

# ============================================================
# Scenario 4: Jump
# ============================================================
print("=" * 60)
print("SCENARIO 4: Jump")
print("=" * 60)

state4 = state
# Before jump
render(state4)
save("mb_04a_before_jump.png")
print(f"  Z before jump: {state4.player.z:.2f}")

# Press space
state4 = minebench.step(ctx, state4, [minebench.KeyPress(Key.SPACE)], 1.0 / 60.0)
# Run physics for ~0.4s to reach peak
for _ in range(24):
    state4 = minebench.step(ctx, state4, [], 1.0 / 60.0)
state4 = drain_futures(state4)
print(f"  Z at peak: {state4.player.z:.2f}")
render(state4)
save("mb_04b_peak.png")

# Continue falling
for _ in range(30):
    state4 = minebench.step(ctx, state4, [], 1.0 / 60.0)
state4 = drain_futures(state4)
print(f"  Z after landing: {state4.player.z:.2f}")
render(state4)
save("mb_04c_landed.png")
print()

# ============================================================
# Scenario 5: Walk far (infinite world test)
# ============================================================
print("=" * 60)
print("SCENARIO 5: Walk far (infinite world)")
print("=" * 60)

state5 = state
events5 = [minebench.KeyPress(Key.W)]
for i in range(600):
    state5 = minebench.step(ctx, state5, events5 if i == 0 else [], 1.0 / 30.0)
state5 = drain_futures(state5)

p5 = state5.player
print(f"  Player after long walk: ({p5.x:.1f}, {p5.y:.1f}, {p5.z:.1f})")
print(f"  Chunks loaded: {len(state5.chunks)}")

render(state5)
save("mb_05_far.png")
print()

# ============================================================
# Scenario 6: Look straight down
# ============================================================
print("=" * 60)
print("SCENARIO 6: Look straight down")
print("=" * 60)

state6 = state
events6 = [minebench.MouseMove(0, 5000)]  # pitch down fully
state6 = minebench.step(ctx, state6, events6, 1.0 / 60.0)
state6 = drain_futures(state6)

p6 = state6.player
print(f"  Pitch: {p6.pitch:.3f} rad ({math.degrees(p6.pitch):.1f} deg)")

render(state6)
save("mb_06_down.png")
print()

# ============================================================
# Scenario 7: Look at horizon
# ============================================================
print("=" * 60)
print("SCENARIO 7: Look at horizon")
print("=" * 60)

state7 = state
events7 = [minebench.MouseMove(0, -50)]  # slight pitch up
state7 = minebench.step(ctx, state7, events7, 1.0 / 60.0)
state7 = drain_futures(state7)

p7 = state7.player
print(f"  Pitch: {p7.pitch:.3f} rad ({math.degrees(p7.pitch):.1f} deg)")

render(state7)
save("mb_07_horizon.png")
print()

print("Smoke tests complete!")
