#! vim: ft=paimel

# Provides a simple interface for interactive debugging and control of a running
# Python process via HTTP requests.

# The `create` function starts a background HTTP server on the specified port
# (default is 8000) and returns an object with two methods:
# - `exec_pending_requests(_globals=None, _locals=None)`: This method should be
#   called periodically (e.g., in the main loop of the application) to process
#   any pending devdoor requests. It executes the code received in the requests
#   within the provided global and local contexts.
# - `close()`: This method shuts down the devdoor server gracefully.

# Once the server is running, you can send HTTP POST requests to
# `http://localhost:8000/` with a body containing Python code. The server will
# execute the code and return the output or any exceptions that occur during
# execution, e.g.

# ```
# curl http://localhost:8000/ -d @- <<EOF
# print("Hello from devdoor!")
# EOF
# ```

# The server also provides a simple status endpoint `http://localhost:8000/status`
# that returns "ok" to indicate that the server is running.

import io
import queue
import threading
import traceback
import builtins as py
import concurrent.futures refer {Future}
import contextlib refer {redirect_stdout, redirect_stderr}
import http.server refer {ThreadingHTTPServer, BaseHTTPRequestHandler}

def create port:8000 =
  let requests = queue.Queue () in
  let server = ThreadingHTTPServer
    (py.tuple ["127.0.0.1", port])
    (makeHandlerClass
      fun method path headers body ->
        handleRequest requests path body)
  in
  let _ = set! server.daemon_threads true in
  let thread = threading.Thread target:server.serve_forever daemon:true in
  let _ = thread.start ()
  in {
    exec_pending_requests: fun globals locals ->
      loop _ = nil in
        try
          let req = requests.get_nowait () in (
            req globals locals;
            recur nil
          )
        except queue.Empty do nil,
    close: fun () -> (
      print "shutting down devdoor server ...";
      server.shutdown ();
      thread.join ();
      print "devdoor server stopped."
    ),
  }

def handleRequest requests path body =
  case
  | path == "/" ->
    let _ = assert "No code provided" $ some? body in
    let future = Future () in (
      requests.put $
        fun globals locals ->
          try
            let stream = io.StringIO () in
            with _out = redirect_stdout stream
            and _err = redirect_stderr stream
            do (
              py.exec body globals locals;
              future.set_result $ stream.getvalue ()
            )
          except Exception do
            future.set_result $ traceback.format_exc ();
      {body: future.result timeout:5}
    )
  | path == "/status" -> {body: "ok"}
  | _ -> {code: 404, body: "Not Found"}

def makeHandlerClass handler =
  let class Handler [BaseHTTPRequestHandler] = {
    def _handle self =
      let method = self.command in
      let path = self.path in
      let length = self.headers.get "Content-Length" 0 |> int in
      let body = when length > 0 do self.rfile.read length |.decode () in
      let response =
        try handler method path self.headers body
        except Exception do {
          code: 500,
          headers: hashMap "Content-Type" "text/plain",
          body: traceback.format_exc (),
        }
      in (
        self.send_response $ response.get "code" 200;
        for! [k, v] in response.get "headers" do
          self.send_header k v;
        self.end_headers ();
        when some? $ response.get "body" do
          self.wfile.write $ response.body.encode ()
      )
    def do_GET = _handle
    def do_POST = _handle
    def do_PUT = _handle
    def do_DELETE = _handle
  } in Handler
