# pylint: disable=missing-docstring

import paimel

gl = paimel.load_module("gelpi")
window = paimel.load_module("window")

# Interleaved position (3f) + normal (3f) per vertex
CUBE_VERTICES = [
    # Front face
    -0.5, -0.5,  0.5,   0.0,  0.0,  1.0,
     0.5, -0.5,  0.5,   0.0,  0.0,  1.0,
     0.5,  0.5,  0.5,   0.0,  0.0,  1.0,
    -0.5, -0.5,  0.5,   0.0,  0.0,  1.0,
     0.5,  0.5,  0.5,   0.0,  0.0,  1.0,
    -0.5,  0.5,  0.5,   0.0,  0.0,  1.0,
    # Back face
    -0.5, -0.5, -0.5,   0.0,  0.0, -1.0,
    -0.5,  0.5, -0.5,   0.0,  0.0, -1.0,
     0.5,  0.5, -0.5,   0.0,  0.0, -1.0,
    -0.5, -0.5, -0.5,   0.0,  0.0, -1.0,
     0.5,  0.5, -0.5,   0.0,  0.0, -1.0,
     0.5, -0.5, -0.5,   0.0,  0.0, -1.0,
    # Top face
    -0.5,  0.5, -0.5,   0.0,  1.0,  0.0,
    -0.5,  0.5,  0.5,   0.0,  1.0,  0.0,
     0.5,  0.5,  0.5,   0.0,  1.0,  0.0,
    -0.5,  0.5, -0.5,   0.0,  1.0,  0.0,
     0.5,  0.5,  0.5,   0.0,  1.0,  0.0,
     0.5,  0.5, -0.5,   0.0,  1.0,  0.0,
    # Bottom face
    -0.5, -0.5, -0.5,   0.0, -1.0,  0.0,
     0.5, -0.5, -0.5,   0.0, -1.0,  0.0,
     0.5, -0.5,  0.5,   0.0, -1.0,  0.0,
    -0.5, -0.5, -0.5,   0.0, -1.0,  0.0,
     0.5, -0.5,  0.5,   0.0, -1.0,  0.0,
    -0.5, -0.5,  0.5,   0.0, -1.0,  0.0,
    # Right face
     0.5, -0.5, -0.5,   1.0,  0.0,  0.0,
     0.5,  0.5, -0.5,   1.0,  0.0,  0.0,
     0.5,  0.5,  0.5,   1.0,  0.0,  0.0,
     0.5, -0.5, -0.5,   1.0,  0.0,  0.0,
     0.5,  0.5,  0.5,   1.0,  0.0,  0.0,
     0.5, -0.5,  0.5,   1.0,  0.0,  0.0,
    # Left face
    -0.5, -0.5, -0.5,  -1.0,  0.0,  0.0,
    -0.5, -0.5,  0.5,  -1.0,  0.0,  0.0,
    -0.5,  0.5,  0.5,  -1.0,  0.0,  0.0,
    -0.5, -0.5, -0.5,  -1.0,  0.0,  0.0,
    -0.5,  0.5,  0.5,  -1.0,  0.0,  0.0,
    -0.5,  0.5, -0.5,  -1.0,  0.0,  0.0,
]


def init(self):
    vbuf = gl.Buffer(self.ctx, gl.pack(CUBE_VERTICES))
    geom = gl.Geometry(
        layout=(("in_position", "3f"), ("in_normal", "3f")),
        primitive=gl.Primitive.Triangles,
        vertexBuffer=vbuf,
    )
    mat = gl.material(self.ctx, color=(1.0, 0.0, 0.0, 1.0), lit=True)
    self.box = gl.drawable(self.ctx, geom, mat)


def render(self, _time, _frame_time):
    w, h = self.wnd.buffer_size
    env = gl.Environment(
        clearColor=(0.0, 0.0, 0.0, 1.0),
        time=_time,
        ambient=(0.3, 0.3, 0.3),
        viewport=(0, 0, w, h),
        light=gl.DirectLight(
            direction=(-1.0, 3.0, -2.0),
            intensity=0.7,
        ),
    )
    camera = gl.Camera(
        position=(0.0, -3.0, 0.0),
        fov=45.0,
        aspect=w / h,
    )
    scene = gl.Node(
        transform=gl.Transform(rotation=(_time * 0.7, 0.0, _time)),
        drawable=self.box,
    )
    gl.render(self.ctx, camera, env, scene)


window.run(init=init, render=render, title="Rotating Box")
