# pylint: disable=missing-docstring

import time

import moderngl_window as mglw  # pylint: disable=import-error

FPS = 60


def run(*, init=None, render=None, key_event=None, title="GL Window"):
    class Window(mglw.WindowConfig):
        gl_version = (4, 3)
        window_size = (800, 600)
        samples = 8
        vsync = False

        def __init__(self, **kwargs):
            super().__init__(**kwargs)
            self._next_frame = time.perf_counter()
            if init is not None:
                init(self)

        def on_render(self, _time, _frame_time):
            if render is not None:
                render(self, _time, _frame_time)

            # Cap frame rate
            now = time.perf_counter()
            if now < self._next_frame:
                time.sleep(self._next_frame - now)
            self._next_frame += 1.0 / FPS

        def on_key_event(self, key, action, modifiers):
            if key_event is not None:
                key_event(self, key, action, modifiers)

    Window.title = title
    mglw.run_window_config(Window)
