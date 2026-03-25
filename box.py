# pylint: disable=missing-docstring

import numpy as np # pylint: disable=import-error
import moderngl_window as mglw # pylint: disable=import-error
from pyrr import Matrix44 # pylint: disable=import-error

import devdoor


# fmt: off
CUBE_VERTICES = np.array([
    # Front face
    -0.5, -0.5,  0.5,   0.5, -0.5,  0.5,   0.5,  0.5,  0.5,
    -0.5, -0.5,  0.5,   0.5,  0.5,  0.5,  -0.5,  0.5,  0.5,
    # Back face
    -0.5, -0.5, -0.5,  -0.5,  0.5, -0.5,   0.5,  0.5, -0.5,
    -0.5, -0.5, -0.5,   0.5,  0.5, -0.5,   0.5, -0.5, -0.5,
    # Top face
    -0.5,  0.5, -0.5,  -0.5,  0.5,  0.5,   0.5,  0.5,  0.5,
    -0.5,  0.5, -0.5,   0.5,  0.5,  0.5,   0.5,  0.5, -0.5,
    # Bottom face
    -0.5, -0.5, -0.5,   0.5, -0.5, -0.5,   0.5, -0.5,  0.5,
    -0.5, -0.5, -0.5,   0.5, -0.5,  0.5,  -0.5, -0.5,  0.5,
    # Right face
     0.5, -0.5, -0.5,   0.5,  0.5, -0.5,   0.5,  0.5,  0.5,
     0.5, -0.5, -0.5,   0.5,  0.5,  0.5,   0.5, -0.5,  0.5,
    # Left face
    -0.5, -0.5, -0.5,  -0.5, -0.5,  0.5,  -0.5,  0.5,  0.5,
    -0.5, -0.5, -0.5,  -0.5,  0.5,  0.5,  -0.5,  0.5, -0.5,
], dtype="f4")

CUBE_NORMALS = np.array([
    # Front face
     0.0,  0.0,  1.0,   0.0,  0.0,  1.0,   0.0,  0.0,  1.0,
     0.0,  0.0,  1.0,   0.0,  0.0,  1.0,   0.0,  0.0,  1.0,
    # Back face
     0.0,  0.0, -1.0,   0.0,  0.0, -1.0,   0.0,  0.0, -1.0,
     0.0,  0.0, -1.0,   0.0,  0.0, -1.0,   0.0,  0.0, -1.0,
    # Top face
     0.0,  1.0,  0.0,   0.0,  1.0,  0.0,   0.0,  1.0,  0.0,
     0.0,  1.0,  0.0,   0.0,  1.0,  0.0,   0.0,  1.0,  0.0,
    # Bottom face
     0.0, -1.0,  0.0,   0.0, -1.0,  0.0,   0.0, -1.0,  0.0,
     0.0, -1.0,  0.0,   0.0, -1.0,  0.0,   0.0, -1.0,  0.0,
    # Right face
     1.0,  0.0,  0.0,   1.0,  0.0,  0.0,   1.0,  0.0,  0.0,
     1.0,  0.0,  0.0,   1.0,  0.0,  0.0,   1.0,  0.0,  0.0,
    # Left face
    -1.0,  0.0,  0.0,  -1.0,  0.0,  0.0,  -1.0,  0.0,  0.0,
    -1.0,  0.0,  0.0,  -1.0,  0.0,  0.0,  -1.0,  0.0,  0.0,
], dtype="f4")
# fmt: on


class Window(mglw.WindowConfig):
    gl_version = (4, 3)
    title = "Rotating Box"
    window_size = (800, 600)
    samples = 8

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.devdoor = devdoor.create()
        self.should_close = False

        vbo_pos = self.ctx.buffer(CUBE_VERTICES)
        vbo_norm = self.ctx.buffer(CUBE_NORMALS)

        self.prog = self.ctx.program(
            vertex_shader="""
                #version 430
                uniform mat4 mvp;
                uniform mat4 model;
                in vec3 in_position;
                in vec3 in_normal;
                out vec3 v_normal;
                void main() {
                    gl_Position = mvp * vec4(in_position, 1.0);
                    v_normal = mat3(model) * in_normal;
                }
            """,
            fragment_shader="""
                #version 430
                in vec3 v_normal;
                out vec4 fragColor;
                void main() {
                    vec3 light_dir = normalize(vec3(1.0, 2.0, 3.0));
                    float diff = max(dot(normalize(v_normal), light_dir), 0.0);
                    float ambient = 0.3;
                    float brightness = ambient + diff * 0.7;
                    fragColor = vec4(vec3(brightness), 1.0);
                }
            """,
        )

        self.vao = self.ctx.vertex_array(self.prog, [
            (vbo_pos, "3f", "in_position"),
            (vbo_norm, "3f", "in_normal"),
        ])

    def on_close(self):
        self.devdoor.close()

    def on_render(self, _time, _frame_time):
        self.ctx.clear(0.0, 0.0, 0.0, 1.0)
        self.ctx.enable(self.ctx.DEPTH_TEST)

        projection = Matrix44.perspective_projection(
            45.0, self.aspect_ratio, 0.1, 100.0)
        view = Matrix44.look_at(
            (0.0, 0.0, 3.0),
            (0.0, 0.0, 0.0),
            (0.0, 1.0, 0.0),
        )
        model = Matrix44.from_y_rotation(_time) * Matrix44.from_x_rotation(_time * 0.7)
        mvp = projection * view * model

        self.prog["mvp"].write(mvp.astype("f4").tobytes())
        self.prog["model"].write(model.astype("f4").tobytes())
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
