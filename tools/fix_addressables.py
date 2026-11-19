#!/usr/bin/env python3
"""Windows Addressables catalogs store bundle paths with backslashes ('...RuntimePath}\\StandaloneWindows64\\x.bundle'), which fail on macOS.
Same-length byte replacement in catalog.bin; (longer) text replacement in catalog.json.  usage: fix_addressables.py <Data>/StreamingAssets/aa"""
import sys, os, json
aa = sys.argv[1]
if not os.path.isdir(aa): print('no Addressables folder, nothing to do'); sys.exit(0)
target = json.load(open(f'{aa}/settings.json'))['m_buildTarget']          # e.g. StandaloneWindows64
for name, a, b in (('catalog.bin', f'\\{target}\\'.encode(), f'/{target}/'.encode()), ('catalog.json', f'\\\\{target}\\\\'.encode(), f'/{target}/'.encode())):
    p = f'{aa}/{name}'
    if os.path.exists(p):
        d = open(p, 'rb').read(); n = d.count(a); open(p, 'wb').write(d.replace(a, b)); print(f'{name}: {n} paths fixed')
