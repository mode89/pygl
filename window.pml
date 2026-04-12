#! vim: ft=paimel

import time
import moderngl_window as mglw
import builtins as py

def FPS = 60

def run init:nil render:nil key_event:nil mouse_event:nil title:"GL Window" =
  let class Window [mglw.WindowConfig] = {
    def gl_version = py.tuple [4, 3]
    def window_size = py.tuple [800, 600]
    def samples = 8
    def vsync = false
    def __init__ self **kwargs = (
      mglw.WindowConfig.__init__ self $** kwargs;
      set! self._next_frame (time.perf_counter ());
      when some? init do init self
    )
    def on_render self _time _frame_time = (
      let now = time.perf_counter () in (
        when now < self._next_frame do
          time.sleep (self._next_frame - now);
        set! self._next_frame (self._next_frame + 1.0 / FPS)
      );
      when some? render do render self _time _frame_time
    )
    def on_key_event self key action modifiers =
      when some? key_event do key_event self key action modifiers
    def on_mouse_position_event self x y dx dy =
      when some? mouse_event do mouse_event self x y dx dy
  } in (
    set! Window.title title;
    mglw.run_window_config Window
  )
