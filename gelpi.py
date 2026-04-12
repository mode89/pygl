"""Minimal rendering engine built on ModernGL."""

import math
import struct
from dataclasses import dataclass, field
from typing import Optional

import moderngl  # pylint: disable=import-error
import glm  # pylint: disable=import-error

# Primitive types
TRIANGLES = moderngl.TRIANGLES
LINES = moderngl.LINES
LINE_STRIP = moderngl.LINE_STRIP
POINTS = moderngl.POINTS


# --- Frozen dataclasses ---

@dataclass(frozen=True)
class DirectLight:
    """A directional light source."""

    direction: tuple
    color: tuple = (1.0, 1.0, 1.0)
    intensity: float = 1.0


@dataclass(frozen=True)
class Environment:
    """Global rendering state: background, lighting, viewport."""

    clear_color: tuple = (0.0, 0.0, 0.0, 1.0)
    time: float = 0.0
    ambient: tuple = (0.1, 0.1, 0.1)
    viewport: tuple = (0, 0, 800, 600)
    light: Optional[DirectLight] = None
    cull_face: bool = False


@dataclass(frozen=True)
class Camera:
    """Perspective camera with position and orientation."""

    position: tuple = (0.0, 0.0, 1.0)
    orientation: tuple = (0.0, 0.0, 0.0)  # (yaw, pitch, roll) in radians
    fov: float = 60.0
    aspect: float = 1.0
    near: float = 0.1
    far: float = 100.0


@dataclass(frozen=True)
class Transform:
    """Translation, rotation, and scale for a scene node."""

    translation: tuple = (0.0, 0.0, 0.0)
    rotation: tuple = (0.0, 0.0, 0.0)  # euler angles (rx, ry, rz) in radians
    scale: tuple = (1.0, 1.0, 1.0)


# --- Mutable types ---

def pack(data):
    n = len(data)
    assert n > 0, "data must not be empty"
    ft = type(data[0])
    assert ft is int or ft is float, f"expected numeric data, got {ft}"
    return struct.pack(f"<{n}{'i' if ft is int else 'f'}", *data)


class Buffer:
    """GPU buffer wrapping a moderngl buffer object."""

    def __init__(self, ctx, data, dynamic=False):
        self._ctx = ctx
        self._buf = ctx.buffer(data, dynamic=dynamic)
        self._size_bytes = None

    @property
    def size_bytes(self):
        if self._size_bytes is not None:
            return self._size_bytes
        return self._buf.size

    @size_bytes.setter
    def size_bytes(self, value):
        self._size_bytes = value

    def update(self, data, offset=0):
        """Write raw bytes into the buffer at the given byte offset."""
        self._buf.write(data, offset=offset)

    def read(self):
        """Read back the raw buffer contents."""
        return self._buf.read()


class Texture:
    """RGBA texture backed by a moderngl texture object."""

    def __init__(self, ctx, size, data=None):
        self._ctx = ctx
        raw = bytes(data) if data is not None else None
        self._tex = ctx.texture(size, 4, data=raw)
        self._tex.filter = (moderngl.NEAREST, moderngl.NEAREST)

    def update(self, data):
        """Overwrite the texture contents."""
        self._tex.write(bytes(data))

    def read(self):
        """Read back the raw texture contents."""
        return self._tex.read()


# --- Frozen dataclasses (continued) ---

@dataclass(frozen=True)
class Geometry:
    """Vertex layout, primitive type, and associated buffers."""

    layout: tuple
    primitive: int
    vertex_buffer: Buffer
    index_buffer: Optional[Buffer] = None


@dataclass(frozen=True)
class Material:
    """Shader program, optional texture, and uniform values."""

    shader: object
    texture: Optional[Texture] = None
    uniforms: dict = field(default_factory=dict)


@dataclass(frozen=True)
class Instancing:
    """Per-instance data for GPU instancing."""

    buffer: Buffer
    layout: tuple


@dataclass(frozen=True)
class Drawable:
    """A geometry/material pair ready to render, with optional instancing."""

    geometry: Geometry
    material: Material
    instancing: Optional[Instancing] = None
    _vao: object = field(default=None, repr=False, compare=False)


@dataclass(frozen=True)
class Node:
    """Scene-graph node with transform, drawable, and children."""

    transform: Transform = field(default_factory=Transform)
    drawable: Optional[Drawable] = None
    children: tuple = ()


def drawable(ctx, geom, mat, instancing=None):
    """Create a Drawable, eagerly building its VAO."""
    vao = _build_vao(ctx, mat.shader, geom, instancing)
    return Drawable(geometry=geom, material=mat, instancing=instancing, _vao=vao)


def quad_geometry(ctx):
    """Unit quad from -0.5 to 0.5, with position, normal, and UV."""
    return Geometry(
        layout=(("in_position", "3f"), ("in_normal", "3f"), ("in_uv", "2f")),
        primitive=TRIANGLES,
        vertex_buffer=Buffer(ctx, pack([
            # position          normal       uv
            -0.5, -0.5, 0.0,   0, 0, 1,    0, 0,
             0.5, -0.5, 0.0,   0, 0, 1,    1, 0,
             0.5,  0.5, 0.0,   0, 0, 1,    1, 1,
            -0.5,  0.5, 0.0,   0, 0, 1,    0, 1,
        ])),
        index_buffer=Buffer(ctx, pack([0, 1, 2, 2, 3, 0])),
    )


def material(
        ctx,
        color=(1.0, 1.0, 1.0, 1.0),
        texture=None,
        lit=True,
        vertex_color=False
    ):
    """Convenience constructor: returns a Material with a pre-built shader."""
    if not hasattr(ctx, "_default_prog"):
        prog = ctx.program(vertex_shader=_VERT, fragment_shader=_FRAG)
        if "Gelpi" in prog:
            prog["Gelpi"].binding = 0
        ctx._default_prog = prog  # pylint: disable=protected-access
    prog = ctx._default_prog  # pylint: disable=protected-access
    if len(color) == 3:
        color = (*color, 1.0)
    return Material(
        shader=prog,
        texture=texture,
        uniforms={
            "u_color": color,
            "u_has_vertex_color": 1 if vertex_color else 0,
            "u_has_texture": 1 if texture is not None else 0,
            "u_lit": 1 if lit else 0,
        },
    )


_GELPI_UBO = """
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
"""

_VERT = "#version 430\n" + _GELPI_UBO + """
in vec3 in_position;
in vec3 in_normal;
in vec2 in_uv;
in vec4 in_color;

out vec3 v_normal;
out vec3 v_position;
out vec2 v_uv;
out vec4 v_color;

void main() {
    vec4 world_pos = model * vec4(in_position, 1.0);
    v_position = world_pos.xyz;
    v_normal = mat3(model) * in_normal;
    v_uv = in_uv;
    v_color = in_color;
    gl_Position = mvp * vec4(in_position, 1.0);
}
"""

_FRAG = "#version 430\n" + _GELPI_UBO + """
uniform vec4 u_color;
uniform int u_has_vertex_color;
uniform int u_has_texture;
uniform sampler2D u_texture;
uniform int u_lit;

in vec3 v_normal;
in vec3 v_position;
in vec2 v_uv;
in vec4 v_color;

out vec4 fragColor;

void main() {
    vec4 base_color = u_color;

    if (u_has_vertex_color != 0) {
        base_color *= v_color;
    }

    if (u_has_texture != 0) {
        base_color *= texture(u_texture, v_uv);
    }

    if (u_lit != 0) {
        vec3 lighting = ambient;
        if (has_light != 0) {
            vec3 n = normalize(v_normal);
            vec3 l = normalize(-light_direction);
            float diff = max(dot(n, l), 0.0);
            lighting += light_color * light_intensity * diff;
        }
        fragColor = vec4(base_color.rgb * lighting, base_color.a);
    } else {
        fragColor = base_color;
    }
}
"""


def particle_material(
        ctx,
        color=(1.0, 1.0, 1.0, 1.0),
        texture=None,
        vertex_color=True,
        size=1.0,
        screen_space=False
    ):
    """Convenience constructor: returns a Material for billboard particles."""
    if not hasattr(ctx, "_particle_prog"):
        prog = ctx.program(vertex_shader=_PARTICLE_VERT, fragment_shader=_FRAG)
        if "Gelpi" in prog:
            prog["Gelpi"].binding = 0
        ctx._particle_prog = prog  # pylint: disable=protected-access
    prog = ctx._particle_prog  # pylint: disable=protected-access
    if len(color) == 3:
        color = (*color, 1.0)
    return Material(
        shader=prog,
        texture=texture,
        uniforms={
            "u_color": color,
            "u_has_vertex_color": 1 if vertex_color else 0,
            "u_has_texture": 1 if texture is not None else 0,
            "u_lit": 0,
            "u_size": size,
            "u_screen_space": screen_space,
        },
    )


_PARTICLE_VERT = "#version 430\n" + _GELPI_UBO + """
uniform float u_size;
uniform bool u_screen_space;

in vec3 in_position;
in vec3 in_normal;
in vec2 in_uv;
in vec3 in_offset;
in vec3 in_color;

out vec3 v_normal;
out vec3 v_position;
out vec2 v_uv;
out vec4 v_color;

void main() {
    v_color = vec4(in_color, 1.0);
    v_normal = in_normal;
    v_uv = in_uv;

    if (u_screen_space) {
        vec4 clip = projection * view * model * vec4(in_offset, 1.0);
        clip.xy += in_position.xy * (2.0 * u_size / viewport) * clip.w;
        gl_Position = clip;
    } else {
        vec3 cam_right = vec3(view[0][0], view[1][0], view[2][0]);
        vec3 cam_up    = vec3(view[0][1], view[1][1], view[2][1]);
        vec3 world_pos = in_offset
                       + cam_right * in_position.x * u_size
                       + cam_up    * in_position.y * u_size;
        gl_Position = projection * view * model * vec4(world_pos, 1.0);
    }
    v_position = gl_Position.xyz;
}
"""


# --- Transform math ---

def _transform_matrix(t):
    """Build a 4x4 model matrix from a Transform.

    Order: T * Rz * Ry * Rx * S.
    """
    m = glm.mat4()
    m = glm.translate(m, glm.vec3(*t.translation))
    m = glm.rotate(m, t.rotation[2], glm.vec3(0, 0, 1))
    m = glm.rotate(m, t.rotation[1], glm.vec3(0, 1, 0))
    m = glm.rotate(m, t.rotation[0], glm.vec3(1, 0, 0))
    m = glm.scale(m, glm.vec3(*t.scale))
    return m


def _camera_matrices(cam):
    """Compute view and projection matrices from a Camera.

    Convention: Z-up, forward along +Y at yaw=0/pitch=0.
    Yaw rotates in the XY plane (positive = clockwise from above).
    Pitch tilts up/down (positive = look up).
    Roll rotates around the forward axis.
    """
    yaw, pitch, roll = cam.orientation
    fx = math.sin(yaw) * math.cos(pitch)
    fy = math.cos(yaw) * math.cos(pitch)
    fz = math.sin(pitch)
    target = (
        cam.position[0] + fx,
        cam.position[1] + fy,
        cam.position[2] + fz,
    )
    right_x = math.cos(yaw)
    right_y = -math.sin(yaw)
    up = (
        -right_x * math.sin(roll),
        -right_y * math.sin(roll),
        math.cos(roll),
    )
    view = glm.lookAt(glm.vec3(*cam.position), glm.vec3(*target), glm.vec3(*up))
    proj = glm.perspective(math.radians(cam.fov), cam.aspect, cam.near, cam.far)
    return view, proj


# --- UBO packing (std140 layout, 336 bytes) ---

_UBO_TAIL = struct.Struct("<2f2f3ff3fi3ff3ff")

def _pack_ubo(model, view, proj, mvp, viewport, cam_pos, time, ambient, light):
    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-positional-arguments
    # pylint: disable=too-many-locals
    vw, vh = float(viewport[2]), float(viewport[3])
    cx, cy, cz = cam_pos
    ax, ay, az = ambient
    if light:
        ldx, ldy, ldz = light.direction
        lcx, lcy, lcz = light.color
        li, hl = light.intensity, 1
    else:
        ldx, ldy, ldz = 0.0, 0.0, 0.0
        lcx, lcy, lcz = 0.0, 0.0, 0.0
        li, hl = 0.0, 0
    tail = _UBO_TAIL.pack(
        vw, vh, 0.0, 0.0,
        cx, cy, cz, time, ax, ay, az, hl,
        ldx, ldy, ldz, 0.0, lcx, lcy, lcz, li)
    return b"".join([
        model.to_bytes(), view.to_bytes(),
        proj.to_bytes(), mvp.to_bytes(), tail])


def _layout_stride(layout):
    stride = 0
    for _, fmt in layout:
        count = int(fmt[:-1])
        if fmt[-1] == "f" or fmt[-1] == "i":
            stride += count * 4
        else:
            assert False, f"unsupported format: {fmt}"
    return stride


def _build_vao(ctx, prog, geom, instancing=None):
    attrs, fmts = [], []
    for attr, fmt in geom.layout:
        if attr in prog:
            attrs.append(attr)
            fmts.append(fmt)
        else:
            fmts.append("/" + fmt)
    content = [(geom.vertex_buffer._buf, " ".join(fmts), *attrs)]  # pylint: disable=protected-access
    if instancing:
        inst_attrs, inst_fmts = [], []
        for attr, fmt in instancing.layout:
            if attr in prog:
                inst_attrs.append(attr)
                inst_fmts.append(fmt)
            else:
                inst_fmts.append("/" + fmt)
        inst_fmts[-1] += "/i"
        content.append((instancing.buffer._buf, " ".join(inst_fmts), *inst_attrs))  # pylint: disable=protected-access
    kw = {"index_buffer": geom.index_buffer._buf} if geom.index_buffer else {}  # pylint: disable=protected-access
    return ctx.vertex_array(prog, content, **kw)


# --- Render ---

def render(ctx, camera, environment, node):
    """Traverse the node tree and draw.

    The sole entry point for rendering a frame.
    """
    vp = environment.viewport
    ctx.viewport = tuple(vp)
    ctx.enable(moderngl.DEPTH_TEST)
    if environment.cull_face:
        ctx.enable(moderngl.CULL_FACE)
    else:
        ctx.disable(moderngl.CULL_FACE)

    cc = environment.clear_color
    ctx.clear(cc[0], cc[1], cc[2], cc[3] if len(cc) > 3 else 1.0)

    view, proj = _camera_matrices(camera)

    if not hasattr(ctx, "_ubo"):
        ctx._ubo = ctx.buffer(reserve=336)  # pylint: disable=protected-access
    ctx._ubo.bind_to_uniform_block(0)  # pylint: disable=protected-access

    identity = glm.mat4()
    _walk(
        ctx, node, identity,
        view, proj, camera, environment, ctx._ubo,  # pylint: disable=protected-access
    )


def _walk(ctx, node, parent_world, view, proj, camera, env, ubo):
    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-positional-arguments
    world = parent_world * _transform_matrix(node.transform)
    if node.drawable:
        _draw(node.drawable, world, view, proj, camera, env, ubo)
    for child in node.children:
        _walk(ctx, child, world, view, proj, camera, env, ubo)


def _draw(drw, world, view, proj, camera, env, ubo):
    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-positional-arguments
    prog = drw.material.shader
    mvp = proj * view * world

    ubo_data = _pack_ubo(
        world, view, proj, mvp, env.viewport,
        camera.position, env.time, env.ambient, env.light,
    )
    ubo.write(ubo_data)

    for name, value in drw.material.uniforms.items():
        if name in prog:
            prog[name].value = value


    if drw.material.texture:
        drw.material.texture._tex.use(0)  # pylint: disable=protected-access
        if "u_texture" in prog:
            prog["u_texture"].value = 0

    if drw.instancing:
        stride = _layout_stride(drw.instancing.layout)
        instances = drw.instancing.buffer.size_bytes // stride
        drw._vao.render(drw.geometry.primitive, instances=instances)  # pylint: disable=protected-access
    else:
        drw._vao.render(drw.geometry.primitive)  # pylint: disable=protected-access
