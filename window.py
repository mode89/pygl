# pylint: disable=missing-docstring

import moderngl_window as mglw  # pylint: disable=import-error


def run(*, init=None, render=None, key_event=None, title="GL Window"):
    class Window(mglw.WindowConfig):
        gl_version = (4, 3)
        window_size = (800, 600)
        samples = 8

        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            if init is not None:
                init(self)

        def on_render(self, _time, _frame_time):
            if render is not None:
                render(self, _time, _frame_time)

        def on_key_event(self, key, action, modifiers):
            if key_event is not None:
                key_event(self, key, action, modifiers)

    Window.title = title
    mglw.run_window_config(Window)
