"""Local preview server that mirrors the GitHub Pages layout.

Serves web/ and maps /assets/<file> to ../site-model/exports/<file>, which is what the Pages workflow
copies at deploy time, so pages load the same URLs locally and online.

  python web/serve.py            (http://localhost:8766)
  python web/serve.py 9000
"""
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

WEB = Path(__file__).resolve().parent
EXPORTS = WEB.parent / "site-model" / "exports"


class Handler(SimpleHTTPRequestHandler):
    def translate_path(self, path):
        clean = path.split("?", 1)[0].split("#", 1)[0]
        if clean.startswith("/assets/"):
            return str(EXPORTS / clean[len("/assets/"):])
        return super().translate_path(path)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")  # always see the latest export while working
        super().end_headers()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8766
    print(f"serving {WEB} on http://localhost:{port}  (/assets -> {EXPORTS})")
    ThreadingHTTPServer(("", port), partial(Handler, directory=str(WEB))).serve_forever()
