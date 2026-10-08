"""Copy of web/serve.py for previewing the Houdini rebuild without touching web/:
  /assets/<f>        -> site-model/houdini/out/<f>        (Houdini GLB)
  /data/<f>          -> site-model/houdini/out/data/<f>   when that file exists (Houdini LiDAR labels), else web/data/<f>
  /ref/<f>           -> site-model/exports/<f>            (the Blender original, for comparisons)
  /data/entities.json -> site-model/houdini/annotations/entities.json (building entities)"""
import sys
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
REPO = Path(__file__).resolve().parents[3]          # the repository root
sys.path.insert(0, str(REPO / "web"))
import serve
serve.EXPORTS = REPO / "site-model" / "houdini" / "out"
HDATA = REPO / "site-model" / "houdini" / "out" / "data"
ANN = REPO / "site-model" / "houdini" / "annotations" / "entities.json"   # building entities (hand-made)
class H(serve.Handler):
    def translate_path(self, path):
        clean = path.split("?", 1)[0].split("#", 1)[0]
        if clean.startswith("/ref/"):
            return str(REPO / "site-model" / "exports" / clean[5:])
        if clean == "/data/entities.json" and ANN.exists():
            return str(ANN)
        if clean.startswith("/data/") and (HDATA / clean[6:]).exists():
            return str(HDATA / clean[6:])
        return super().translate_path(path)
port = int(sys.argv[1]) if len(sys.argv) > 1 else 8767
print("serving houdini rebuild on", port)
ThreadingHTTPServer(("", port), partial(H, directory=str(REPO / "web"))).serve_forever()
