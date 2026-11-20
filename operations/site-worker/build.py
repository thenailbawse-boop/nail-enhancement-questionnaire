#!/usr/bin/env python3
"""Pack funnel-site/public into funnel.js and patch the live Worker (worker.original.js -> worker.new.js)."""
import base64, json, os, re, io
here = os.path.dirname(os.path.abspath(__file__)); pub = os.path.join(here, '..', '..', 'funnel-site', 'public')
rd = lambda p: open(os.path.join(pub, p), encoding='utf-8').read()

def page(html):
    html = html.replace('/assets/', '/webinar-assets/')
    return html
idx = page(rd('index.html'))
idx = re.sub(r'\s*<details class="more">.*?</details>', '', idx, flags=re.S)   # this site stores first name + email only
idx = idx.replace('<html lang="en">', '<html lang="en" data-thanks="/webinar/thanks">', 1)
idx = idx.replace('<head>', '<head>\n<link rel="canonical" href="https://thenailbawse.com/webinar">\n<meta property="og:url" content="https://thenailbawse.com/webinar">', 1)
ty = page(rd('thanks.html'))
assert 'details class="more"' not in idx and 'data-thanks' in idx

from PIL import Image
def webp(src, size, q):
    im = Image.open(os.path.join(pub, 'assets', src)).convert('RGB'); im.thumbnail((size, size))
    b = io.BytesIO(); im.save(b, 'WEBP', quality=q, method=6); return base64.b64encode(b.getvalue()).decode()
assets = {
  'index':  {'t': 'text/html; charset=utf-8', 'b': idx},
  'thanks': {'t': 'text/html; charset=utf-8', 'b': ty},
  'funnel.css': {'t': 'text/css; charset=utf-8', 'b': rd('assets/funnel.css')},
  'app.js':  {'t': 'text/javascript; charset=utf-8', 'b': rd('assets/app.js')},
  'card.js': {'t': 'text/javascript; charset=utf-8', 'b': rd('assets/card.js')},
  'anisia.jpg': {'t': 'image/webp', 'e': 'b64', 'b': webp('anisia.jpg', 640, 72)},
  'anisia-face.jpg': {'t': 'image/webp', 'e': 'b64', 'b': webp('anisia-face.jpg', 160, 80)},
}
mod = open(os.path.join(here, 'funnel.template.js')).read().replace('__ASSETS__', json.dumps(assets, ensure_ascii=False, separators=(',', ':')))
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
]
src = open(os.path.join(here, 'worker.original.js')).read()
for a, b, n in PATCH:
    assert src.count(a) == n, (a[:60], src.count(a)); src = src.replace(a, b)
assert 'Burnt Out' not in src
open(os.path.join(here, 'worker.new.js'), 'w').write(src)
json.dump(PATCH, open(os.path.join(here, 'patch.json'), 'w'), ensure_ascii=False)
print('funnel.js', len(mod), 'bytes; worker.new.js', len(src), 'bytes')
