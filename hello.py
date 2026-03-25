# pylint: disable=missing-docstring

import numpy as np # pylint: disable=import-error
import moderngl_window as mglw # pylint: disable=import-error
from pyrr import Matrix44 # pylint: disable=import-error

import devdoor


class Window(mglw.WindowConfig):
    gl_version = (4, 3)
    title = "GL Window"
    window_size = (800, 600)
    samples = 8

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.devdoor = devdoor.create()
        self.should_close = False

        vbo = self.ctx.buffer(np.array([
             0.0,  0.5, 0.0,   1.0, 0.0, 0.0,
            -0.5, -0.5, 0.0,   0.0, 1.0, 0.0,
             0.5, -0.5, 0.0,   0.0, 0.0, 1.0,
        ], dtype="f4"))

        self.prog = self.ctx.program(
            vertex_shader="""
                #version 430
                uniform mat4 mvp;
                in vec3 in_position;
                in vec3 in_color;
                out vec3 v_color;
                void main() {
                    gl_Position = mvp * vec4(in_position, 1.0);
                    v_color = in_color;
                }
            """,
            fragment_shader="""
                #version 430
                in vec3 v_color;
                out vec4 fragColor;
                void main() {
                    fragColor = vec4(v_color, 1.0);
                }
            """,
        )

        self.vao = self.ctx.vertex_array(self.prog, [
            (vbo, "3f 3f", "in_position", "in_color"),
        ])

    def on_close(self):
        self.devdoor.close()

    def on_render(self, _time, _frame_time):
        self.ctx.clear(0.0, 0.0, 0.0, 1.0)

        projection = Matrix44.perspective_projection(
            45.0, self.aspect_ratio, 0.1, 100.0)
        view = Matrix44.look_at(
            (0.0, 0.0, 2.0),
            (0.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
        )
        model = Matrix44.from_z_rotation(_time)
        mvp = projection * view * model

        self.prog["mvp"].write(mvp.astype("f4").tobytes())
        self.vao.render()

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
