"""Builds pages.js: serves the free resources pages (/resources...) and the digital business card (/card...)
on thenailbawse.com. Files live in site/ at a pinned commit; the Worker checks each file's SHA-256 and keeps it in KV.
Usage: python3 build.py <commit>   (commit = the commit that contains site/ as it should be served)"""
import hashlib, json, os, sys
COMMIT = sys.argv[1]
TYPES = {".html": "text/html; charset=utf-8", ".css": "text/css; charset=utf-8", ".png": "image/png", ".jpg": "image/jpeg", ".svg": "image/svg+xml"}
man = {}
for root, _, files in os.walk("site"):
    for f in sorted(files):
        full = os.path.join(root, f); rel = os.path.relpath(full, "site").replace(os.sep, "/")
        ext = os.path.splitext(f)[1]
        route = "/" + (rel[:-len("/index.html")] if rel.endswith("/index.html") else rel[:-5] if ext == ".html" else rel)
        man[route] = {"f": rel, "s": hashlib.sha256(open(full, "rb").read()).hexdigest(), "t": TYPES[ext]}
src = open("pages.template.js").read().replace("__MANIFEST__", json.dumps(man, sort_keys=True)).replace("__COMMIT__", COMMIT)
open("pages.js", "w").write(src)
print(len(man), "routes; pages.js sha", hashlib.sha256(src.encode()).hexdigest(), len(src), "bytes")
