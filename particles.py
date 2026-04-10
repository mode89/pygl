# pylint: disable=missing-docstring

import math
import random
import struct
from types import SimpleNamespace

import glm  # pylint: disable=import-error

import window
import paimel

gl = paimel.load_module("gelpi")

# Constants
MAX_PARTICLES = 200
SPAWN_RATE = 100  # particles per second
LIFETIME = 1.0
GRAVITY = -9.8
WORLD_SIZE = 0.1
SCREEN_SIZE = 20.0

# Colors to lerp between
COLOR_YELLOW = (1.0, 0.9, 0.3)
COLOR_ORANGE = (1.0, 0.3, 0.0)

INSTANCE_STRIDE = 24  # 6 floats * 4 bytes (3f pos + 3f color)


def init(self):
    self.particles = Particles()
    self.screen_space = False

    geom = gl.quadGeometry(self.ctx)

    # Dynamic instance buffer
    self.instance_buf = gl.Buffer(
        self.ctx, [0.0] * MAX_PARTICLES * 6, dynamic=True,
    )
    self.instance_buf.setSizeBytes(0)

    instancing = gl.Instancing(
        buffer=self.instance_buf,
        layout=(("in_offset", "3f"), ("in_color", "3f")),
    )
    world_mat = gl.particleMaterial(self.ctx, size=WORLD_SIZE)
    self.world_drawable = gl.drawable(self.ctx, geom, world_mat, instancing)

    screen_mat = gl.particleMaterial(
        self.ctx, size=SCREEN_SIZE, screenSpace=True,
    )
    self.screen_drawable = gl.drawable(
        self.ctx, geom, screen_mat, instancing,
    )


def render(self, _time, _frame_time):
    w, h = self.wnd.buffer_size
    aspect = w / h

    # Update simulation
    self.particles.update(_frame_time)

    env = gl.Environment(
        clearColor=(0.05, 0.02, 0.05, 1.0),
        time=_time,
        viewport=(0, 0, w, h),
    )
    camera = gl.Camera(
        position=(0.0, -3.0, 3.0),
        orientation=(0.0, -0.1, 0.0),
        fov=90.0,
        aspect=aspect,
    )

    # Upload instance data
    count = self.particles.count
    if count > 0:
        self.instance_buf.updateBytes(self.particles.pack())
    self.instance_buf.setSizeBytes(count * INSTANCE_STRIDE)

    drw = self.screen_drawable if self.screen_space else self.world_drawable
    gl.render(self.ctx, camera, env, gl.Node(drawable=drw))


def key_event(self, key, action, _modifiers):
    if action == self.wnd.keys.ACTION_PRESS and key == self.wnd.keys.SPACE:
        self.screen_space = not self.screen_space


class Particles:
    """Pure-Python particle fountain simulation."""

    def __init__(self):
        self.count = 0
        self.ps = [_particle() for _ in range(MAX_PARTICLES)]

    def update(self, dt):
        ps = self.ps

        # Update alive particles
        i = 0
        count = self.count
        while i < count:
            p = ps[i]
            p.age += dt
            if p.age >= LIFETIME:
                # Swap-remove with last alive
                count -= 1
                ps[i], ps[count] = ps[count], ps[i]
                continue
            p.velocity.z += GRAVITY * dt
            p.pos += p.velocity * dt
            i += 1
        self.count = count

        # Spawn new particles (Poisson-distributed to randomise count
        # while preserving the average spawn rate)
        to_spawn = min(_poisson(SPAWN_RATE * dt), MAX_PARTICLES - count)
        for i in range(to_spawn):
            p = ps[count + i]
            t = random.random()
            p.pos = glm.vec3(0.0)
            p.velocity = glm.vec3(
                random.uniform(-2.0, 2.0),
                random.uniform(-2.0, 2.0),
                random.uniform(6.0, 10.0),
            )
            p.age = 0.0
            p.color = glm.mix(
                glm.vec3(*COLOR_YELLOW),
                glm.vec3(*COLOR_ORANGE),
                t,
            )
        self.count = count + to_spawn

    def pack(self):
        """Pack alive particles into bytes (3f pos + 3f color per particle)."""
        n = self.count
        if n == 0:
            return b""
        ps = self.ps
        buf = bytearray(n * 24)  # 6 floats * 4 bytes
        offset = 0
        for i in range(n):
            p = ps[i]
            struct.pack_into("<6f", buf, offset, *p.pos, *p.color)
            offset += 24
        return bytes(buf)


def _poisson(mean):
    L = math.exp(-mean)  # pylint: disable=invalid-name
    k = 0
    p = 1.0
    while p > L:
        k += 1
        p *= random.random()
    return k - 1


def _particle():
    return SimpleNamespace(
        pos=glm.vec3(0.0),
        velocity=glm.vec3(0.0),
        color=glm.vec3(0.0),
        age=0.0,
    )


window.run(
    init=init, render=render, key_event=key_event,
    title="Particle Fountain",
)
