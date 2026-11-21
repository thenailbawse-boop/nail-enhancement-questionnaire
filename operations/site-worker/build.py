#!/usr/bin/env python3
"""Pack funnel-site/public into funnel.js and patch the live Worker (worker.original.js -> worker.new.js)."""
import base64, json, os, re, io
here = os.path.dirname(os.path.abspath(__file__)); pub = os.path.join(here, '..', '..', 'funnel-site', 'public')
rd = lambda p: open(os.path.join(pub, p), encoding='utf-8').read()

PHOTOS = {  # hosted in the Wix Media Manager of "The Nail Bawse —" site
  '/assets/anisia.jpg': 'https://static.wixstatic.com/media/86a5ad_65777c887ac14c5d9884accaf44a6826~mv2.jpg',
  '/assets/anisia-face.jpg': 'https://static.wixstatic.com/media/86a5ad_1db25fb895c54f74b2ee64d9d9a78d44~mv2.jpg',
}
def page(html):
    for a, b in PHOTOS.items(): html = html.replace(a, b)
    html = html.replace('/assets/', '/webinar-assets/')
    return html
def mincss(c):
    c = re.sub(r'/\*.*?\*/', '', c, flags=re.S); c = re.sub(r'\s*\n\s*', '', c); return c
idx = page(rd('index.html'))
idx = re.sub(r'\s*<details class="more">.*?</details>', '', idx, flags=re.S)   # this site stores first name + email only
idx = idx.replace('<html lang="en">', '<html lang="en" data-thanks="/webinar/thanks">', 1)
idx = idx.replace('<head>', '<head>\n<link rel="canonical" href="https://thenailbawse.com/webinar">\n<meta property="og:url" content="https://thenailbawse.com/webinar">', 1)
ty = page(rd('thanks.html'))
assert 'details class="more"' not in idx and 'data-thanks' in idx

assets = {
  'index':  {'t': 'text/html; charset=utf-8', 'b': idx},
  'thanks': {'t': 'text/html; charset=utf-8', 'b': ty},
  'funnel.css': {'t': 'text/css; charset=utf-8', 'b': mincss(rd('assets/funnel.css'))},
  'app.js':  {'t': 'text/javascript; charset=utf-8', 'b': rd('assets/app.js')},
  'card.js': {'t': 'text/javascript; charset=utf-8', 'b': rd('assets/card.js')},
}
# Write the page files to dist/ (served from a pinned commit, cached in the Worker's KV) and a manifest of fingerprints
import hashlib, sys
dist = os.path.join(here, 'dist'); os.makedirs(dist, exist_ok=True)
names = {'index': 'index.html', 'thanks': 'thanks.html', 'funnel.css': 'funnel.css', 'app.js': 'app.js', 'card.js': 'card.js'}
manifest = {}
for k, a in assets.items():
    open(os.path.join(dist, names[k]), 'w', encoding='utf-8').write(a['b'])
    manifest[k] = {'f': names[k], 't': a['t'], 's': hashlib.sha256(a['b'].encode('utf-8')).hexdigest()}
commit = sys.argv[1] if len(sys.argv) > 1 else 'PENDING'
mod = open(os.path.join(here, 'funnel.template.js')).read().replace('__MANIFEST__', json.dumps(manifest, separators=(',', ':'))).replace('__COMMIT__', commit)
open(os.path.join(here, 'funnel.js'), 'w').write(mod)
# Patch for the live Worker: the same string edits are applied on Cloudflare at deploy time.
PATCH = [
  ['const FILES = ', 'import { funnel } from "./funnel.js";\nconst FILES = ', 1],
  ['    if (key === "/webinar" && request.method === "POST") return register(request, env);',
   '    const fr = await funnel(request, env, { key: key, path: path, nextSession: nextSession, icsText: icsText, ZOOM: ZOOM, APEX: APEX, DUR: DUR }); if (fr) return fr;\n    if (key === "/webinar" && request.method === "POST") return register(request, env);', 1],
  ['<h1>Booked, Burnt Out <em>&amp; Underpaid.</em></h1>', '<h1>Build Your <em>AI Agent.</em></h1>', 1],
  ['Free Webinar: Booked, Burnt Out & Underpaid | The Nail Bawse', 'Free Class: Build Your AI Agent | The Nail Bawse', 1],
  ['Booked, Burnt Out &amp; Underpaid — free live', 'Build Your AI Agent — free live', 1],
  ['SUMMARY:Booked\\\\, Burnt Out & Underpaid — The Nail Bawse (free Zoom webinar)', 'SUMMARY:Build Your AI Agent — The Nail Bawse (free live class on Zoom)', 1],
  # Never Start Over: /shop sales page, /shop/buy and the private product (module shop.js, built by never-start-over/build_shop.py)
  ['import { funnel } from "./funnel.js";', 'import { funnel } from "./funnel.js";\nimport { shop } from "./shop.js";', 1],
  ['    const fr = await funnel(', '    const sr = await shop(request, env, { key: key, path: path, page: page, html: html, respond: respond, SESSION_URL: SESSION_URL }); if (sr) return sr;\n    const fr = await funnel(', 1],
]
src = open(os.path.join(here, 'worker.original.js')).read()
for a, b, n in PATCH:
    assert src.count(a) == n, (a[:60], src.count(a)); src = src.replace(a, b)
assert 'Burnt Out' not in src
open(os.path.join(here, 'worker.new.js'), 'w').write(src)
json.dump(PATCH, open(os.path.join(here, 'patch.json'), 'w'), ensure_ascii=False)
print('funnel.js', len(mod), 'bytes; worker.new.js', len(src), 'bytes')
