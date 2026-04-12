# pylint: disable=missing-docstring

import paimel

gl = paimel.load_module("gelpi")
window = paimel.load_module("window")

# Interleaved position (3f) + color (3f) per vertex
# Triangle in the XZ plane (vertical), facing -Y toward the camera.
TRIANGLE_VERTICES = [
     0.0, 0.0,  0.5,   1.0, 0.0, 0.0,
    -0.5, 0.0, -0.5,   0.0, 1.0, 0.0,
     0.5, 0.0, -0.5,   0.0, 0.0, 1.0,
]


def init(self):
    vbuf = gl.Buffer(self.ctx, gl.pack(TRIANGLE_VERTICES))
    geom = gl.Geometry(
        layout=(("in_position", "3f"), ("in_color", "3f")),
        primitive=gl.TRIANGLES,
        vertexBuffer=vbuf,
    )
    mat = gl.material(self.ctx, lit=False, vertexColor=True)
    self.triangle = gl.drawable(self.ctx, geom, mat)


def render(self, _time, _frame_time):
    w, h = self.wnd.buffer_size
    env = gl.Environment(
        clearColor=(0.0, 0.0, 0.0),
        time=_time,
        viewport=(0, 0, w, h),
    )
    camera = gl.Camera(
        position=(0.0, -2.0, 0.0),
        fov=45.0,
        aspect=w / h,
    )
    scene = gl.Node(
        transform=gl.Transform(rotation=(0.0, _time, 0.0)),
        drawable=self.triangle,
    )
    gl.render(self.ctx, camera, env, scene)


window.run(init=init, render=render, title="GL Window")
