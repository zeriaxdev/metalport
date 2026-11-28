#!/usr/bin/env python3
"""Fetch the two Unity pieces a Mac port needs, for an exact Unity version (the player must match the game's Unity version):
  1. the "Mac Mono Support" module  -> macOS player variations (arm64/x64), Info.plist + nib templates, MonoBleedingEdge/etc  (~0.7 GB download)
  2. the macOS Mono class libraries (mscorlib, System.*, ...) streamed out of the Editor .pkg without storing it (~5 GB transfer, ~100 MB kept)
usage: fetch_unity.py 6000.3.28f1 OUT_DIR   ->  OUT_DIR/module/Payload/...   OUT_DIR/monolibs/<unityjit-macos|unityjit-win32>/
"""
import sys, os, json, struct, zlib, subprocess, urllib.request
import xml.etree.ElementTree as ET
ver, out = sys.argv[1], os.path.abspath(sys.argv[2]); os.makedirs(out, exist_ok=True)
rel = json.load(urllib.request.urlopen(f'https://services.api.unity.com/unity/editor/release/v1/releases?version={ver}&limit=1'))['results'][0]

mac_editors = [d for d in rel.get('downloads', []) if d.get('platform') == 'MAC_OS']
editor_download = next((d for d in mac_editors if d.get('architecture') == 'ARM64'), None) or next((d for d in mac_editors if d.get('architecture') == 'X86_64'), None)
if editor_download is None:
    available = [d.get('architecture') for d in mac_editors]
    raise SystemExit(f'No macOS editor download for Unity {ver}; available architectures: {available}')
editor = editor_download['url']
print('editor architecture:', editor_download['architecture'])

module = next(m['url'] for d in rel['downloads'] if d['platform'] == 'LINUX' for m in d.get('modules', []) if m['id'] == 'mac-mono')
print('module :', module); print('editor :', editor)

pkg = f'{out}/module.pkg'
if not os.path.isdir(f'{out}/module'):
    subprocess.run(['curl', '-L', '-C', '-', '-sS', '--fail', '-o', pkg, module], check=True)
    subprocess.run(['pkgutil', '--expand-full', pkg, f'{out}/module'], check=True); os.remove(pkg)
print('module ready:', f'{out}/module')

# Editor .pkg is a flat xar; Payload is a gzip'd cpio. Read the TOC with a range request, then stream-extract only the Mono libs.
def rng(a, b): return subprocess.run(['curl', '-sS', '-r', f'{a}-{b}', editor], capture_output=True, check=True).stdout
head = rng(0, 65535); hsize, toc_len = 28, struct.unpack('>Q', head[8:16])[0]
toc = ET.fromstring(zlib.decompress(head[hsize:hsize + toc_len])).find('toc'); heap = hsize + toc_len
def walk(el):
    for f in el.findall('file'):
        if f.findtext('name') == 'Payload': yield f
        yield from walk(f)
pl = next(walk(toc)).find('data'); start = heap + int(pl.findtext('offset')); length = int(pl.findtext('length'))
dest = f'{out}/editor_x'; os.makedirs(dest, exist_ok=True)
if not os.path.isdir(f'{out}/monolibs'):
    print(f'streaming {length / 1e9:.1f} GB payload, keeping only lib/mono/unityjit* (a few minutes)...')
    subprocess.run(f'curl -sS -r {start}-{start + length - 1} "{editor}" | gunzip | cpio -idm --quiet "*lib/mono/unityjit*"', shell=True, cwd=dest, check=True)
    src = next(os.path.join(r, 'unityjit-macos') for r, d, _ in os.walk(dest) if 'unityjit-macos' in d)
    os.rename(os.path.dirname(src), f'{out}/monolibs')
print('mono libs ready:', f'{out}/monolibs')
