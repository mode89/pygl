# pylint: disable=missing-docstring

import enum
import math
import random
from concurrent.futures import ProcessPoolExecutor, Future
from dataclasses import dataclass, replace

import array

import paimel

gl = paimel.load_module("gelpi")
window = paimel.load_module("window")

_EXECUTOR = ProcessPoolExecutor(max_workers=16)

CHUNK_SIZE = 16
CHUNK_HEIGHT = 64
RENDER_DISTANCE = 8


class Block(enum.IntEnum):
    AIR = 0
    GRASS = 1
    DIRT = 2


class Key(enum.Enum):
    W = "w"
    A = "a"
    S = "s"
    D = "d"
    SPACE = "space"
    SHIFT = "shift"
    ESCAPE = "escape"


# --- Frozen dataclasses ---

@dataclass(frozen=True)
class Player:
    x: float
    y: float
    z: float
    vz: float
    yaw: float
    pitch: float


@dataclass(frozen=True)
class KeyPress:
    key: object


@dataclass(frozen=True)
class KeyRelease:
    key: object


@dataclass(frozen=True)
class MouseMove:
    dx: float
    dy: float


@dataclass(frozen=True)
class Chunk:
    cx: int
    cy: int
    heightmap: object    # array.array("i"), CHUNK_SIZE*CHUNK_SIZE
    blocks: object       # bytearray, CHUNK_SIZE*CHUNK_SIZE*CHUNK_HEIGHT
    drawable: object     # gl.Drawable or None or "empty"


@dataclass(frozen=True)
class State:
    player: Player
    keys: frozenset
    chunks: object       # dict[(int,int), Chunk]
    seed: int
    perm: tuple          # Perlin permutation table
    block_material: object  # shared gl.Material
    selected_block: object  # wireframe cube drawable


# --- Perlin noise (2D) ---

def _perlin_permutation(rng):
    p = list(range(256))
    rng.shuffle(p)
    return p + p


def _perlin_fade(t):
    return t * t * t * (t * (t * 6 - 15) + 10)


def _perlin_lerp(a, b, t):
    return a + t * (b - a)


def _perlin_grad(h, x, y):
    h = h & 3
    if h == 0:
        return x + y
    if h == 1:
        return -x + y
    if h == 2:
        return x - y
    return -x - y


def _perlin2d(x, y, perm):
    xi = int(math.floor(x)) & 255
    yi = int(math.floor(y)) & 255
    xf = x - math.floor(x)
    yf = y - math.floor(y)
    u = _perlin_fade(xf)
    v = _perlin_fade(yf)
    aa = perm[perm[xi] + yi]
    ab = perm[perm[xi] + yi + 1]
    ba = perm[perm[xi + 1] + yi]
    bb = perm[perm[xi + 1] + yi + 1]
    x1 = _perlin_lerp(
        _perlin_grad(aa, xf, yf),
        _perlin_grad(ba, xf - 1, yf), u)
    x2 = _perlin_lerp(
        _perlin_grad(ab, xf, yf - 1),
        _perlin_grad(bb, xf - 1, yf - 1), u)
    return _perlin_lerp(x1, x2, v)


# --- Chunk-local indexing ---

def _chunk_block_idx(lx, ly, lz):
    return (lx * CHUNK_SIZE + ly) * CHUNK_HEIGHT + lz


def _chunk_hmap_idx(lx, ly):
    return lx * CHUNK_SIZE + ly


# --- World generation ---

def generate_chunk_heightmap(cx, cy, perm):
    scale = 0.05
    hmap = array.array("i", [0]) * (CHUNK_SIZE * CHUNK_SIZE)
    for lx in range(CHUNK_SIZE):
        for ly in range(CHUNK_SIZE):
            wx = cx * CHUNK_SIZE + lx
            wy = cy * CHUNK_SIZE + ly
            n = _perlin2d(wx * scale, wy * scale, perm)
            hmap[_chunk_hmap_idx(lx, ly)] = int(round(n * 10 + 20))
    return hmap


def generate_chunk_blocks(heightmap):
    blocks = bytearray(CHUNK_SIZE * CHUNK_SIZE * CHUNK_HEIGHT)
    for lx in range(CHUNK_SIZE):
        for ly in range(CHUNK_SIZE):
            h = heightmap[_chunk_hmap_idx(lx, ly)]
            for z in range(max(0, min(h - 1, CHUNK_HEIGHT))):
                blocks[_chunk_block_idx(lx, ly, z)] = Block.DIRT
            if 0 <= h - 1 < CHUNK_HEIGHT:
                blocks[_chunk_block_idx(lx, ly, h - 1)] = Block.GRASS
    return blocks


def generate_chunk(cx, cy, perm):
    heightmap = generate_chunk_heightmap(cx, cy, perm)
    blocks = generate_chunk_blocks(heightmap)
    return Chunk(
        cx=cx, cy=cy,
        heightmap=heightmap, blocks=blocks, drawable=None)


def _is_solid(blocks, lx, ly, lz):
    if not (0 <= lx < CHUNK_SIZE
            and 0 <= ly < CHUNK_SIZE
            and 0 <= lz < CHUNK_HEIGHT):
        return False
    return blocks[_chunk_block_idx(lx, ly, lz)] != Block.AIR


# Face definitions: (dx, dy, dz, normal, vertices)
# Each vertex is (ox, oy, oz) offset from block origin
_FACES = [
    # +X face
    (1, 0, 0, (1.0, 0.0, 0.0), [
        (1, 0, 0), (1, 1, 0), (1, 1, 1),
        (1, 0, 0), (1, 1, 1), (1, 0, 1),
    ]),
    # -X face
    (-1, 0, 0, (-1.0, 0.0, 0.0), [
        (0, 1, 0), (0, 0, 0), (0, 0, 1),
        (0, 1, 0), (0, 0, 1), (0, 1, 1),
    ]),
    # +Y face
    (0, 1, 0, (0.0, 1.0, 0.0), [
        (1, 1, 0), (0, 1, 0), (0, 1, 1),
        (1, 1, 0), (0, 1, 1), (1, 1, 1),
    ]),
    # -Y face
    (0, -1, 0, (0.0, -1.0, 0.0), [
        (0, 0, 0), (1, 0, 0), (1, 0, 1),
        (0, 0, 0), (1, 0, 1), (0, 0, 1),
    ]),
    # +Z face (top)
    (0, 0, 1, (0.0, 0.0, 1.0), [
        (0, 0, 1), (1, 0, 1), (1, 1, 1),
        (0, 0, 1), (1, 1, 1), (0, 1, 1),
    ]),
    # -Z face (bottom)
    (0, 0, -1, (0.0, 0.0, -1.0), [
        (0, 1, 0), (1, 1, 0), (1, 0, 0),
        (0, 1, 0), (1, 0, 0), (0, 0, 0),
    ]),
]


def build_chunk_mesh(chunk, seed):  # pylint: disable=too-many-locals
    rng = random.Random(f"{seed},{chunk.cx},{chunk.cy}")
    wx0 = chunk.cx * CHUNK_SIZE
    wy0 = chunk.cy * CHUNK_SIZE
    blocks = chunk.blocks
    verts = []

    def block_color(btype, is_top):
        if btype == Block.GRASS:
            return (0.3, 0.8, 0.2) if is_top else (0.3, 0.6, 0.1)
        return (0.55, 0.35, 0.15)

    def emit_block(lx, ly, lz, btype):  # pylint: disable=too-many-locals
        boff = rng.uniform(-0.08, 0.08)
        wx = wx0 + lx
        wy = wy0 + ly
        for fdx, fdy, fdz, normal, fv in _FACES:
            if _is_solid(blocks, lx + fdx, ly + fdy, lz + fdz):
                continue
            base = block_color(btype, fdz == 1)
            color = tuple(
                max(0.0, min(1.0, c + boff)) for c in base
            )
            for ox, oy, oz in fv:
                verts.extend([
                    float(wx + ox), float(wy + oy),
                    float(lz + oz),
                    normal[0], normal[1], normal[2],
                    color[0], color[1], color[2],
                ])

    for lx in range(CHUNK_SIZE):
        for ly in range(CHUNK_SIZE):
            h = chunk.heightmap[_chunk_hmap_idx(lx, ly)]
            for lz in range(min(h, CHUNK_HEIGHT)):
                btype = blocks[_chunk_block_idx(lx, ly, lz)]
                if btype != Block.AIR:
                    emit_block(lx, ly, lz, btype)
    return gl.pack(verts) if verts else b""


def _generate_and_mesh(cx, cy, perm, seed):
    chunk = generate_chunk(cx, cy, perm)
    verts = build_chunk_mesh(chunk, seed)
    return (chunk, verts)


# --- Core functions ---

def _get_ground_z(state, x, y):
    ix = int(math.floor(x))
    iy = int(math.floor(y))
    cx = _world_to_chunk(ix)
    cy = _world_to_chunk(iy)
    entry = state.chunks.get((cx, cy))
    if isinstance(entry, Chunk):
        lx = ix - cx * CHUNK_SIZE
        ly = iy - cy * CHUNK_SIZE
        return float(entry.heightmap[_chunk_hmap_idx(lx, ly)])
    # Future or absent — generate heightmap on the fly (cheap)
    perm = state.perm
    scale = 0.05
    n = _perlin2d(ix * scale, iy * scale, perm)
    return float(int(round(n * 10 + 20)))


def _world_to_chunk(v):
    iv = int(math.floor(v))
    if iv >= 0:
        return iv // CHUNK_SIZE
    return -(-iv // CHUNK_SIZE) - (1 if iv % CHUNK_SIZE != 0 else 0)


def _player_look_dir(player):
    return (
        math.sin(player.yaw) * math.cos(player.pitch),
        math.cos(player.yaw) * math.cos(player.pitch),
        math.sin(player.pitch),
    )


def _get_block_at(state, wx, wy, wz):
    if wz < 0 or wz >= CHUNK_HEIGHT:
        return Block.AIR
    cx = _world_to_chunk(wx)
    cy = _world_to_chunk(wy)
    entry = state.chunks.get((cx, cy))
    if not isinstance(entry, Chunk):
        return Block.AIR
    lx = wx - cx * CHUNK_SIZE
    ly = wy - cy * CHUNK_SIZE
    return entry.blocks[_chunk_block_idx(lx, ly, wz)]


def _raycast(state, origin, direction, max_dist=64.0):
    ox, oy, oz = origin
    dx, dy, dz = direction

    bx = int(math.floor(ox))
    by = int(math.floor(oy))
    bz = int(math.floor(oz))

    sx = 1 if dx > 0 else -1
    sy = 1 if dy > 0 else -1
    sz = 1 if dz > 0 else -1

    INF = float("inf")

    if dx != 0:
        t_max_x = ((bx + (1 if dx > 0 else 0)) - ox) / dx
        t_delta_x = abs(1.0 / dx)
    else:
        t_max_x = INF
        t_delta_x = INF

    if dy != 0:
        t_max_y = ((by + (1 if dy > 0 else 0)) - oy) / dy
        t_delta_y = abs(1.0 / dy)
    else:
        t_max_y = INF
        t_delta_y = INF

    if dz != 0:
        t_max_z = ((bz + (1 if dz > 0 else 0)) - oz) / dz
        t_delta_z = abs(1.0 / dz)
    else:
        t_max_z = INF
        t_delta_z = INF

    dist = 0.0
    while dist < max_dist:
        if _get_block_at(state, bx, by, bz) != Block.AIR:
            return (bx, by, bz)
        if t_max_x < t_max_y:
            if t_max_x < t_max_z:
                bx += sx
                dist = t_max_x
                t_max_x += t_delta_x
            else:
                bz += sz
                dist = t_max_z
                t_max_z += t_delta_z
        else:
            if t_max_y < t_max_z:
                by += sy
                dist = t_max_y
                t_max_y += t_delta_y
            else:
                bz += sz
                dist = t_max_z
                t_max_z += t_delta_z
    return None


def _make_wireframe_drawable(ctx):
    edges = [
        (0, 0, 0, 1, 0, 0), (1, 0, 0, 1, 1, 0),
        (1, 1, 0, 0, 1, 0), (0, 1, 0, 0, 0, 0),
        (0, 0, 1, 1, 0, 1), (1, 0, 1, 1, 1, 1),
        (1, 1, 1, 0, 1, 1), (0, 1, 1, 0, 0, 1),
        (0, 0, 0, 0, 0, 1), (1, 0, 0, 1, 0, 1),
        (1, 1, 0, 1, 1, 1), (0, 1, 0, 0, 1, 1),
    ]
    verts = []
    for e in edges:
        verts.extend([float(v) for v in e])
    vbuf = gl.Buffer(ctx, gl.pack(verts))
    geom = gl.Geometry(
        layout=(("in_position", "3f"),),
        primitive=gl.LINES,
        vertexBuffer=vbuf,
    )
    mat = gl.material(ctx, color=(1.0, 1.0, 1.0, 1.0), lit=False)
    return gl.drawable(ctx, geom, mat)


def _update_chunks(state, ctx, max_meshes=16):
    pcx = _world_to_chunk(state.player.x)
    pcy = _world_to_chunk(state.player.y)
    chunks = state.chunks

    def upload_mesh(verts):
        if not verts:
            return "empty"
        vbuf = gl.Buffer(ctx, verts)
        geom = gl.Geometry(
            layout=(
                ("in_position", "3f"),
                ("in_normal", "3f"),
                ("in_color", "3f")
            ),
            primitive=gl.TRIANGLES,
            vertexBuffer=vbuf,
        )
        return gl.drawable(ctx, geom, state.block_material)

    def unload_far():
        unload_dist = RENDER_DISTANCE + 1
        to_remove = [
            key for key in chunks
            if (key[0] - pcx) ** 2 + (key[1] - pcy) ** 2
            > unload_dist * unload_dist
        ]
        if not to_remove:
            return chunks
        result = dict(chunks)
        for key in to_remove:
            entry = result.pop(key)
            if isinstance(entry, Future):
                entry.cancel()
        return result

    def collect_futures():
        uploaded = 0
        changed = False
        result = chunks
        for key, entry in list(chunks.items()):
            if not isinstance(entry, Future) or not entry.done():
                continue
            if uploaded >= max_meshes:
                break
            chunk, verts = entry.result()
            if not changed:
                result = dict(chunks)
                changed = True
            result[key] = replace(chunk, drawable=upload_mesh(verts))
            uploaded += 1
        return result

    def submit_missing():
        missing = sorted(
            (dx * dx + dy * dy, (pcx + dx, pcy + dy))
            for dx in range(-RENDER_DISTANCE, RENDER_DISTANCE + 1)
            for dy in range(-RENDER_DISTANCE, RENDER_DISTANCE + 1)
            if dx * dx + dy * dy <= RENDER_DISTANCE * RENDER_DISTANCE
            and (pcx + dx, pcy + dy) not in chunks
        )
        if not missing:
            return chunks
        result = dict(chunks)
        for _, key in missing:
            result[key] = _EXECUTOR.submit(
                _generate_and_mesh,
                key[0], key[1], state.perm, state.seed)
        return result

    chunks = unload_far()
    chunks = collect_futures()
    chunks = submit_missing()
    return replace(state, chunks=chunks)


def init(ctx, seed=None):
    if seed is None:
        seed = random.randint(0, 2**32 - 1)
    rng = random.Random(seed)
    perm = tuple(_perlin_permutation(rng))
    mat = gl.material(ctx, lit=True, vertexColor=True)

    px = 0.0
    py = 0.0

    player = Player(
        x=px, y=py, z=22.0,
        vz=0.0, yaw=0.0, pitch=0.0,
    )

    selected_block = _make_wireframe_drawable(ctx)

    state = State(
        player=player,
        keys=frozenset(),
        chunks={},
        seed=seed,
        perm=perm,
        block_material=mat,
        selected_block=selected_block,
    )

    # Submit initial chunks asynchronously
    state = _update_chunks(state, ctx)

    # Player Z from Perlin fallback (chunks still in flight)
    ground_z = _get_ground_z(state, px, py)
    player = replace(state.player, z=ground_z + 1.7)
    state = replace(state, player=player)

    return state


def step(ctx, state, events, dt):
    # pylint: disable=too-many-locals
    # pylint: disable=too-many-statements
    player = state.player

    def process_events():
        keys = state.keys
        mdx = 0.0
        mdy = 0.0
        for event in events:
            if isinstance(event, KeyPress):
                keys = keys | {event.key}
            elif isinstance(event, KeyRelease):
                keys = keys - {event.key}
            elif isinstance(event, MouseMove):
                mdx += event.dx
                mdy += event.dy
        return keys, mdx, mdy

    def apply_look(yaw, pitch, mdx, mdy):
        sensitivity = 0.002
        yaw += mdx * sensitivity
        pitch -= mdy * sensitivity
        pitch = max(
            math.radians(-89.999),
            min(math.radians(89.999), pitch))
        return yaw, pitch

    def apply_movement(yaw, keys):
        speed = 20.0 if Key.SHIFT in keys else 5.0
        fwd_x = math.sin(yaw)
        fwd_y = math.cos(yaw)
        rgt_x = math.cos(yaw)
        rgt_y = -math.sin(yaw)
        dx = 0.0
        dy = 0.0
        if Key.W in keys:
            dx += fwd_x
            dy += fwd_y
        if Key.S in keys:
            dx -= fwd_x
            dy -= fwd_y
        if Key.A in keys:
            dx -= rgt_x
            dy -= rgt_y
        if Key.D in keys:
            dx += rgt_x
            dy += rgt_y
        length = math.sqrt(dx * dx + dy * dy)
        if length > 0:
            dx = dx / length * speed * dt
            dy = dy / length * speed * dt
        return player.x + dx, player.y + dy

    def apply_physics(px, py, keys):
        ground_z = _get_ground_z(state, px, py) + 1.7
        on_ground = player.z <= ground_z + 0.001
        vz = player.vz
        if Key.SPACE in keys and on_ground:
            vz = 20.0
        vz -= 20.0 * dt
        pz = player.z + vz * dt
        if pz <= ground_z:
            pz = ground_z
            vz = 0.0
        return pz, vz

    keys, mdx, mdy = process_events()
    yaw, pitch = apply_look(player.yaw, player.pitch, mdx, mdy)
    px, py = apply_movement(yaw, keys)
    pz, vz = apply_physics(px, py, keys)

    new_player = Player(
        x=px, y=py, z=pz, vz=vz, yaw=yaw, pitch=pitch)
    state = replace(state, player=new_player, keys=keys)
    state = _update_chunks(state, ctx)
    return state


def render_frame(ctx, state, viewport):
    w, h = viewport[2], viewport[3]
    p = state.player

    camera = gl.Camera(
        position=(p.x, p.y, p.z),
        orientation=(p.yaw, p.pitch, 0.0),
        fov=60.0,
        aspect=w / h if h > 0 else 1.0,
        near=0.1,
        far=300.0,
    )

    env = gl.Environment(
        clearColor=(0.53, 0.81, 0.92, 1.0),
        ambient=(0.3, 0.3, 0.3),
        viewport=viewport,
        light=gl.DirectLight(
            direction=(0.5, -1.0, -0.3),
            color=(1.0, 1.0, 1.0),
            intensity=1.0,
        ),
        cullFace=True,
    )

    children = []
    for entry in state.chunks.values():
        if not isinstance(entry, Chunk):
            continue
        if entry.drawable is not None and entry.drawable != "empty":
            children.append(gl.Node(drawable=entry.drawable))

    hit = _raycast(state, (p.x, p.y, p.z), _player_look_dir(p))
    if hit is not None:
        pad = 0.002
        size = 1.0 + 2 * pad
        children.append(gl.Node(
            transform=gl.Transform(
                translation=(hit[0] - pad, hit[1] - pad, hit[2] - pad),
                scale=(size, size, size),
            ),
            drawable=state.selected_block,
        ))

    scene = gl.Node(children=tuple(children))
    gl.render(ctx, camera, env, scene)


# --- Window ---


def _translate_key(wnd, key):
    keys = wnd.keys
    mapping = {
        keys.W: Key.W, keys.A: Key.A,
        keys.S: Key.S, keys.D: Key.D,
        keys.SPACE: Key.SPACE,
    }
    return mapping.get(key)


def _window_init(self):
    self.wnd.mouse_exclusivity = True
    self.ctx.gc_mode = "auto"
    self.state = init(self.ctx, 0)
    self.pending = []


def _window_key_event(self, key, action, _modifiers):
    keys = self.wnd.keys
    if action == keys.ACTION_PRESS and key == keys.ESCAPE:
        self.wnd.close()
        return

    if key in (keys.LEFT_SHIFT, keys.RIGHT_SHIFT):
        mapped = Key.SHIFT
    else:
        mapped = _translate_key(self.wnd, key)
    if mapped is None:
        return

    if action == keys.ACTION_PRESS:
        self.pending.append(KeyPress(mapped))
    elif action == keys.ACTION_RELEASE:
        self.pending.append(KeyRelease(mapped))


def _window_mouse_event(self, _x, _y, dx, dy):
    self.pending.append(MouseMove(dx, dy))


def _window_render(self, _time, frame_time):
    print(f"Frame time: {frame_time * 1000:.2f} ms")
    dt = min(frame_time, 0.05)  # cap dt to avoid physics explosions
    self.state = step(self.ctx, self.state, self.pending, dt)
    self.pending.clear()

    w, h = self.wnd.buffer_size
    render_frame(self.ctx, self.state, (0, 0, w, h))


if __name__ == "__main__":
    window.run(
        init=_window_init,
        render=_window_render,
        key_event=_window_key_event,
        mouse_event=_window_mouse_event,
        title="minebench",
    )
