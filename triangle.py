# pylint: disable=missing-docstring

import moderngl_window as mglw # pylint: disable=import-error

import paimel
import gelpi as gl

devdoor = paimel.load_module("devdoor")

# Interleaved position (3f) + color (3f) per vertex
# Triangle in the XZ plane (vertical), facing -Y toward the camera.
TRIANGLE_VERTICES = [
     0.0, 0.0,  0.5,   1.0, 0.0, 0.0,
    -0.5, 0.0, -0.5,   0.0, 1.0, 0.0,
     0.5, 0.0, -0.5,   0.0, 0.0, 1.0,
]


class Window(mglw.WindowConfig):
    gl_version = (4, 3)
    title = "GL Window"
    window_size = (800, 600)
    samples = 8

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.devdoor = devdoor.create()
        self.should_close = False

        vbuf = gl.Buffer(self.ctx, TRIANGLE_VERTICES)
        geom = gl.Geometry(
            layout=(("in_position", "3f"), ("in_color", "3f")),
            primitive=gl.TRIANGLES,
            vertex_buffer=vbuf,
        )
        mat = gl.material(self.ctx, lit=False, vertex_color=True)
        self.triangle = gl.drawable(self.ctx, geom, mat)

    def on_close(self):
        self.devdoor.close()

    def on_render(self, _time, _frame_time):
        w, h = self.wnd.buffer_size
        env = gl.Environment(
            clear_color=(0.0, 0.0, 0.0, 1.0),
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
