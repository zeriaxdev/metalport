#!/usr/bin/env python3
"""Add Metal shaders to the asset bundles of BepInEx mods, so they stop rendering magenta on a native Mac port.
usage: patch_mod_bundles.py <plugins dir> [--backup-dir DIR] [--dry-run]

Mod authors ship Windows (D3D11) shaders only. This finds every UnityFS bundle under <plugins dir> that has a shader without a Metal
variant, translates its programs (xlate_all.py, filling tools/cache), appends the Metal variants (patch_bundles.py with
ALLOW_PARTIAL_SHADER=1, so a few variants Metal rejects are left out) and replaces the bundle. Originals are copied to the backup dir first.
Re-run after a mod update replaces a bundle. Needs the project's Python environment (UnityPy, lz4) and the built tools/h2m."""
import argparse, os, shutil, subprocess, sys, tempfile, time
import UnityPy

here = os.path.dirname(os.path.abspath(__file__))


def needs_metal(path):
    with open(path, 'rb') as f:
        if f.read(7) != b'UnityFS': return False
    for obj in UnityPy.load(path).objects:
        if obj.type.name != 'Shader': continue
        shader = obj.read(); platforms = set(getattr(shader, 'platforms', None) or [])
        if 4 in platforms and 14 not in platforms: return True
    return False


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('plugins'); ap.add_argument('--backup-dir'); ap.add_argument('--dry-run', action='store_true')
    a = ap.parse_args(); root = os.path.abspath(a.plugins)
    found = [os.path.join(d, f) for d, _, fs in os.walk(root) for f in fs
             if 2000 < os.path.getsize(os.path.join(d, f)) < 600_000_000 and needs_metal(os.path.join(d, f))]
    for p in found: print('needs Metal:', os.path.relpath(p, root))
    if a.dry_run or not found: return print(f'{len(found)} bundle(s) need Metal shaders')
    backup = a.backup_dir or os.path.expanduser(f'~/Library/Application Support/metalport/backups/mod-bundles-{time.strftime("%Y%m%d-%H%M%S")}')
    work = tempfile.mkdtemp(prefix='mod-bundles-'); data = os.path.join(work, 'Data'); os.makedirs(data); copies = {}
    for i, p in enumerate(found):
        copies[p] = os.path.join(data, f'{i}.bundle'); shutil.copyfile(p, copies[p])
    subprocess.run([sys.executable, os.path.join(here, 'xlate_all.py'), data, '--report', os.path.join(work, 'report.json'), '--allow-incomplete'], cwd=here)
    env = dict(os.environ, ALLOW_PARTIAL_SHADER='1', ALLOW_METAL_FAILURES='1'); patched = 0
    for p, copy in copies.items():
        rc = subprocess.run([sys.executable, os.path.join(here, 'patch_bundles.py'), copy], cwd=here, env=env).returncode
        if rc not in (0, 2): print('failed, left as is:', os.path.relpath(p, root)); continue      # 2 = patched, some variants left out
        dest = os.path.join(backup, os.path.relpath(p, root)); os.makedirs(os.path.dirname(dest), exist_ok=True)
        shutil.copy2(p, dest); shutil.copyfile(copy, p); patched += 1; print('patched:', os.path.relpath(p, root))
    print(f'{patched}/{len(found)} bundle(s) patched; originals in {backup}')


if __name__ == '__main__':
    main()
