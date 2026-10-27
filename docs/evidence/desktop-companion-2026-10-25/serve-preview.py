"""Serve only this design reference and the unchanged brand image on loopback."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
ASSETS = {
    "/presence-scenarios.html": (HERE / "presence-scenarios.html", "text/html; charset=utf-8"),
    "/apps/workbench/brand/core.png": (ROOT / "apps/workbench/brand/core.png", "image/png"),
}


class PreviewHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        path = urlsplit(self.path).path
        if path == "/favicon.ico":
            self.send_response(204)
            self.end_headers()
            return
        asset = ASSETS.get(path)
        if asset is None:
            self.send_error(404)
            return
        data = asset[0].read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", asset[1])
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, *_):
        pass


if __name__ == "__main__":
    with ThreadingHTTPServer(("127.0.0.1", 0), PreviewHandler) as server:
        print(f"http://127.0.0.1:{server.server_port}/presence-scenarios.html", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
