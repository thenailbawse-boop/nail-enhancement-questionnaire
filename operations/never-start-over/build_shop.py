#!/usr/bin/env python3
"""Build operations/site-worker/shop.js (the /shop sales page module) from shop/shop.body.html + shop/shop.css.

The private product (private/hub.html) is NOT packed here. It lives in the Worker's NSO_KV namespace under
"hub.html" and is backed up to Google Drive, because this repository is public.
"""
import json, os, re

here = os.path.dirname(os.path.abspath(__file__))
rd = lambda p: open(os.path.join(here, p), encoding='utf-8').read()

body = rd('shop/shop.body.html')
css = rd('shop/shop.css')
css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
css = re.sub(r'\s*\n\s*', '', css)

# Guard rails: words that must never reach the public page or this public repo (the surprise promo code,
# any $100-off wording) are listed one per line in private/forbidden.txt, which is git-ignored.
fp = os.path.join(here, 'private', 'forbidden.txt')
forbidden = [w.strip() for w in open(fp, encoding='utf-8')] if os.path.exists(fp) else []
if not forbidden: print('WARNING: private/forbidden.txt missing; skipping the forbidden-words check')
assert body.count('{{PRICE}}') == 2 and '{{SESSION_URL}}' in body

tpl = rd('shop/shop.template.js')
for bad in filter(None, forbidden):
    for name, text in (('shop.body.html', body), ('shop.css', css), ('shop.template.js', tpl)):
        assert bad.lower() not in text.lower(), name + ' contains a forbidden word'
out = tpl.replace('__BODY__', json.dumps(body, ensure_ascii=False)).replace('__CSS__', json.dumps(css, ensure_ascii=False))
dst = os.path.join(here, '..', 'site-worker', 'shop.js')
open(dst, 'w', encoding='utf-8').write(out)
print('shop.js', len(out.encode('utf-8')), 'bytes')
