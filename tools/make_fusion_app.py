#!/usr/bin/env python3
"""Wrap a Clickteam Fusion 2.5 game (a Windows .exe) in a double-clickable macOS .app that runs it with a KlikCore2 binary you built.
usage: make_fusion_app.py --klikcore <path to klikcore> --game-dir <folder with the game .exe> --exe <exe file name> --name "Game Name" --out <folder> [--bundle-id id]
The game folder is APFS-cloned into the bundle (no extra disk), the icon is extracted from the .exe, the app is ad-hoc signed.
This script only packages files; it never runs the game or the runtime."""
import argparse, os, shutil, struct, subprocess, sys, tempfile
ap = argparse.ArgumentParser(); ap.add_argument('--klikcore', required=True); ap.add_argument('--game-dir', required=True); ap.add_argument('--exe', required=True)
ap.add_argument('--name', required=True); ap.add_argument('--out', required=True); ap.add_argument('--bundle-id'); a = ap.parse_args()
run = lambda *c: subprocess.run(c, check=True, capture_output=True)

def pe_icon_ico(path):
    d = open(path, 'rb').read(); pe = struct.unpack_from('<I', d, 0x3c)[0]; nsec = struct.unpack_from('<H', d, pe + 6)[0]; opt = pe + 24
    sec0 = opt + struct.unpack_from('<H', d, pe + 20)[0]; secs = [struct.unpack_from('<IIII', d, sec0 + 40 * i + 8) for i in range(nsec)]
    magic = struct.unpack_from('<H', d, opt)[0]; ddir = opt + (96 if magic == 0x10b else 112); rva, size = struct.unpack_from('<II', d, ddir + 16)
    def off(r):
        for vs, va, rs, rp in secs:
            if va <= r < va + max(vs, rs): return r - va + rp
    base = off(rva)
    def entries(o):
        n = struct.unpack_from('<H', d, o + 12)[0] + struct.unpack_from('<H', d, o + 14)[0]
        return [struct.unpack_from('<II', d, o + 16 + 8 * i) for i in range(n)]
    def leaf(o):                                   # descend first entry until a data entry
        while True:
            _, v = entries(o)[0]
            if v & 0x80000000: o = base + (v & 0x7fffffff)
            else: r, s, _, _ = struct.unpack_from('<IIII', d, base + v); return d[off(r):off(r) + s]
    res = {}
    for t, v in entries(base):
        if not v & 0x80000000: continue
        sub = base + (v & 0x7fffffff); res[t] = {i: leaf(base + (vv & 0x7fffffff)) if vv & 0x80000000 else None for i, vv in entries(sub)}
    if 14 not in res or 3 not in res: return None
    grp = leaf_first = next(iter(res[14].values())); cnt = struct.unpack_from('<H', grp, 4)[0]
    ents = [struct.unpack_from('<BBBBHHIH', grp, 6 + 14 * i) for i in range(cnt)]
    ico = struct.pack('<HHH', 0, 1, cnt); data = b''; pos = 6 + 16 * cnt; head = b''
    for w, h, cc, _, pl, bc, size, iid in ents:
        blob = res[3][iid]; head += struct.pack('<BBBBHHII', w, h, cc, 0, pl, bc, len(blob), pos + len(data)); data += blob
    return ico + head + data

app = f'{a.out}/{a.name}.app'; C = f'{app}/Contents'; slug = ''.join(ch for ch in a.name if ch.isalnum()) or 'FusionGame'
if os.path.exists(app): sys.exit(f'{app} exists; remove it first')
for sub in ('MacOS', 'Resources'): os.makedirs(f'{C}/{sub}')
shutil.copyfile(a.klikcore, f'{C}/Resources/klikcore'); os.chmod(f'{C}/Resources/klikcore', 0o755)
run('cp', '-c', '-R', a.game_dir, f'{C}/Resources/game')
open(f'{C}/MacOS/{slug}', 'w').write(f'#!/bin/zsh\nD="${{0:A:h}}/../Resources"\nexport KLIKCORE_DISCORD="${{KLIKCORE_DISCORD:-off}}"\ncd "$D/game" || exit 1\nexec "$D/klikcore" "$D/game/{a.exe}" "$@"\n'); os.chmod(f'{C}/MacOS/{slug}', 0o755)
icon_ok = False; ico = pe_icon_ico(f'{a.game_dir}/{a.exe}')
if ico:
    t = tempfile.mkdtemp(); open(f'{t}/i.ico', 'wb').write(ico)
    try:
        run('sips', '-s', 'format', 'png', f'{t}/i.ico', '--out', f'{t}/big.png'); iset = f'{t}/i.iconset'; os.makedirs(iset)
        for s in (16, 32, 64, 128, 256, 512):
            for scale, suf in ((1, ''), (2, '@2x')):
                px = s * scale
                if px <= 1024: run('sips', '-z', str(px), str(px), f'{t}/big.png', '--out', f'{iset}/icon_{s}x{s}{suf}.png')
        run('iconutil', '-c', 'icns', iset, '-o', f'{C}/Resources/AppIcon.icns'); icon_ok = True
    except subprocess.CalledProcessError as e: print('icon conversion failed:', (e.stderr or b'').decode()[:200])
plist = f'''<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleName</key><string>{a.name}</string><key>CFBundleDisplayName</key><string>{a.name}</string>
<key>CFBundleExecutable</key><string>{slug}</string><key>CFBundleIdentifier</key><string>{a.bundle_id or 'local.fusion.' + slug.lower()}</string>
<key>CFBundlePackageType</key><string>APPL</string><key>CFBundleShortVersionString</key><string>1.0</string><key>CFBundleVersion</key><string>1</string>
{'<key>CFBundleIconFile</key><string>AppIcon</string>' if icon_ok else ''}
<key>NSHighResolutionCapable</key><true/><key>LSMinimumSystemVersion</key><string>12.0</string><key>LSApplicationCategoryType</key><string>public.app-category.games</string>
</dict></plist>
'''
open(f'{C}/Info.plist', 'w').write(plist)
run('codesign', '--force', '--deep', '-s', '-', app); print('built', app, '| icon:', 'extracted from the exe' if icon_ok else 'none')
