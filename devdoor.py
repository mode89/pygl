# pylint: disable=missing-docstring

"""
Provides a simple interface for interactive debugging and control of a running
Python process via HTTP requests.

The `create` function starts a background HTTP server on the specified port
(default is 8000) and returns an object with two methods:
- `exec_pending_requests(_globals=None, _locals=None)`: This method should be
  called periodically (e.g., in the main loop of the application) to process
  any pending devdoor requests. It executes the code received in the requests
  within the provided global and local contexts.
- `close()`: This method shuts down the devdoor server gracefully.

Once the server is running, you can send HTTP POST requests to
`http://localhost:8000/` with a body containing Python code. The server will
execute the code and return the output or any exceptions that occur during
execution, e.g.

```
curl http://localhost:8000/ -d @- <<EOF
print("Hello from devdoor!")
EOF
```

The server also provides a simple status endpoint `http://localhost:8000/status`
that returns "ok" to indicate that the server is running.
"""

import io
import queue
import threading
from concurrent.futures import Future
from contextlib import redirect_stdout, redirect_stderr
from http.server import ThreadingHTTPServer, BaseHTTPRequestHandler
import traceback
from types import SimpleNamespace

def create(port=8000):
    requests = queue.Queue()
    server = ThreadingHTTPServer(
        ("127.0.0.1", port),
        _make_handler_class(
            lambda _method, path, _headers, body:
                _handler(requests, path, body)))
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    def poll():
        while True:
            try:
                yield requests.get_nowait()
            except queue.Empty:
                break

    def exec_(_globals=None, _locals=None):
        for req in poll():
            req(_globals, _locals)

    def close():
        print("shutting down devdoor server ...")
        server.shutdown()
        thread.join()
        print("devdoor server stopped.")

    return SimpleNamespace(
        exec_pending_requests=exec_,
        close=close,
    )

def _handler(requests, path, body):
    if path == "/":
        assert body is not None, "No code provided"

        future = Future()
        def _exec(_globals=None, _locals=None):
            try:
                stream = io.StringIO()
                with redirect_stdout(stream), redirect_stderr(stream):
                    exec(body, _globals, _locals) # pylint: disable=exec-used
                future.set_result(stream.getvalue())
            except Exception: # pylint: disable=broad-except
                future.set_result(traceback.format_exc())

        requests.put(_exec)

        data = future.result(timeout=5)

        return {
            "code": 200,
            "body": data,
        }

    if path == "/status":
        return {
            "code": 200,
            "body": "ok",
        }

    return {
        "code": 404,
        "body": "Not Found",
    }


def _make_handler_class(handler):

    class Handler(BaseHTTPRequestHandler):

        def _handle(self):
            method = self.command
            path = self.path
            headers = dict(self.headers)
            length = int(headers.get("Content-Length", 0))
            body = self.rfile.read(length).decode() if length else None

            try:
                response = handler(method, path, headers, body)
            except Exception: # pylint: disable=broad-except
                response = {
                    "code": 500,
                    "headers": {"Content-Type": "text/plain"},
                    "body": traceback.format_exc(),
                }

            self.send_response(response.get("code", 200))
            for k, v in response.get("headers", {}).items():
                self.send_header(k, v)
            self.end_headers()
            if "body" in response:
                self.wfile.write(response["body"].encode())

        do_GET = _handle
        do_POST = _handle
        do_PUT = _handle
        do_DELETE = _handle

    return Handler
