"""Loopback-only one-download fixture for a reviewed installed App SDK probe.

No account, provider requests, auth data, upload or generation. Run explicitly;
this does not change installed browser policies or register an OpenCLI adapter.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from io import BytesIO
from pathlib import Path
from PIL import Image
import argparse
import hashlib
import json
import socketserver
import threading
import time
import uuid


class LoopbackServer(ThreadingHTTPServer):
    def server_bind(self):
        # HTTPServer.server_bind reverse-resolves the host with getfqdn, a blocking
        # DNS PTR query that can stall startup on CI resolvers. Loopback needs no name.
        socketserver.TCPServer.server_bind(self)
        self.server_name, self.server_port = self.server_address[:2]


def serve(directory):
    root = Path(directory)
    root.mkdir(mode=0o700, parents=True, exist_ok=False)
    nonce = uuid.uuid4().hex
    filename = "atm-xyq-sdk-fixture-" + nonce + ".png"
    output = BytesIO()
    Image.new("RGB", (81, 108), "blue").save(output, format="PNG")
    payload = output.getvalue()
    state = {"fixture_id": nonce, "filename": filename,
             "image_sha256": hashlib.sha256(payload).hexdigest(),
             "download_requests": 0, "provider_called": False}
    state_lock = threading.Lock()
    html = ("""<!doctype html><html lang="zh"><head><meta charset="utf-8">
<title>ATM 本机下载事件验收</title><style>
body{font:20px system-ui;max-width:800px;margin:60px auto;line-height:1.6;
background:#f5f7fb;color:#17243b}main{background:white;padding:32px;border-radius:18px}
button{padding:14px 22px;border:0;border-radius:9px;background:#3469db;color:white;font:inherit}
code{font-size:13px;word-break:break-all}</style></head><body><main>
<h1>ATM 本机下载事件验收</h1>
<p>只下载本机合成蓝色 PNG（81 × 108）。不访问小云雀、不使用账号、不消费积分。</p>
<button id="download">下载本机测试 PNG</button>
<p id="count" role="status">下载点击次数：0</p><code>FILENAME</code>
<script>let n=0;document.querySelector('#download').addEventListener('click',()=>{
n++;document.querySelector('#count').textContent='下载点击次数：'+n;
if(n===1)location.href='/FILENAME';});</script></main></body></html>""").replace("FILENAME", filename).encode()

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(3)

        def log_message(self, *args):
            pass  # Fixture requests carry no diagnostic or account content.

        def do_GET(self):
            if self.path == "/":
                content, mime, code = html, "text/html; charset=utf-8", 200
            elif self.path == "/status":
                with state_lock:
                    content = json.dumps(state).encode()
                mime, code = "application/json", 200
            elif self.path == "/" + filename:
                with state_lock:
                    state["download_requests"] += 1
                    first = state["download_requests"] == 1
                if first:
                    content, mime, code = payload, "image/png", 200
                else:
                    content, mime, code = b"original fixture already requested", "text/plain", 409
            else:
                content, mime, code = b"not found", "text/plain", 404
            self.send_response(code)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(content)))
            self.send_header("Cache-Control", "no-store")
            if self.path == "/" + filename and code == 200:
                self.send_header("Content-Disposition", 'attachment; filename="' + filename + '"')
            self.end_headers()
            self.wfile.write(content)

    # Chrome opens idle preconnections. A single-threaded HTTPServer would let
    # one idle socket block both the actual file and the read-only status probe.
    server = LoopbackServer(("127.0.0.1", 0), Handler)
    server.timeout = 0.5
    initial = {**state, "origin": "http://127.0.0.1:" + str(server.server_port)}
    with (root / "fixture.json").open("x") as file:
        json.dump(initial, file, indent=2)
    (root / "fixture.json").chmod(0o600)
    print(json.dumps(initial), flush=True)
    try:
        deadline = time.monotonic() + 600
        while time.monotonic() < deadline:
            server.handle_request()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        final = {"status": "fixture_server_stopped", **state}
        with (root / "server-final.json").open("x") as file:
            json.dump(final, file, indent=2)
        (root / "server-final.json").chmod(0o600)
        print(json.dumps(final), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", required=True)
    serve(parser.parse_args().output)
