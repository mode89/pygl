# pylint: disable=missing-docstring

import moderngl_window as mglw # pylint: disable=import-error

import paimel

gl = paimel.load_module("gelpi")
devdoor = paimel.load_module("devdoor")


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


class Window(mglw.WindowConfig):
    gl_version = (4, 3)
    title = "Rotating Box"
    window_size = (800, 600)
    samples = 8

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.devdoor = devdoor.create()
        self.should_close = False

        vbuf = gl.Buffer(self.ctx, CUBE_VERTICES)
        geom = gl.Geometry(
            layout=(("in_position", "3f"), ("in_normal", "3f")),
            primitive=gl.TRIANGLES,
            vertexBuffer=vbuf,
        )
        mat = gl.material(self.ctx, color=(1.0, 0.0, 0.0, 1.0), lit=True)
        self.box = gl.drawable(self.ctx, geom, mat)

    def on_close(self):
        self.devdoor.close()

    def on_render(self, _time, _frame_time):
        env = gl.Environment(
            clearColor=(0.0, 0.0, 0.0, 1.0),
            time=_time,
            ambient=(0.3, 0.3, 0.3),
            viewport=(0, 0, *self.wnd.buffer_size),
            light=gl.DirectLight(
                direction=(-1.0, 3.0, -2.0),
                intensity=0.7,
            ),
        )
        w, h = self.wnd.buffer_size
        camera = gl.Camera(
            position=(0.0, -3.0, 0.0),
            fov=45.0,
            aspect=w/h,
        )
        scene = gl.Node(
            transform=gl.Transform(rotation=(_time * 0.7, 0.0, _time)),
            drawable=self.box,
        )
        gl.render(self.ctx, camera, env, scene)

        self.devdoor.exec_pending_requests(globals(), {"window": self})

        if self.should_close:
            self.wnd.close()


def _quit(window):
    window.should_close = True

def _window_size(window):
    w, h = window.wnd.buffer_size
    return w, h

def _screenshot(window):
    w, h = _window_size(window)
    return window.ctx.screen.read(
        viewport=(0, 0, w, h), components=3, alignment=1)

def _save_screenshot(window, path):
    from PIL import Image # pylint: disable=import-error,import-outside-toplevel
    w, h = _window_size(window)
    raw = _screenshot(window)
    img = Image.frombytes("RGB", (w, h), raw)
    img = img.transpose(Image.FLIP_TOP_BOTTOM)
    img.save(path, format="PNG")


if __name__ == "__main__":
    mglw.run_window_config(Window)
