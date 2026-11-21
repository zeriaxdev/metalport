#!/usr/bin/env python3
"""Opt-in ULTRAKILL palette comparison. All app/profile mutations stay under --out."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import plistlib
import shutil
import subprocess
import sys
import uuid

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def capture_stats(path):
    from PIL import Image, ImageChops
    with Image.open(path) as image:
        rgb = image.convert('RGB')
    channels = rgb.split()
    maximum = ImageChops.lighter(ImageChops.lighter(channels[0], channels[1]), channels[2])
    total = rgb.width * rgb.height
    lit = total - sum(maximum.histogram()[:6])
    colors = len(rgb.getcolors(total))
    return {'size': list(rgb.size), 'pixels': total, 'lit_pixels': lit, 'colors': colors,
            'looks_rendered': lit > total / 50 and colors >= 32}


def compare_images(left, right):
    from PIL import Image, ImageChops, ImageStat
    with Image.open(left) as image:
        a = image.convert('RGB')
    with Image.open(right) as image:
        b = image.convert('RGB')
    if a.size != b.size:
        raise ValueError('Capture dimensions differ')
    diff = ImageChops.difference(a, b)
    channels = diff.split()
    maximum = ImageChops.lighter(ImageChops.lighter(channels[0], channels[1]), channels[2])
    total = a.width * a.height
    different = total - maximum.histogram()[0]
    return {'pixels': total, 'different_pixels': different, 'identical_percent': 100 * (total - different) / total,
            'mean_absolute_rgb_error_0_255': sum(ImageStat.Stat(diff).mean) / 3,
            'max_rgb_error_0_255': maximum.getextrema()[1]}


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--app', required=True, type=Path, help='An existing working native ULTRAKILL app')
    parser.add_argument('--out', required=True, type=Path, help='A new directory for the disposable app, profiles and captures')
    args = parser.parse_args()
    source, output = args.app.expanduser().resolve(), args.out.expanduser().resolve()
    if not source.is_dir() or source.suffix != '.app':
        parser.error('--app must be a working native app bundle')
    if output.exists() or output.is_relative_to(source) or source.is_relative_to(output):
        parser.error('--out must be a new directory outside the source app')
    resources = source / 'Contents/Resources'
    config = json.loads((resources / 'converter-profile.json').read_text())
    identifier = str(uuid.UUID(config['profile_id']))
    original_info = plistlib.loads((source / 'Contents/Info.plist').read_bytes())
    override = original_info.get('LSEnvironment', {}).get('ULTRAKILL_MAC_DATA_PATH')
    profile = Path(override).parent if override else Path.home() / 'Library/Application Support/ULTRAKILL Mac' / identifier
    profile = profile.expanduser().resolve()
    if output.is_relative_to(profile) or profile.is_relative_to(output):
        parser.error('--out must be outside the live profile')
    output.mkdir(parents=True)
    (output / '.metalport-gameplay-test').touch()
    app = output / 'mac/GameplayTest.app'
    app.parent.mkdir()
    subprocess.run(['/bin/cp', '-cR', str(source), str(app)], check=True)
    protected_files = [source / 'Contents/Info.plist', source / 'Contents/MacOS/ULTRAKILL', source / 'Contents/MacOS/UnityPlayer',
                       resources / 'Data/Managed/Assembly-CSharp.dll',
                       resources / 'Data/StreamingAssets/aa/StandaloneWindows64/assets_assets_assets/shaders.bundle']
    live = [p for folder in [profile / 'Saves', profile / 'Preferences'] for p in folder.rglob('*') if p.is_file() and not p.is_symlink()]
    hashes = {str(p): digest(p) for p in protected_files + live if p.is_file()}
    (output / 'original-hashes.json').write_text(json.dumps(hashes, indent=2) + '\n')
    seed = output / 'profile-seed'
    seed.mkdir()
    for name in ('Saves', 'Preferences', 'Cybergrind', 'Palettes'):
        original = profile / name
        if original.exists():
            if original.is_symlink() or any(p.is_symlink() for p in original.rglob('*')):
                raise ValueError('Profile content contains symlinks; use a regular copied profile')
            shutil.copytree(original, seed / name)
    for mode in ('off', 'on'):
        copied = output / ('profile-' + mode)
        shutil.copytree(seed, copied)
        prefs = copied / 'Preferences/LocalPrefs.json'
        prefs.parent.mkdir(exist_ok=True)
        values = json.loads(prefs.read_text()) if prefs.is_file() else {}
        values.update(disabledComputeShaders=mode == 'off', colorPalette=False)
        prefs.write_text(json.dumps(values, indent=2) + '\n')
        (copied / 'ULTRAKILL_Data').symlink_to(app / 'Contents/Resources/Data')
    info = dict(original_info)
    info.update(CFBundleExecutable='UnityPlayer', CFBundleIdentifier='local.metalport.ultrakill-probe.' + str(uuid.uuid4()),
                CFBundleDisplayName='ULTRAKILL Compute Probe', CFBundleName='ULTRAKILL Compute Probe')
    info['LSEnvironment'] = {'MTL_HUD_ENABLED': '0', 'ULTRAKILL_MAC_DATA_PATH': str(output / 'profile-off/ULTRAKILL_Data'),
                             'ULTRAKILL_MAC_START_SCENE': 'Main Menu', 'GAMEPLAY_COMPUTE_MODE': 'off',
                             'GAMEPLAY_OUTPUT': str(output / 'off')}
    (app / 'Contents/Info.plist').write_bytes(plistlib.dumps(info))
    managed = app / 'Contents/Resources/Data/Managed'
    subprocess.run([sys.executable, str(REPO / 'tools/patch_bundles.py'), str(managed.parent / 'StreamingAssets/aa/StandaloneWindows64/assets_assets_assets/shaders.bundle')], check=True)
    build_env = os.environ.copy()
    build_env.update(DOTNET_CLI_HOME=str(output / 'dotnet-home'), NUGET_PACKAGES=os.environ.get('NUGET_PACKAGES', str(Path.home() / '.nuget/packages')),
                     DOTNET_CLI_USE_MSBUILD_SERVER='0', DOTNET_GENERATE_ASPNET_CERTIFICATE='false', DOTNET_CLI_TELEMETRY_OPTOUT='1')
    major = int(subprocess.check_output(['dotnet', '--version'], env=build_env, text=True).split('.')[0])
    if major < 8:
        raise ValueError('.NET SDK 8 or newer is required')
    framework = 'net' + str(major) + '.0'
    for project, name, target in [('Probe/GameplayProbe.csproj', 'probe', 'netstandard2.1'), ('Patch/Patch.csproj', 'patch', framework)]:
        subprocess.run(['dotnet', 'build', str(HERE / project), '-c', 'Release', '--nologo', '--ignore-failed-sources',
                        '-p:NuGetAudit=false', '-p:UseSharedCompilation=false', '-nodeReuse:false',
                        '-p:BaseIntermediateOutputPath=' + str(output / 'build' / (name + '-obj')) + '/',
                        '-p:GameplayTargetFramework=' + target, '-p:GameManagedPath=' + str(managed),
                        '-o', str(output / 'build' / name)], env=build_env, check=True)
    subprocess.run(['dotnet', str(output / 'build/patch/Patch.dll'), str(managed / 'Assembly-CSharp.dll'),
                    str(output / 'build/probe/GameplayProbe.dll'), str(output)], env=build_env, check=True)
    subprocess.run(['/usr/bin/codesign', '--force', '--deep', '--sign', '-', str(app)], check=True)
    subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', str(app)], check=True)
    protected = [str(source), str(profile), str(Path.home() / 'Library/Preferences'), str(Path.home() / 'Library/Application Support')]
    if config.get('source'):
        protected.append(str(Path(config['source']).expanduser().resolve()))
    policy = '(version 1)\n(allow default)\n' + ''.join('(deny file-write* (subpath ' + json.dumps(p) + '))\n' for p in protected)
    modes = {}
    for mode in ('off', 'on'):
        destination = output / mode
        destination.mkdir()
        for name in ('tmp', 'home/Library/Preferences', 'diagnostics'):
            (destination / name).mkdir(parents=True, exist_ok=True)
        (destination / 'test.sb').write_text(policy)
        env = {k: v for k, v in os.environ.items() if not k.startswith('ULTRAKILL_')}
        env.update(HOME=str(destination / 'home'), CFFIXED_USER_HOME=str(destination / 'home'), TMPDIR=str(destination / 'tmp') + '/',
                   ULTRAKILL_MAC_DATA_PATH=str(output / ('profile-' + mode) / 'ULTRAKILL_Data'),
                   ULTRAKILL_MAC_DIAGNOSTICS_PATH=str(destination / 'diagnostics'), ULTRAKILL_MAC_TEST_MUTE='1',
                   ULTRAKILL_MAC_START_SCENE='Main Menu', GAMEPLAY_COMPUTE_MODE=mode, GAMEPLAY_OUTPUT=str(destination), MTL_HUD_ENABLED='0')
        command = ['/usr/bin/sandbox-exec', '-f', str(destination / 'test.sb'), str(app / 'Contents/MacOS/UnityPlayer'),
                   '-force-metal', '-batchmode', '-screen-fullscreen', '0', '-screen-width', '960', '-screen-height', '600',
                   '-logFile', str(destination / 'Player.log')]
        print('Running isolated compute-' + mode.upper(), flush=True)
        with (destination / 'launch.log').open('w') as log:
            process = subprocess.Popen(command, env=env, cwd=output / ('profile-' + mode), stdout=log, stderr=subprocess.STDOUT)
            try:
                code = process.wait(timeout=75)
            except subprocess.TimeoutExpired:
                process.terminate()
                try: process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
                raise RuntimeError('Isolated test timed out; only its own process was stopped')
        result = json.loads((destination / 'result.json').read_text())
        stats = capture_stats(destination / 'normal.png')
        if code != 0 or not result['success'] or result['engineErrors'] or not stats['looks_rendered']:
            raise RuntimeError('Invalid gameplay baseline; inspect ' + str(destination))
        modes[mode] = {'unity': result, 'baseline': stats}
    if modes['off']['unity']['cameraPosition'] != modes['on']['unity']['cameraPosition'] or modes['off']['unity']['cameraAngles'] != modes['on']['unity']['cameraAngles']:
        raise RuntimeError('Camera poses differ; comparison rejected')
    report = {'status': 'comparison_completed', 'modes': modes, 'comparisons': {},
              'unchanged_original_files': all(Path(p).is_file() and digest(Path(p)) == value for p, value in hashes.items()),
              'original_files_checked': len(hashes), 'limits': 'One scene and synthetic palette; small pixel differences are measured, not treated as exact parity.'}
    for label in ('normal', 'palette', 'restored'):
        report['comparisons'][label] = compare_images(output / 'off' / (label + '.png'), output / 'on' / (label + '.png'))
    (output / 'comparison.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    if not report['unchanged_original_files']:
        raise RuntimeError('Original files changed during the run; check concurrent user activity before attributing it to the protected test')


if __name__ == '__main__':
    main()
