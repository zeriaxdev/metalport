#!/usr/bin/env python3
"""Wrap a Windows Unity (Mono) game's Data folder in a native arm64 macOS player.  Does steps 1-5 of docs/PIPELINE.md except shaders.
usage: assemble_app.py --data <Game>_Data --unity <fetch_unity out dir> --out <dir> --name <AppName> [--dev]
result: <out>/<AppName>.app and <out>/Resources (symlink the Addressables path hack needs)"""
import argparse, glob, hashlib, os, shutil, subprocess, sys
ap = argparse.ArgumentParser(); ap.add_argument('--data', required=True); ap.add_argument('--unity', required=True); ap.add_argument('--out', required=True)
ap.add_argument('--name', required=True); ap.add_argument('--bundle-id'); ap.add_argument('--dev', action='store_true'); ap.add_argument('--icon', help='optional .icns to use as the app icon'); a = ap.parse_args()
here = os.path.dirname(os.path.abspath(__file__)); sh = lambda *c: subprocess.run(c, check=True)
payload = os.path.dirname(glob.glob(f'{a.unity}/module/**/Payload/Variations', recursive=True)[0])
var = f'{payload}/Variations/macos_arm64_player_{"development" if a.dev else "nondevelopment"}_mono/UnityPlayer.app/Contents'
app = f'{a.out}/{a.name}.app'; C = f'{app}/Contents'
if os.path.exists(app): sys.exit(f'{app} exists; remove it first')
for d in ('MacOS', 'Frameworks', 'Resources', 'Plugins'): os.makedirs(f'{C}/{d}')
sh('cp', '-c', f'{var}/MacOS/UnityPlayer', f'{C}/MacOS/{a.name}')
for f in os.listdir(f'{var}/Frameworks'): sh('cp', '-c', f'{var}/Frameworks/{f}', f'{C}/Frameworks/')
src = f'{payload}/Source/Player/MacPlayer/MacPlayerEntryPoint'
sh('cp', f'{src}/Info.plist', f'{C}/Info.plist'); sh('cp', '-c', '-R', f'{src}/Resources/MainMenu.nib', f'{src}/Resources/PlayerIcon.icns', f'{C}/Resources/')
sh('cp', '-c', '-R', a.data, f'{C}/Resources/Data'); sh('cp', '-c', '-R', f'{payload}/MonoBleedingEdge', f'{C}/MonoBleedingEdge')
if a.icon: shutil.copyfile(a.icon, f'{C}/Resources/PlayerIcon.icns')
for k, v in (('CFBundleExecutable', a.name), ('CFBundleIdentifier', a.bundle_id or f'local.port.{a.name.lower()}'), ('CFBundleName', a.name), ('CFBundleShortVersionString', '1'),
             ('CFBundleVersion', '1'), ('UnityBuildNumber', '1'), ('CFBundleGetInfoString', f'{a.name} port'), ('LSApplicationCategoryType', 'public.app-category.games'),
             ('NSMicrophoneUsageDescription', 'This game uses the microphone for voice chat.')): sh('plutil', '-replace', k, '-string', v, f'{C}/Info.plist')
sh('plutil', '-replace', 'NSAppSleepDisabled', '-bool', 'YES', f'{C}/Info.plist')     # keep App Nap from throttling audio when unfocused
# Windows class libraries -> macOS ones (identified by being byte-identical to Unity's unityjit-win32 build)
h = lambda p: hashlib.sha1(open(p, 'rb').read()).hexdigest(); lib = f'{a.unity}/monolibs'
def index(d): return {f: f'{lib}/{d}/{s}{f}' for s in ('', 'Facades/') for f in os.listdir(f'{lib}/{d}/{s}'.rstrip('/')) if f.endswith('.dll')}
win, mac = index('unityjit-win32'), index('unityjit-macos'); M = f'{C}/Resources/Data/Managed'; swapped = []
for f in sorted(os.listdir(M)):
    if f in win and f in mac and h(f'{M}/{f}') == h(win[f]) and h(win[f]) != h(mac[f]): shutil.copyfile(mac[f], f'{M}/{f}'); swapped.append(f)
print(f'swapped {len(swapped)} class libraries to macOS builds')
D = f'{C}/Resources/Data'; py = sys.executable
sh(py, f'{here}/patch_buildsettings.py', f'{D}/globalgamemanagers'); sh(py, f'{here}/fix_addressables.py', f'{D}/StreamingAssets/aa')
os.symlink(f'{a.name}.app/Contents/Resources', f'{a.out}/Resources') if not os.path.exists(f'{a.out}/Resources') else None
print('assembled', app)
