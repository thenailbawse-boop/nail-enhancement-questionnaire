#!/usr/bin/env python3
"""Pack onboard.html + manage.html into dist/ and build onboarding.js pinned to a commit: python3 build.py <commit>"""
import hashlib, json, os, shutil, sys
here = os.path.dirname(os.path.abspath(__file__)); dist = os.path.join(here, 'dist'); os.makedirs(dist, exist_ok=True)
manifest = {}
for name, f in [('onboard', 'onboard.html'), ('manage', 'manage.html')]:
    shutil.copyfile(os.path.join(here, f), os.path.join(dist, f))
    manifest[name] = {'f': f, 's': hashlib.sha256(open(os.path.join(dist, f), 'rb').read()).hexdigest()}
commit = sys.argv[1] if len(sys.argv) > 1 else 'PENDING'
src = open(os.path.join(here, 'onboarding.template.js')).read().replace('__MANIFEST__', json.dumps(manifest, separators=(',', ':'))).replace('__COMMIT__', commit)
open(os.path.join(here, 'onboarding.js'), 'w').write(src)
print('onboarding.js', len(src), 'bytes', hashlib.sha256(src.encode()).hexdigest())
