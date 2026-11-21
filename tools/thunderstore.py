#!/usr/bin/env python3
"""Install Thunderstore mods (with dependencies) into a BepInEx folder, laid out the way r2modman does.
usage: thunderstore.py <BepInEx dir> add <Namespace-Name> [...] | list | del <Namespace-Name>
BepInExPack is skipped (tools/mods installs BepInEx itself). Mods that contain Windows-native DLLs are refused."""
import io, json, os, shutil, sys, time, urllib.request, zipfile

API = 'https://thunderstore.io/api/experimental/package/{}/{}/'
SKIP = {'BepInEx-BepInExPack'}

def fetch(url): return urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'metalport'}), timeout=60).read()

def resolve(full, seen):
    """full = 'Namespace-Name' (optional -Version suffix ignored: always the latest). Returns install order, dependencies first."""
    ns, name = full.split('-')[:2]; key = f'{ns}-{name}'
    if key in seen or key in SKIP: return []
    seen.add(key)
    pkg = json.loads(fetch(API.format(ns, name)))['latest']
    order = []
    for dep in pkg['dependencies']: order += resolve(dep, seen)
    return order + [(key, pkg['version_number'], pkg['download_url'])]

def is_native_dll(data):            # PE without a .NET (CLI) header = Windows-native code, which can't load on macOS
    if data[:2] != b'MZ': return False
    pe = int.from_bytes(data[0x3c:0x40], 'little'); magic = int.from_bytes(data[pe + 24:pe + 26], 'little')
    dd = pe + 24 + (96 if magic == 0x10b else 112); cli = dd + 14 * 8
    return int.from_bytes(data[cli:cli + 8], 'little') == 0

def install(root, key, version, url):
    z = zipfile.ZipFile(io.BytesIO(fetch(url)))
    native = [n for n in z.namelist() if n.lower().endswith('.dll') and is_native_dll(z.read(n))]
    if native: sys.exit(f'{key}: contains Windows-native code ({", ".join(native[:3])}); not installed')
    dest = os.path.join(root, 'plugins', key); shutil.rmtree(dest, ignore_errors=True)
    for n in z.namelist():
        if n.endswith('/'): continue
        parts = n.replace('\\', '/').split('/')
        if parts[0] == 'BepInEx' and len(parts) > 2: parts = parts[1:]                  # BepInEx/plugins/x -> plugins/x
        top = parts[0].lower()
        if top in ('plugins', 'patchers', 'core'): out = os.path.join(root, top, key, *parts[1:])
        elif top == 'config': out = os.path.join(root, 'config', *parts[1:])
        else: out = os.path.join(dest, *parts)                                            # manifest.json, icon, loose .dll
        if top == 'config' and os.path.exists(out): continue                               # keep the user's settings
        os.makedirs(os.path.dirname(out), exist_ok=True); open(out, 'wb').write(z.read(n))
    print(f'installed {key} {version}')

def main(a):
    root, cmd, names = a[1], a[2], a[3:]
    if cmd == 'add':
        seen = set(); order = []
        for n in names: order += resolve(n, seen)
        for key, version, url in order: install(root, key, version, url)
    elif cmd == 'list':
        d = os.path.join(root, 'plugins')
        for k in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            m = os.path.join(d, k, 'manifest.json'); v = json.load(open(m, encoding='utf-8-sig')).get('version_number', '?') if os.path.exists(m) else '-'
            print(k, v)
    elif cmd == 'del':
        for n in names:
            for top in ('plugins', 'patchers'):
                p = os.path.join(root, top, n)
                if os.path.isdir(p): shutil.move(p, os.path.expanduser(f'~/.Trash/{n}-{time.strftime("%Y%m%d-%H%M%S")}')); print(f'removed {n} ({top}, moved to Trash)')
    else: sys.exit(__doc__)

if __name__ == '__main__':
    if len(sys.argv) < 3: sys.exit(__doc__)
    main(sys.argv)
